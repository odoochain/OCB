<#
.SYNOPSIS
    Watch the PostgreSQL 5433 instance for the 0xC0000142 degradation.

.DESCRIPTION
    Read-only sampler. It never starts, stops or reconfigures anything; it only
    opens connections and reads counters, so it is safe to leave running.

    Each sample records:
      - whether a NEW backend can be created (this is the actual failure mode:
        the postmaster stays alive and listening while CreateProcess stalls on
        CSRSS, so a plain port check would wrongly report "up")
      - postmaster PID, handle count and thread count
      - handle counts of processes suspected of hooking CreateProcess
      - new 0xC0000142 / sharing-violation lines appearing in the server log
      - free physical memory and session-1 process count

    Output is one CSV row per sample plus a console line. On the first failure
    it prints an alert with the elapsed uptime, which is the number worth
    comparing between configurations.

.PARAMETER IntervalSeconds
    Seconds between samples. Default 60.

.PARAMETER DurationHours
    Stop after this many hours. 0 means run until interrupted. Default 0.

.PARAMETER OutDir
    Where the CSV lands. Default D:\odoochain\pg-monitor.

.PARAMETER StopOnFirstFailure
    Exit as soon as a backend cannot be created. Useful when you only need the
    time-to-failure and do not want the sampler running unattended afterwards.

.EXAMPLE
    .\watch-pg5433.ps1
    Sample every minute until Ctrl+C.

.EXAMPLE
    .\watch-pg5433.ps1 -IntervalSeconds 30 -StopOnFirstFailure
    Tighter sampling, stop at the moment of failure.

.NOTES
    Ctrl+C still produces the summary: the loop body is wrapped so the finally
    block runs on interruption.

    Context: the failure is a slow degradation tied to elapsed runtime, not to
    load. 200 back-to-back connections right after a restart all succeeded, so
    do not expect this script to provoke the fault - it is there to timestamp it.
    See doc/dev/postgres-extensions.md section 6 for the dump analysis.
#>

[CmdletBinding()]
param(
    [ValidateRange(5, 3600)]
    [int]$IntervalSeconds = 60,

    [ValidateRange(0, 720)]
    [double]$DurationHours = 0,

    [string]$OutDir = 'D:\odoochain\pg-monitor',

    [switch]$StopOnFirstFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- target under observation -------------------------------------------------
$PgPort    = 5433
$PgData    = 'D:\mydata\pgdata'
$PgLog     = Join-Path $PgData 'logfile'
$PsqlExe   = 'D:\programs\Scoop\apps\msys2\2026-06-11\mingw64\bin\psql.exe'
# Processes suspected of hooking CreateProcess / file I/O. Handle growth here is
# the pattern that matches the degradation; it is a lead, not a proven cause.
$WatchProcs = @('WDDriveService', 'MsMpEng', 'csrss')

if (-not (Test-Path -LiteralPath $PsqlExe)) {
    throw "psql not found: $PsqlExe"
}
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$csvPath = Join-Path $OutDir "pg5433-watch-$stamp.csv"

# Only report log lines written after the sampler starts, so a restart does not
# replay the whole history as if it were new.
$logOffset = 0
if (Test-Path -LiteralPath $PgLog) {
    $logOffset = (Get-Item -LiteralPath $PgLog).Length
}

function Get-BackendProbe {
    <# Opens a real connection. Returns ok/latency/error. #>
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $out = & $PsqlExe -X -w -h 127.0.0.1 -p $PgPort -d postgres `
                   -tAc 'SELECT 1' 2>&1
        $sw.Stop()
        $text = ($out | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $text -match '^1') {
            return [pscustomobject]@{ Ok = $true; Ms = $sw.ElapsedMilliseconds; Err = '' }
        }
        # A FATAL from the server still proves a backend was created, which is
        # the thing being measured here.
        if ($text -match 'FATAL') {
            return [pscustomobject]@{ Ok = $true; Ms = $sw.ElapsedMilliseconds; Err = 'server FATAL (backend started)' }
        }
        $first = ($text -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
        return [pscustomobject]@{ Ok = $false; Ms = $sw.ElapsedMilliseconds; Err = "$first".Trim() }
    }
    catch {
        $sw.Stop()
        return [pscustomobject]@{ Ok = $false; Ms = $sw.ElapsedMilliseconds; Err = $_.Exception.Message }
    }
}

function Get-PostmasterInfo {
    # Identify the postmaster from postmaster.pid rather than by matching the
    # command line: under a service account the command line is not readable
    # from an unelevated session, and the pid file is authoritative anyway.
    $info = [pscustomobject]@{ Pid = 0; Handles = 0; Threads = 0; WsMb = 0.0; UptimeMin = 0.0; Children = 0 }
    $pidFile = Join-Path $PgData 'postmaster.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $info }
    try {
        $pmPid = [int](Get-Content -LiteralPath $pidFile -TotalCount 1 -ErrorAction Stop).Trim()
        $p = Get-Process -Id $pmPid -ErrorAction Stop
        if ($p.ProcessName -ne 'postgres') { return $info }   # stale pid file

        $info.Pid     = $p.Id
        $info.Handles = $p.HandleCount
        $info.Threads = $p.Threads.Count
        $info.WsMb    = [math]::Round($p.WorkingSet64 / 1MB, 1)
        try { $info.UptimeMin = [math]::Round(((Get-Date) - $p.StartTime).TotalMinutes, 1) } catch { }

        # Child count is the clearest health signal: a healthy postmaster keeps
        # its background workers, a stalled one loses them and cannot fork more.
        try {
            $info.Children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$pmPid" -ErrorAction Stop).Count
        } catch { }
    }
    catch { }
    return $info
}

function Get-NewLogEvents {
    param([ref]$Offset)
    $result = [pscustomobject]@{ Crash = 0; Sharing = 0; Last = '' }
    if (-not (Test-Path -LiteralPath $PgLog)) { return $result }
    try {
        $len = (Get-Item -LiteralPath $PgLog).Length
        if ($len -lt $Offset.Value) { $Offset.Value = 0 }   # log rotated/truncated
        if ($len -eq $Offset.Value) { return $result }

        $fs = [System.IO.File]::Open($PgLog, 'Open', 'Read', 'ReadWrite')
        try {
            [void]$fs.Seek($Offset.Value, 'Begin')
            $reader = New-Object System.IO.StreamReader($fs)
            $chunk  = $reader.ReadToEnd()
        }
        finally { $fs.Dispose() }
        $Offset.Value = $len

        foreach ($line in ($chunk -split "`r?`n")) {
            if ($line -match '0xC0000142')       { $result.Crash++;   $result.Last = $line.Trim() }
            elseif ($line -match 'sharing violation') { $result.Sharing++ }
        }
    }
    catch { }
    return $result
}

# --- run ---------------------------------------------------------------------
$started   = Get-Date
$deadline  = if ($DurationHours -gt 0) { $started.AddHours($DurationHours) } else { [datetime]::MaxValue }
$sampleNo  = 0
$failures  = 0
$crashes   = 0
$sharings  = 0
$firstFail = $null

Write-Host "PostgreSQL 5433 watcher" -ForegroundColor Cyan
Write-Host "  CSV      : $csvPath"
Write-Host "  interval : ${IntervalSeconds}s"
Write-Host ("  until    : " + $(if ($DurationHours -gt 0) { $deadline.ToString('yyyy-MM-dd HH:mm:ss') } else { 'interrupted (Ctrl+C)' }))
Write-Host "  watching : $($WatchProcs -join ', ')"
Write-Host ''

try {
    while ((Get-Date) -lt $deadline) {
        $sampleNo++
        $now = Get-Date

        $probe = Get-BackendProbe
        $pm    = Get-PostmasterInfo
        $ev    = Get-NewLogEvents ([ref]$logOffset)

        $crashes  += $ev.Crash
        $sharings += $ev.Sharing

        $row = [ordered]@{
            Time           = $now.ToString('yyyy-MM-dd HH:mm:ss')
            Sample         = $sampleNo
            BackendOk      = $probe.Ok
            ConnectMs      = $probe.Ms
            Error          = $probe.Err
            PostmasterPid  = $pm.Pid
            PmHandles      = $pm.Handles
            PmThreads      = $pm.Threads
            PmChildren     = $pm.Children
            PmWsMb         = $pm.WsMb
            PmUptimeMin    = $pm.UptimeMin
            NewCrashLines  = $ev.Crash
            NewSharingVios = $ev.Sharing
            FreePhysMb     = 0
            Session1Procs  = 0
        }

        try {
            $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
            $row.FreePhysMb = [math]::Round($os.FreePhysicalMemory / 1KB, 0)
        } catch { }
        try {
            $row.Session1Procs = @(Get-Process -ErrorAction Stop | Where-Object { $_.SessionId -eq 1 }).Count
        } catch { }

        foreach ($name in $WatchProcs) {
            $h = 0
            try {
                $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
                if ($procs.Count -gt 0) {
                    $h = ($procs | Measure-Object -Property HandleCount -Sum).Sum
                }
            } catch { }
            $row["$name`_Handles"] = $h
        }

        [pscustomobject]$row | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Append -Encoding UTF8

        if ($probe.Ok) {
            $msg = "[{0}] #{1,-4} OK   {2,5}ms  pm={3} kids={4} handles={5} uptime={6}min" -f `
                   $now.ToString('HH:mm:ss'), $sampleNo, $probe.Ms, $pm.Pid, $pm.Children, $pm.Handles, $pm.UptimeMin
            Write-Host $msg -ForegroundColor DarkGray
        }
        else {
            $failures++
            if (-not $firstFail) {
                $firstFail = [pscustomobject]@{
                    Time      = $now
                    Sample    = $sampleNo
                    UptimeMin = $pm.UptimeMin
                    Error     = $probe.Err
                }
                Write-Host ''
                Write-Host ("*** FIRST FAILURE at {0} ***" -f $now.ToString('yyyy-MM-dd HH:mm:ss')) -ForegroundColor Red
                Write-Host ("    postmaster uptime : {0} min" -f $pm.UptimeMin) -ForegroundColor Red
                Write-Host ("    postmaster kids   : {0}" -f $pm.Children) -ForegroundColor Red
                Write-Host ("    error             : {0}" -f $probe.Err) -ForegroundColor Red
                Write-Host ''
            }
            else {
                Write-Host ("[{0}] #{1,-4} FAIL kids={2}  {3}" -f $now.ToString('HH:mm:ss'), $sampleNo, $pm.Children, $probe.Err) -ForegroundColor Red
            }
            if ($StopOnFirstFailure) { break }
        }

        if ($ev.Crash -gt 0) {
            Write-Host ("    !! {0} new 0xC0000142 line(s): {1}" -f $ev.Crash, $ev.Last) -ForegroundColor Magenta
        }
        if ($ev.Sharing -gt 0) {
            Write-Host ("    !! {0} new sharing violation(s)" -f $ev.Sharing) -ForegroundColor Yellow
        }

        if ((Get-Date) -ge $deadline) { break }
        Start-Sleep -Seconds $IntervalSeconds
    }
}
finally {
    # Runs on Ctrl+C too, so an interrupted session still yields the summary.
    $elapsed = (Get-Date) - $started
    Write-Host ''
    Write-Host '=== summary ===' -ForegroundColor Cyan
    Write-Host ("  observed        : {0:hh\:mm\:ss}" -f $elapsed)
    Write-Host ("  samples         : {0}" -f $sampleNo)
    Write-Host ("  failed probes   : {0}" -f $failures)
    Write-Host ("  0xC0000142 lines: {0}" -f $crashes)
    Write-Host ("  sharing viol.   : {0}" -f $sharings)
    if ($firstFail) {
        Write-Host ("  FIRST FAILURE   : {0} (postmaster uptime {1} min)" -f `
                    $firstFail.Time.ToString('yyyy-MM-dd HH:mm:ss'), $firstFail.UptimeMin) -ForegroundColor Red
        Write-Host '  -> compare this uptime across configurations' -ForegroundColor Red
    }
    else {
        Write-Host '  no failure observed in this window' -ForegroundColor Green
    }
    Write-Host ("  CSV             : {0}" -f $csvPath)
}

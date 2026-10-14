<#
.SYNOPSIS
    SUPERSEDED - kept for the record, do not run it expecting a log file.

.DESCRIPTION
    Original intent: re-register the service with -l so server stderr lands in a
    file. That does not work. pg_ctl register accepts only -N, -P, -U and -S; -l
    belongs to the start mode and register silently ignores it. Run elevated this
    script reported exactly that: "WARNING: -l does not appear in the service
    command line" and "log file NOT created".

    The working fix is enabling logging_collector in postgresql.conf, which also
    provides rotation through log_rotation_age / log_rotation_size. See
    apply-logging.ps1, then restart the service.

    Context for why the log matters: with the service registered without -l and
    logging_collector off, server stderr was discarded entirely, so the log stops
    at 2026-10-08 11:50 and three days of server logging were lost. The log is
    what identified the 0xC0000142 stall, so without it a recurrence cannot be
    diagnosed.

.PARAMETER LogFile
    Destination log file. Default D:\mydata\pgdata\pgservice.log. Not honoured by
    register.

.EXAMPLE
    # elevated PowerShell - reference only
    .\repair-pg5433-service.ps1

.NOTES
    Does not achieve its stated goal. Use apply-logging.ps1 instead.
    See doc/dev/postgres-extensions.md section 6.
#>

[CmdletBinding()]
param(
    [string]$LogFile = 'D:\mydata\pgdata\pgservice.log'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PgCtl    = 'D:\programs\Scoop\apps\msys2\2026-06-11\mingw64\bin\pg_ctl.exe'
$PsqlExe  = 'D:\programs\Scoop\apps\msys2\2026-06-11\mingw64\bin\psql.exe'
$DataDir  = 'D:\mydata\pgdata'
$SvcName  = 'pgsql-5433'
$PgPort   = 5433

function Assert-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script needs an elevated PowerShell. Right-click PowerShell and choose Run as administrator."
    }
}

Assert-Elevated
Write-Host "Elevated: yes" -ForegroundColor Green

foreach ($exe in @($PgCtl, $PsqlExe)) {
    if (-not (Test-Path -LiteralPath $exe)) { throw "Missing: $exe" }
}
if (-not (Test-Path -LiteralPath $DataDir)) { throw "Missing data dir: $DataDir" }

# --- 1. stop -----------------------------------------------------------------
$svc = Get-Service -Name $SvcName -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq 'Running') {
    Write-Host "Stopping $SvcName ..."
    Stop-Service -Name $SvcName -Force
    Start-Sleep -Seconds 3
}

# Make sure nothing still holds the data directory.
$leftover = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'postgres.exe' }
if ($leftover) {
    Write-Host "Still running, waiting for clean shutdown ..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    $leftover = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -eq 'postgres.exe' }
    if ($leftover) {
        throw "postgres.exe still running (PID $($leftover.ProcessId -join ', ')); refusing to continue"
    }
}
if (Test-Path -LiteralPath (Join-Path $DataDir 'postmaster.pid')) {
    throw "postmaster.pid still present; instance did not shut down cleanly"
}
Write-Host "Data directory free" -ForegroundColor Green

# --- 2-3. unregister / register ----------------------------------------------
$svc = Get-Service -Name $SvcName -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "Unregistering $SvcName ..."
    & $PgCtl unregister -N $SvcName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "Registering $SvcName with -l `"$LogFile`" ..."
& $PgCtl register -N $SvcName -D "$DataDir" -l "$LogFile" -o "-p $PgPort"
if ($LASTEXITCODE -ne 0) { throw "register failed with exit $LASTEXITCODE" }

$reg = Get-CimInstance Win32_Service -Filter "Name='$SvcName'" -ErrorAction SilentlyContinue
if (-not $reg) { throw 'service not found after register' }
Write-Host ("  PathName: " + $reg.PathName) -ForegroundColor DarkGray
if ($reg.PathName -notmatch '-[-]?log|\s-l\s') {
    Write-Host '  WARNING: -l does not appear in the service command line' -ForegroundColor Yellow
}

# --- 4. start ----------------------------------------------------------------
Write-Host "Starting $SvcName ..."
Start-Service -Name $SvcName
Start-Sleep -Seconds 12

# --- 5. verify ---------------------------------------------------------------
Write-Host ''
Write-Host '=== verification ===' -ForegroundColor Cyan

$svc = Get-Service -Name $SvcName
Write-Host ("  service status : " + $svc.Status) -ForegroundColor $(
    if ($svc.Status -eq 'Running') { 'Green' } else { 'Red' })

$ok = $false
try {
    $out = & $PsqlExe -X -w -h 127.0.0.1 -p $PgPort -d postgres -tAc 'SELECT version()' 2>&1
    $txt = ($out | Out-String).Trim()
    if ($txt -match 'PostgreSQL') {
        $ok = $true
        Write-Host ("  connection     : " + (($txt -split "`n") | Select-Object -First 1)) -ForegroundColor Green
    }
    else {
        Write-Host ("  connection     : FAILED - " + (($txt -split "`n") | Select-Object -First 1)) -ForegroundColor Red
    }
}
catch {
    Write-Host ("  connection     : FAILED - " + $_.Exception.Message) -ForegroundColor Red
}

# The point of the whole exercise: is anything actually landing in the log?
if (Test-Path -LiteralPath $LogFile) {
    $len = (Get-Item -LiteralPath $LogFile).Length
    Write-Host ("  log file       : {0} ({1} bytes)" -f $LogFile, $len) -ForegroundColor $(
        if ($len -gt 0) { 'Green' } else { 'Yellow' })
    if ($len -gt 0) {
        Write-Host '  --- last lines ---' -ForegroundColor DarkGray
        Get-Content -LiteralPath $LogFile -Tail 6 | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor DarkGray }
    }
    else {
        Write-Host '    empty: server may not have written yet, or -l did not take effect' -ForegroundColor Yellow
    }
}
else {
    Write-Host ("  log file       : {0} NOT created" -f $LogFile) -ForegroundColor Red
}

Write-Host ''
if ($ok) {
    Write-Host 'Service re-registered and serving.' -ForegroundColor Green
    Write-Host 'Note: -l appends with no rotation; truncate periodically or enable'
    Write-Host '      logging_collector for log_rotation_age / log_rotation_size.'
}
else {
    Write-Host 'Service started but connections still fail - do not leave it in this state.' -ForegroundColor Red
}

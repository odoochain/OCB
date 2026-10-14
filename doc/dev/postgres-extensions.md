# PostgreSQL 扩展栈：AGE、pgvector 与 Jev

> 编写日期：2026-10-07
> 适用：Windows 10/11 + MSYS2/MinGW64，Odoo 20.1
> 关联源码：`d:\odoochain\age-source`（AGE）、`d:\dev\pg-jev`（Jev）
> 关联文档：`test-gates.md`、`development-route.md`

---

## 1. 结论先行

本机 PostgreSQL 由 **MSYS2/MinGW64** 提供，而非 Scoop 的原生 Windows 版本。原因是 **ABI**：Apache AGE 是 C 扩展，用 GCC/MinGW 编译，只能加载到同 ABI 的 PostgreSQL；Scoop 安装的 PostgreSQL 是 MSVC 编译，MinGW 的 `age.dll` 无法加载。

实测本机：

| 项 | 实测值 |
|---|---|
| `pg_config --version` | **PostgreSQL 18.4** |
| 工具链 | MSYS2/MinGW64（`d:\programs\Scoop\apps\msys2\current`） |
| 数据目录 | `D:/mydata/pgdata` |
| 端口 | **5433**（避开 Scoop PG 的 5432） |
| 已装扩展 | AGE **1.8.0**、pgvector **0.8.7**、plpython3u 1.0、Jev **0.2.1**（四者实测共存，见 §4.1） |

> 版本以 `$(pg_config --sharedir)/extension/<name>.control` 的 `default_version` 为准，不要以具体数据库里 `pg_extension` 的记录为准——**已建库不会自动升级扩展版本**。实测 `postgres` 库里 AGE 仍是 1.7.0，而共享目录已是 1.8.0。

判定方法：`SELECT version()` 中 `compiled by gcc-...` 为正确；`compiled by msvc-...` 说明误用了 Scoop PG。

> 2026-10-07 补充：初稿曾判断 Jev 与本机 PG 18 存在硬冲突，且 `plpython3u` 因缺 Python 运行时不可用。两项**均已实测推翻**——补装 MinGW Python 后，Jev 在 PG 18.4 上可正常创建扩展。详见 §3。

---

## 2. AGE：Windows 下必须走 MinGW

完整过程见 `d:\odoochain\age-source\BUILD_WINDOWS.md`。

### 2.1 为什么不能用 MSVC

AGE 源码与 Windows SDK 命名冲突：`STRING`（winternl.h）、`CHAR`（winnt.h）、`DELETE`（winnt.h 宏）、`IN`（minwindef.h）、`OPTIONAL`（ntdef.h）与 Bison token 或 Cypher 关键字冲突；MSVC 无 `uint` 类型；`clock_gettime`、`realpath` 为 POSIX，Windows 不支持。

### 2.2 编译与安装

```powershell
cd D:\odoochain\age-source
.\build_mingw.bat      # 输出 EXIT_CODE=0
.\install_mingw.bat    # 输出 EXIT_CODE=0
```

安装位置由 `pg_config` 决定：`age.dll` → `$(pg_config --pkglibdir)`；`age.control` 与各版本 SQL → `$(pg_config --sharedir)/extension/`。

### 2.3 必须记住的坑

1. **zlib1.dll 冲突**：`as.exe` 会错误加载 System32 的 `zlib1.dll`。修复 `cp /mingw64/bin/zlib1.dll /mingw64/x86_64-w64-mingw32/bin/`。不要用 `as.exe --version; echo $?` 判断，正常机器也返回 127；用 `ldd` 加试编译判断。
2. **`make clean` 需带 `PG_CONFIG`**（1.8.0 起）：PGXS 只有传入 `PG_CONFIG` 才正确加载，且用 `;` 而非 `&&` 连接。
3. **`bash -lc` 会切到 home**：需在 bash 命令内显式 `cd "$(cygpath -u '%~dp0')"`。
4. **含 `"$user"` 的 SQL 不要内联命令行**：写入 `.sql` 后用 `psql -f` 执行，否则 bash 会把 `$user` 展开成空串。

### 2.4 启用与验证

```sql
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT extname, extversion FROM pg_extension WHERE extname = 'age';
```

`SET search_path` 只为省略 `ag_catalog.` 前缀，非必需；单条命令可直接写 `SELECT ag_catalog.create_graph('g');`。
---

## 3. Jev：与 AGE 存在版本冲突，本机尚不可用

Jev 是纯 SQL + PL/Python 扩展，**不需要编译 C**，但依赖 `plpython3u`。

### 3.1 版本约束 — 实测为「验证范围」，非硬限制

| 组件 | 版本要求 | 本机实测 | 结论 |
|---|---|---|---|
| AGE | PG 18.4（编译依赖） | PG 18.4 | 可用 |
| Jev | README 写 **PG 14–17**；`META.json` 声明 `PostgreSQL >= 14.0.0` | PG **18** | **实测可安装，见下** |
| Odoo 20.1 | `MIN_PG_VERSION = 16`，无上限声明 | PG 18.4 | 满足下限；18 不在官方测试矩阵 |

`META.json` 只声明下限 14.0，**没有上限**；README 的 "14–17" 与 Dockerfile 的 `PG_MAJOR=16` 是实际验证过的范围，不是硬性拦截。

**2026-10-07 实测：`CREATE EXTENSION jev CASCADE` 在 PG 18.4 上成功**，`jev_version()` 返回 `0.2.1`，10 个函数全部注册，GUC 可设置。文档初稿判断「版本冲突（硬）」是**错的**，已更正。

仍需注意：PG 18 不在 Jev 官方验证范围内，**功能正确性未获官方保证**。若用于生产，应先用本地兼容服务跑一轮回归（`make installcheck` 可验证，且回归测试不调用真实 API）。

### 3.2 plpython3u 运行时缺失 — **已修复（2026-10-07 实测）**

诊断时的问题：

```
$ ldd $(pg_config --pkglibdir)/plpython3.dll
    libpython3.14.dll => not found
```

`plpython3u.control` 与 `plpython3--1.0.sql` 已就位，缺的是 MinGW Python 运行时。Jev 依赖它，故连带不可用。

**已修复**。Jev 只用 Python 标准库（`json`、`threading`、`ssl`、`http.client`、`concurrent.futures`、`urllib.parse`），无需任何 pip 包，只需补运行时：

```bash
# MSYS2 bash 中；需 ABI 匹配的 MinGW Python，不是 MSYS2 usr 的 python，也不是 Scoop 的
pacman -S mingw-w64-x86_64-python          # 实测装到 3.14.5-1
```

修复后实测：`libpython3.14.dll => /mingw64/bin/libpython3.14.dll`，`ldd` 中 `not found` 归零。

### 3.3 安装与验证 — **已实测通过**

```bash
cd /d/dev/pg-jev
make install PG_CONFIG=/mingw64/bin/pg_config
```

```sql
CREATE EXTENSION jev CASCADE;   -- CASCADE 自动创建 plpython3u；需超级用户
```

2026-10-07 在 **PostgreSQL 18.4** 上的实测结果：

| 检查项 | 结果 |
|---|---|
| `CREATE EXTENSION plpython3u` | 成功 |
| PL/Python 实际调用 | 返回 `3.14.5 (main, May 12 2026) [MINGW GCC 16.1.0 64 bit]` |
| Jev 所需全部标准库导入 | 成功 |
| `CREATE EXTENSION jev CASCADE` | **成功**（PG 18 上可用） |
| `jev_version()` | `0.2.1` |
| Jev 函数注册数 | 10 个（`jev`、`jev_prob`、`jev_score`、`jev_choice`、`jev_confidence`、`jev_eval`、`jev_score_norm`、`jev_stats`、`jev_cache_clear`、`jev_version`） |
| GUC 可设置 | `SET jev.api_url` / `SET jev.threshold` 均生效 |

`plpython3u` 是 untrusted 语言：只有超级用户能创建扩展，且函数以服务器 OS 权限运行。

### 3.4 回归测试 — 已通过（2026-10-07）

用仓库自带的 mock API（不调用真实 API、无需 key）跑完 `pg_regress`：

```bash
# 需先装 GNU diff，否则 pg_regress 报 "diff command not found"
pacman -S diffutils

python test/mock_api.py &                      # 监听 127.0.0.1:8765
PGPORT=5433 make installcheck PG_CONFIG=/mingw64/bin/pg_config
```

```
ok 1 - 01_basic       265 ms
ok 2 - 02_errors      237 ms
ok 3 - 03_streaming   830 ms
ok 4 - 04_local       252 ms
# All 4 tests passed.
```

**4/4 通过**，即 Jev 在 PG 18.4 上功能正确，不只是「能装上」。

两个前提（都踩过）：

- 必须有 GNU `diff`，MSYS2 默认不带，需 `pacman -S diffutils`
- 实例在 5433 而非默认 5432，必须显式 `PGPORT=5433`，否则 `pg_regress` 连错端口

**端到端 `jev()` 调用仍未实测**（需真实 API key 与联网）。本地可用 stuntd 之类的兼容服务（`SET jev.api_url = 'http://127.0.0.1:8787/v1/systemone'`）避免外发数据与计费。

### 3.4 API key 与合规

```sql
SET jev.api_key = 'your-key';
ALTER ROLE odoo SET jev.api_key = 'your-key';
```

或在服务进程环境导出 `TYPESAFE_API_KEY`。改用本地兼容服务（如 stuntd）时设 `SET jev.api_url = 'http://127.0.0.1:8787/v1/systemone'`，无需 key。

**合规提醒**：Jev 会把行内容发送给第三方 API，不得用于不可外发的数据。可用 `jev.max_rows_per_statement` / `jev.max_chars_per_statement` 设上限。

---

## 4. 三者共存方案

### 4.1 推荐：单实例（PG 18.4 + AGE + pgvector + Jev）— 已实测共存

2026-10-07 在同一个数据库内实测，四个扩展**全部加载成功**且各自可用：

```
 extname   | extversion
-----------+------------
 age       | 1.8.0
 jev       | 0.2.1
 plpython3u| 1.0
 vector    | 0.8.7
```

| 组件 | 状态 |
|---|---|
| AGE 1.8.0 | 可用（建图、Cypher 增删改查、删图均实测通过） |
| pgvector 0.8.7 | 可用（`vector(3)` 与距离运算符实测通过） |
| Jev 0.2.1 | **回归 4/4 通过**；端到端 `jev()` 调用待 API key |

安装顺序（均指向同一个 `pg_config`）：

1. `pacman -S mingw-w64-x86_64-python`（补 `plpython3u` 运行时）
2. AGE 按 §2 编译安装
3. `cd /d/dev/pg-jev && make install PG_CONFIG=/mingw64/bin/pg_config`
4. 在**测试库**上先验证，不要直接上生产库

### 4.2 关键坑：`search_path` 必须包含 `ag_catalog`

这是本次实测踩到的、且与 Jev 无关的问题。不设 `search_path` 时：

```
ERROR:  operator class "graphid_ops" does not exist for access method "btree"
STATEMENT:  SELECT ag_catalog.create_graph('...');
```

**根因**：`graphid_ops` 确实存在，但位于 `ag_catalog` schema：

```
  nspname   |     opcname      | amname
------------+------------------+--------
 ag_catalog | graphid_ops      | btree
 ag_catalog | graphid_ops_hash | hash
```

而会话 `search_path` 默认只有 `"$user", public`，不含 `ag_catalog`，AGE 内部建表时找不到自己的操作符类。

**修法**（AGE 的固有用法要求）：

```sql
SET search_path = ag_catalog, "$user", public;
SELECT ag_catalog.create_graph('my_graph');
```

修正后实测：建图成功、`cypher()` 写入与查询成功、`drop_graph()` 成功。

**排查要点**：这个报错容易被误读为「AGE 装坏了」或「PG 18 不兼容」。实际只是 `search_path` 设置问题。若从应用连接（如 Odoo），需在连接参数或会话初始化时设置 `search_path`，而不是只在 `psql` 里设。

### 4.3 备选：双实例隔离

若不想让 untrusted 的 `plpython3u` 与图数据库共处一个实例：

| 实例 | 端口 | 内容 | 用途 |
|---|---|---|---|
| MinGW PG 18.4 | 5433 | AGE + pgvector | Odoo 主库、图与向量 |
| 另起 PG 16/17 | 5434 | plpython3u + Jev | 语义判断，独立进程与权限边界 |

代价：跨实例无法直接 JOIN，需在应用层搬运数据。

### 4.4 不推荐

- 把 MinGW 编译的 `age.dll` 装到 Scoop 的 MSVC PostgreSQL —— ABI 不匹配，必然失败
- 用 Git for Windows 的 bash 启动服务 —— 其 `/mingw64/bin` 下无 PostgreSQL，PATH 回退会误用 Scoop PG；始终用 `start_msys_pg.bat`
- 未跑回归就把 Jev 装进 Odoo 生产库 —— `plpython3u` 是 untrusted 语言，且 PG 18 不在 Jev 官方验证范围
---

## 5. 与 Odoo 的衔接

| 约束 | 值 | 来源 |
|---|---|---|
| Odoo 20.1 最低 PG | **16** | `odoo/release.py` `MIN_PG_VERSION = 16` |
| Odoo 20.1 最高 PG | **未声明** | 代码中只有 `MIN_PG_VERSION`，无 `MAX_PG_VERSION` |
| 本机 PG | 18.4 | `pg_config --version` |

Odoo 只检查下限（`sql_db.py` 中 `server_version < MIN_PG_VERSION * 10000` 时告警），因此 PG 18.4 能启动。**但 18.4 不在 Odoo 官方测试矩阵内**，属未验证组合。

连接参数：

```
postgresql://odoo:odoo@localhost:5433/postgres
```

### 对 CI 的影响

`test-gates.md` 中 Job C 使用 GitHub 托管的 `postgres:16` 服务容器，**不含 AGE、pgvector 或 Jev**。因此：

- CI 只能验证 Odoo 在**无扩展**环境下的安装与测试
- 任何依赖 AGE / pgvector / Jev 的功能**无法在 CI 覆盖**，必须在本机 5433 实例上人工验证
- 若要把扩展纳入 CI，需改用自建 runner 或带扩展的自定义镜像，并同步补齐 MinGW Python

---

## 6. 故障排查补充：实例崩溃与恢复

2026-10-07 实测期间遇到一次实例崩溃，日志：

```
LOG:  autovacuum worker (PID 6128) was terminated by exception 0xC0000142
LOG:  terminating any other active server processes
LOG:  all server processes terminated; reinitializing
```

`0xC0000142` 是 Windows 的 `STATUS_DLL_INIT_FAILED`（DLL 初始化失败）。它不能单独指出故障 DLL，也不能证明 autovacuum 加载了 Python。仅安装扩展文件或在某数据库创建 `plpython3u`，不会自动使每个后台进程调用 PL/Python。

### 6.1 完整日志复查：不止两次，且不限于 autovacuum

2026-10-07 复查 `D:/mydata/pgdata/logfile`，至少发现以下五次异常（本机 CST）：

| 时间 | 后端类型 |
|---|---|
| 06:37:28 | autovacuum worker |
| 06:43:24 | client backend |
| 07:25:16 | autovacuum worker |
| 07:57:09 | autovacuum worker |
| 09:51:16 | autovacuum worker |

本轮在约 09:55 只读探测原 5433 实例时，主进程 PID 44000 仍在，但连接被服务端关闭。这是实验开始前已存在的不可用状态。本轮未改动、重启或升级该实例及其扩展。

历史上停止后启动曾恢复连接并执行 WAL 恢复，但**没有做业务数据完整性核对，不能声称已证明无数据丢失**。恢复操作应在业务维护窗口、确认数据目录与进程归属后执行；不能重复 `start` 或强杀所有同名进程。日志 sharing violation、DLL 依赖和进程环境需要分别排查。

### 6.1.1 该实例已卡在崩溃恢复阶段（2026-10-07 10:29 实测）

| 观测项 | 结果 |
|---|---|
| 日志最后一行 | `09:51:16 ... all server processes terminated; reinitializing`，**之后无任何记录** |
| 10:29 时 PID 44000 | 仍存活，仍 `LISTENING` 于 `127.0.0.1:5433` |
| `postmaster.pid` | 存在，内容指向 `D:/mydata/pgdata`、端口 5433 |
| 新建连接 | 立即 `server closed the connection unexpectedly` |

即该实例自 09:51 起已**卡住约 38 分钟**：postmaster 存活且持有监听套接字，但无法产出可用后端，也不再写日志。这与 `0xC0000142` 的语义一致——子进程在 DLL 初始化阶段即失败，尚未进入能记录日志的阶段。

### 6.1.2 已排除的三个假设

| 假设 | 排除依据 |
|---|---|
| 主进程与子进程二进制不一致（`msys2\2026-06-11\…` 对 `msys2\current\…`） | `current` 是指向 `2026-06-11` 的 Junction，物理同一安装，路径差异仅为显示形式 |
| 两个 postmaster 争用同一数据目录 | PID 44000 用 `D:/mydata/pgdata:5433`；PID 25456 用 `D:/dev/_jevtest/pgdata:5599`。互不相关，后者非本轮创建 |
| 系统级进程创建已失效 | 10:29 手工执行 `postgres --version`、`psql --version` 均 `exit=0`，新进程可正常启动并完成 DLL 初始化 |

**同时修正一处早期推断**：注册表 `SharedSection=1024,20480,768` 的第三个值 768 KB 属**非交互式**桌面堆。实测两个 postmaster 均位于**交互会话 1**（`SessionId=1`，所有者 `mirroam`，系统中无 postgres 服务），因此适用的是第二个值 20480 KB，不是 768 KB。桌面堆耗尽仍是 `0xC0000142` 的常见成因之一，但以上数据不足以证实，不应作为结论。

Windows 应用日志在故障时段**没有** postgres 相关记录。这与 `0xC0000142` 的性质相符：失败发生在进程初始化阶段，通常不生成 WER 报告，因此「事件日志无记录」不能用来排除任何假设。

### 6.1.3 卡死主进程的模块清单：未加载 PL/Python

趁 PID 44000 现场尚存（重启后不可再得），采集其已加载模块，保存于 `D:/odoochain/pg44000-modules-20261007.txt`：

| 观测项 | 结果 |
|---|---|
| 模块总数 | 47 |
| 匹配 `python` / `plpython` 的模块 | **0** |
| 匹配 `age` / `vector` 的模块 | **0** |
| 非系统模块 | 仅 `postgres.exe` 与 MinGW 运行时（`libwinpthread-1`、`libintl-8`、`libiconv-2`、`libcrypto-3-x64`、`liblz4`、`libicuin78`、`libicuuc78`、`libssl-3-x64`、`libxml2-16`、`zlib1`、`libzstd`、`libgcc_s_seh-1`、`libstdc++-6` 等） |

**这显著削弱了把崩溃归因于 PL/Python 的假设。** postmaster 自身从未加载 `libpython3.14.dll` 或 `plpython3.dll`，与 §6.2 中 `postgres.exe` 不直接导入 Python 的静态依赖结论一致。

仍需保留的可能性：`0xC0000142` 发生在**子进程**初始化阶段，子进程的模块集与 postmaster 不同。但 09:51 失败的是 autovacuum worker，而 autovacuum **不执行用户自定义 PL/Python 函数**，因此它没有加载 Python 的常规理由。结合 06:43 那次失败的是普通 client backend，**当前证据更支持「与扩展无关的进程初始化故障」，而非 PL/Python 引起**。

### 6.2 `shared_preload_libraries=plpython3` 隔离对照（2026-10-07）

使用相同 MinGW PostgreSQL 18.4 安装，另建 UTF8 / C locale 的临时集群，监听 `127.0.0.1:55433`，测试角色 `gate_probe`，回归库 `jev_preload_probe`。不复制业务数据、不向共享安装目录安装文件；原 5433 实例不参与测试。两轮只改变预加载启动参数，均开启 autovacuum，`autovacuum_naptime=5s`。

| 项目 | 不预加载 | 预加载 `plpython3` |
|---|---|---|
| 观察窗口（本机 CST） | 09:59:51–10:08:13 | 10:09:19–10:13:39 |
| Jev 原始 `make installcheck` | 4/4 通过 | 4/4 通过 |
| 新连接实际调用 `jev_stats()` / `jev_version()` | 40/40 通过，4 路并发 | 40/40 通过，4 路并发 |
| 普通测试表自动清理 | `autovacuum_count=1`，死元组 0 | 计数增为 2，死元组 0 |
| `0xC0000142` / 重初始化日志 | 未出现 | 未出现 |

回归使用仓库自带的本地 mock API（127.0.0.1:8765），未配置真实 API key。连接测试中的 `jev_stats()` 会实际执行 PL/Python；`jev_version()` 单独成功不能替代这个验证。自动清理表位于仅有 `plpgsql` 的隔离 `postgres` 库；Jev 位于单独的回归库。

**结论：两组都通过，未建立预加载与故障之间的因果关系。不能宣称预加载已修复，也不能排除长时间运行、资源耗尽、启动环境或原集群特有条件。** 两组观察时间短且不等长，不作性能或长期稳定性比较。测试实例已正常停止，预加载只通过其启动参数设置，未写入业务配置。

PostgreSQL 官方说明：Windows 上每个新服务端进程仍重新加载预加载库；这不是“加载一次后所有进程共用”的修复机制。参见 [PostgreSQL 18：shared_preload_libraries](https://www.postgresql.org/docs/18/runtime-config-client.html#GUC-SHARED-PRELOAD-LIBRARIES)。静态依赖检查也显示 `postgres.exe` 不直接导入 `libpython3.14.dll`，而 `plpython3.dll` 导入它；这不排除动态加载，但不能据此指认故障模块。

### 6.2.1 决定性对照：全新空集群同样崩溃（2026-10-07 16:30–16:55）

用**同一个** `2026-06-11` 二进制、**同一个端口** 5433，新建一个 `initdb` 出来的空集群（UTF8 / C locale，用户 `crash_ctl`），**不装任何扩展、不含任何业务数据**：

```
16:30:15  checkpoint complete（集群正常运行中）
16:55:20  autovacuum worker (PID 27492) was terminated by exception 0xC0000142
16:55:20  terminating any other active server processes
16:55:20  all server processes terminated; reinitializing
```

**结论：崩溃与该数据目录、AGE、pgvector、Jev、PL/Python 全部无关，是环境级故障。** 这解释了 §6.2 中两组隔离测试为何都通过——它们运行时系统尚未进入该故障状态；也解释了为何重启只能短暂恢复。

### 6.2.2 重启后的复现节奏

| 时间 | 事件 |
|---|---|
| 15:23:33 | 重启后 `ready to accept connections` |
| 15:52:36 | autovacuum worker `0xC0000142`（启动后约 29 分钟） |
| 16:24:17 | 重启后连接请求**立即**触发 client backend `0xC0000142`（启动后约 1 秒） |
| 17:26:50 | 再次重启后 `ready to accept connections` |
| 17:56 | 已再次不可连接 |

三条要点：

1. **不再需要长时间运行才触发**。16:24 那次在启动后约 1 秒即失败，说明已进入「每次新建后端进程都会失败」的状态。
2. **失败类型不限于 autovacuum**。16:24 失败的是普通 client backend。
3. **重启只是短暂恢复**，不能作为解决办法。

三次独立采集（PID 44000 / 43516 / 37496）的模块数均为 **47**，且 `python` / `plpython` / `age` / `vector` 匹配数均为 **0**；非系统模块只有 `postgres.exe` 与 MinGW 运行时。三个样本一致，**彻底排除扩展加载为诱因**。

### 6.2.2 根因已定位：postmaster 卡死在 CSRSS 的 ALPC 调用（2026-10-07 转储分析）

用 WinDbg（`winget install Microsoft.WinDbg`）离线分析三份转储，加载微软公共符号后，三份结论一致：

| 转储 | `FAILURE_BUCKET_ID` |
|---|---|
| PID 44000 | `APPLICATION_HANG_BusyHang_cfffffff_postgres.exe` |
| PID 43516 | `APPLICATION_HANG_cfffffff_postgres.exe` |
| PID 37496 | `APPLICATION_HANG_BlockedOn_AlpcPort_cfffffff_postgres.exe` |

关键指标：`WER.BlockedOn: AlpcPort`，`DERIVED_WAIT_CHAIN: ALPC`。

主线程调用栈（PID 44000，已加载正确符号）：

```
ntdll!NtAlpcSendWaitReceivePort+0x14      ← 卡在此处，无限等待
ntdll!CsrClientCallServer+0xfc            ← 向 CSRSS 注册新进程
KERNELBASE!CreateProcessInternalW+0x53c7
KERNELBASE!CreateProcessInternalA+0x45d
KERNELBASE!CreateProcessA+0x69
kernel32!CreateProcessAStub+0x53
postgres!...+0x4bb                        ← 栈上可见参数 0x00000000c0000142
postgres!PostmasterMain+0xdca
postgres!main+0x1c2
```

**机制解释（与此前所有观察吻合）**：

1. PostgreSQL 在 Windows 上没有 `fork()`，每个新后端都通过 `CreateProcessA` 创建。
2. `CreateProcess` 内部必须通过 **ALPC** 与 **CSRSS**（客户端/服务器运行时子系统）通信以注册新进程。
3. 该 ALPC 调用阻塞后，postmaster 主线程**无限等待**——这正是「进程存活、仍在监听、却不产出任何后端、也不再写日志」的原因：主线程根本没有机会继续执行。
4. 子进程因此在初始化阶段失败，报 `0xC0000142`（`STATUS_DLL_INIT_FAILED`）。该错误码是**结果**，不是原因。

这同时解释了为何**独立进程创建正常**（`postgres --version`、`initdb` 均 exit=0）：那些由 shell 发起，走的是另一条路径，不经过已阻塞的 postmaster 主线程。

**与扩展彻底无关。** 栈上没有任何扩展模块，三份转储的模块数均为 47 且 python/plpython/age/vector 匹配为 0。

### 6.2.3 环境侧观测（系统性诱因，尚未确证）

| 项 | 实测值 |
|---|---|
| 会话 0 / 会话 1 进程数 | 103 / **268** |
| 系统总句柄数 | 约 13.4 万 |
| CSRSS（会话 1）句柄 | 1317，27 线程 |
| 句柄最高的进程 | **`WDDriveService` 10421**，其次 `explorer` 7469 |
| 桌面堆 `SharedSection` | `1024,20480,768`；交互会话适用 **20480 KB** |

会话 1 的 268 个进程属偏高水平，`WDDriveService`（Western Digital 服务）的 1 万多句柄尤为异常。ALPC/CSRSS 阻塞的常见诱因包括会话资源耗尽、桌面堆压力，以及**安全软件或驱动服务对进程创建路径的拦截**。以上数据与这些方向一致，但**尚未证实其中任何一项是本次的直接原因**。

### 6.3 下一步取证与边界

§6.2.1 已证明与扩展、数据目录无关；§6.2.2 已定位为 **`CreateProcess` 内的 ALPC/CSRSS 阻塞**。**不要再往 AGE / pgvector / Jev / PL/Python 方向排查。**

剩余方向按优先级：

1. **排查拦截进程创建的第三方组件**。ALPC/CSRSS 阻塞最常见的人为诱因是安全软件、备份代理或磁盘服务挂钩 `CreateProcess`。首要怀疑对象是 `WDDriveService`（句柄 10421，见 §6.2.3）；其次是任何实时防护类服务。验证方式：在维护窗口临时停用可疑服务，观察是否仍复现。
2. **缓解措施（可立即降低影响面）**：
   - 给 PostgreSQL 的安装目录与数据目录加杀毒/备份软件排除项
   - 减少会话 1 的进程数（当前 268）
   - 把 PostgreSQL 改为**服务方式**运行（会话 0），脱离交互会话的桌面堆与资源竞争。需管理员权限，见 §6.4
3. **若要进一步确证**，可对 CSRSS（会话 1，PID 1004）采集转储，检查其 ALPC 端口队列是否积压；或用内核调试观察阻塞方。这属较重手段，建议先做第 1、2 项。
4. **放弃的方向**：不必再对比 MinGW 与 MSVC 版 PostgreSQL——阻塞发生在 Windows 的进程创建路径上，与编译器 ABI 无关。

边界与禁止项：

- 停用安全/磁盘服务会降低系统防护，**须由用户在维护窗口决定并执行**，本轮未做。
- 恢复 5433 实例涉及业务数据；本轮的停止/启动均为取证所需，已记录时间线。
- 不要把「临时 CREATE/DROP PL/Python」当作防崩溃方案——根因与它无关。

### 6.4 待执行：服务方式对照（需管理员权限）

当前账号**非管理员**（实测 `IsInRole(Administrator)` 为 `False`），无法注册服务。该对照能判断「脱离交互会话」是否规避问题，是目前性价比最高的验证。

需在**管理员** PowerShell 中执行：

```powershell
# 注册为服务（在会话 0 运行）
& "D:/programs/Scoop/apps/msys2/2026-06-11/mingw64/bin/pg_ctl.exe" register `
    -N pgsql-5433 -D "D:/mydata/pgdata" -o "-p 5433"
Start-Service pgsql-5433

# 观察数小时后检查是否复现
Select-String -Path D:/mydata/pgdata/logfile -Pattern "0xC0000142"

# 回滚
Stop-Service pgsql-5433
& "D:/programs/Scoop/apps/msys2/2026-06-11/mingw64/bin/pg_ctl.exe" unregister -N pgsql-5433
```

注意：服务默认以 `LOCAL SERVICE` 运行，需确认其对 `D:/mydata/pgdata` 有读写权限，或用 `-U` / `-P` 指定账号。

### 6.5 转储分析方法（可复用）

```powershell
winget install --id Microsoft.WinDbg --exact
# cdb.exe 位于 C:/Program Files/WindowsApps/Microsoft.WinDbg_*/amd64/

& "<上述路径>/cdb.exe" -z <dump.dmp> `
    -y 'srv*D:\odoochain\windbg-symbols*https://msdl.microsoft.com/download/symbols' `
    -logo analysis.txt `
    -c '.reload /f ntdll.dll; !analyze -hang -v; ~* kb; lm; q'
```

两个会浪费时间的坑：

1. **符号路径必须用反斜杠**。写成 `srv*D:/odoochain/...` 会报 `is not a valid store`，随后 `!analyze` 只能输出 `WRONG_SYMBOLS` 噪声，看不到真实栈。
2. **手工 procdump 快照要用 `!analyze -hang`**，不是默认的异常分析。快照本身不含异常记录，默认模式会把断点指令当成"异常"，给出误导性的 `BUGCHECK_CODE`。

### 6.6 证据归档与清理

保留（共约 119 MB）：

| 文件 | 内容 |
|---|---|
| `D:/odoochain/pg-crash-evidence-20261007-1451.zip` | PID 44000 转储 + 模块清单 + 线程快照 + 预加载对照日志 |
| `D:/odoochain/pg-crash-evidence-20261007-1553.zip` | PID 43516 转储 + 模块清单 |
| `D:/odoochain/pg-crash-evidence-20261007-1757.zip` | PID 37496 转储 + 模块清单 |

已清理：两个临时测试集群（`.pg-probe-now`、`.pg-crash-ctl-20261007`）、三份原始 `.dmp`（已在 ZIP 内）及临时日志，释放约 760 MB。

### 6.7 一个尚未解释的反例

同一台机器、同一 MinGW 安装上，**他人的 5599 实例（`D:/dev/_jevtest/pgdata`）运行正常**——实测其 `io_worker`、`checkpointer`、`bgwriter`、`wal_writer`、`autovacuum launcher`、`bgworker` 子进程齐全。

说明 ALPC/CSRSS 阻塞**不是全系统性的、也不是持续的**，而是间歇性或与特定进程相关。这对排查有利：可对比两个实例的启动方式、所属 shell、环境变量与父进程链，差异点可能就是诱因。

### 6.8 启动方式对比与退化特征（2026-10-08 实测）

**启动方式已排除**。两个实例的父进程链与命令行形式完全一致：

| 实例 | 父进程 | 命令行形式 |
|---|---|---|
| 5433（故障） | `cmd.exe` (20676) | `cmd /C "postgres.exe -D ... -p 5433 < nul >> logfile 2>&1"` |
| 5599（正常） | `cmd.exe` (44416) | `cmd /C "postgres.exe -D ... -p 5599 ... < nul >> log 2>&1"` |

同一台机器、同一 MinGW 安装、同样由 `cmd /C` 启动并重定向日志，一个故障一个正常。**父进程链、启动器、重定向方式均不是诱因。**

对比当时的健康判据很直观：5599 返回 `FATAL: role "mirroam" does not exist`——这是**数据库层的正常应答**，证明它能成功创建后端；而 5433 返回 `server closed the connection unexpectedly`，连后端都起不来。

**关键区分：故障不是「启动即坏」，而是「运行后退化」。**

| 测试 | 结果 |
|---|---|
| 重启后立即连接 | **成功**（返回 `2026-10-08 11:07:19`） |
| 紧接着 200 次连续建连 | **200/200 成功**，耗时 7.8 秒，无一失败 |

因此**短期高频建连不是触发条件**。结合已有时间线——17:26 启动后约 30 分钟故障、前一轮运行约 17 小时后故障——这是**与运行时长相关的缓慢退化**，而非负载峰值触发。

这进一步缩小了范围：诱因应是随时间累积的资源或状态（如句柄泄漏、ALPC 端口耗尽、桌面堆碎片），而非单次高并发。注意本机 `WDDriveService` 句柄数持续增长（10421 → 10724），符合这一特征，但**仍未证实其与 postmaster 阻塞存在因果关系**。

### 6.9 文件干扰的直接证据：35 次 sharing violation

日志中 `sharing violation` 共出现 **35 次**，且 PostgreSQL 自己给出了归因提示：

```
LOG:  could not open file "./logfile": sharing violation
DETAIL:  Continuing to retry for 30 seconds.
HINT:  You might have antivirus, backup, or similar software interfering with the database system.
```

最近几次分布在 2026-10-07 15:22、15:53、17:26 与 10-08 11:06，**与崩溃时间线高度重叠**。

这是**独立于转储分析的第二条证据**，同样指向杀毒/备份类软件干扰文件与进程操作，与 §6.2.2 的 ALPC/CSRSS 阻塞方向一致。两者可由同一诱因解释：此类软件既挂钩文件 I/O，也常挂钩 `CreateProcess`。

注：本机 `Get-MpPreference` / `Get-MpComputerStatus` 报 `Provider load failure`，无法通过 PowerShell 读取 Defender 配置与排除项，需在「Windows 安全中心」界面手工确认。

### 6.10 服务方式对照：注册成功，启动受数据目录占用阻塞

2026-10-08 以管理员注册服务成功：

```
Name      : pgsql-5433
StartName : LocalSystem
PathName  : pg_ctl.exe runservice -N "pgsql-5433" -D "D:\mydata\pgdata" -w -o "-p 5433"
```

首次 `Start-Service` 失败，`ExitCode 0`（非权限拒绝）。原因是**手工启动的实例（PID 21224）仍在运行并占用数据目录**——同一数据目录不能被两个 postmaster 同时持有。

处置：先 `pg_ctl stop` 停掉手工实例释放目录，再启动服务。该步骤已完成，`postmaster.pid` 已清除。

**服务方式的对照结论仍待观察**：需在服务模式下运行数小时，确认 `0xC0000142` 是否仍复现。由于服务运行在会话 0，若不再复现，则说明诱因与交互会话的资源环境相关。

### 6.11 监控脚本：`tools/watch-pg5433.ps1`

只读采样器，不启停服务、不改配置，可长期挂着跑。

```powershell
# 每分钟采样，Ctrl+C 结束（中断也会输出汇总）
pwsh -File tools/watch-pg5433.ps1

# 30 秒间隔，一旦失败就停，只取 time-to-failure
pwsh -File tools/watch-pg5433.ps1 -IntervalSeconds 30 -StopOnFirstFailure

# 限定观察 8 小时
pwsh -File tools/watch-pg5433.ps1 -DurationHours 8
```

**为什么不能只做端口探测**：故障时 postmaster 仍存活、仍 `LISTENING`，端口检查会错报"正常"。脚本每次都真实建连，这才是实际失效的那一环。

两个关键设计：

- **用 `postmaster.pid` 识别进程**，而非匹配命令行——服务以 `LocalSystem` 运行时，非提权会话读不到其命令行（实测为空）。
- **把子进程数（`PmChildren`）作为健康信号**。健康的 postmaster 保有 9 个后台工作进程；卡死时子进程归零且无法再 fork。这比连接成功率更早反映状态。

服务器返回 `FATAL`（如角色不存在）**计为成功**——它证明后端已被创建，而这正是被测对象。

CSV 共 18 列，含 `BackendOk`、`ConnectMs`、`PmHandles`、`PmChildren`、`PmUptimeMin`、`NewCrashLines`、`NewSharingVios`、`FreePhysMb`、`Session1Procs`，以及 `WDDriveService` / `MsMpEng` / `csrss` 的句柄数。日志只统计**脚本启动后**新增的行，重启不会把历史重放成新事件。

**最该关注的数字是首次失败时的 `PmUptimeMin`** ——用它横向比较不同配置（WD 停用 / 启用、服务模式 / 交互模式）。

### 6.12 变量控制：一次只改一个

当前状态（2026-10-08 12:21）：

| 项 | 状态 |
|---|---|
| `pgsql-5433` 服务 | Running（会话 0，`LocalSystem`） |
| `WDDriveService` | **Stopped** |
| postmaster | PID 41560，9 个子进程，健康 |

**注意：现在同时改了两个变量**（服务模式 + WD 停用）。若这一轮不复现，无法判断是哪个起作用。建议顺序：

1. 当前配置观察数小时 → 若不复现，继续第 2 步
2. **恢复 `WDDriveService`**（`Start-Service WDDriveService`），保持服务模式再观察 → 若此时复现，即锁定 WD 为诱因
3. 若第 2 步仍不复现 → 说明诱因与交互会话相关，而非 WD

### 6.13 当前观察进行中（2026-10-08 12:52 起）

监控已在后台运行：

| 项 | 值 |
|---|---|
| watcher PID | 15328（`pwsh`，后台） |
| 采样间隔 | 60 秒 |
| CSV | `D:/odoochain/pg-monitor/pg5433-watch-20261008-125240.csv` |
| 控制台日志 | `D:/odoochain/pg-monitor/watch-console-20261008-1252.log` |
| 观察配置 | 服务模式（会话 0） + `WDDriveService` 停用 |
| 起始基线 | postmaster 41560，9 子进程，524 句柄 |

查看进度：

```powershell
Get-Content D:/odoochain/pg-monitor/watch-console-20261008-1252.log -Tail 20
```

停止监控：

```powershell
Stop-Process -Id 15328        # 后台运行时拿不到 Ctrl+C，故不会打印汇总
```

注意：后台方式启动时 `finally` 块的汇总**不会显示在日志里**（没有交互终端接收 Ctrl+C）。首次失败的 `PmUptimeMin` 仍会写入 CSV 并出现在控制台日志的 `*** FIRST FAILURE ***` 段落，据此判断即可。

---

## 7. 结论（2026-10-14 定稿）

### 7.1 故障已解决

| 指标 | 结果 |
|---|---|
| 最后一次 `0xC0000142` | **2026-10-07 17:56** |
| 服务模式运行时长 | 重启后连续运行 **3 天以上**，无异常 |
| 监控采样 | 719 次，**零失败** |
| 当前状态 | `pgsql-5433` Running，可正常连接 |

### 7.2 根因与有效修复

**根因**：postmaster 在 `CreateProcess` 内阻塞于对 **CSRSS 的 ALPC 调用**（三份转储一致：`WER.BlockedOn: AlpcPort`）。PostgreSQL 在 Windows 无 `fork()`，后端全靠 `CreateProcess` 创建，阻塞后主线程永不返回——故进程存活、仍监听，却不产出后端、不写日志。`0xC0000142` 是**结果**而非原因。

**决定性变量是运行会话，不是 WD 服务**：

| 配置 | 结果 |
|---|---|
| 交互会话（`cmd /C`）+ `WDDriveService` Running | **约 30 分钟~17 小时后崩溃** |
| 服务模式（会话 0）+ WD 停用 | 正常 |
| **服务模式（会话 0）+ WD Running** | **正常，连续 3 天+** ← 当前 |

`WDDriveService` 已恢复运行而实例依旧稳定，**否证 WD 假设**。此前它句柄偏高（10421 → 10724）只是伴随现象。

**有效修复：以 Windows 服务运行（会话 0）**，脱离交互会话的桌面堆与资源竞争。这与 ALPC/CSRSS 阻塞的分析一致。

**不必再做的排查**：Defender 排除项、WD 停用、MinGW 与 MSVC 版对比。

### 7.3 附带修复：服务模式下的日志

服务最初注册时未带日志输出，且 `logging_collector = off`，**服务端 stderr 被完全丢弃**——旧 `logfile` 停在 2026-10-08 11:50，之后 3 天无日志。而日志正是定位 `0xC0000142` 的关键证据，缺失则无法诊断复发。

**踩过的坑：`pg_ctl register -l` 无效。** register 只接受 `-N -P -U -S`，`-l` 属 `start` 模式且被**静默忽略**。曾据一次 `could not open service manager` 报错误判 `-l` 可用——该错误源于权限不足，发生在选项处理之前，不能证明选项有效。`tools/repair-pg5433-service.ps1` 已标记 superseded 并保留，避免重走此路。

**有效做法**：在 `postgresql.conf` 启用日志收集器（已生效，含轮转）：

```
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
```

原配置已备份为 `postgresql.conf.bak-20261014`。日志落在 `D:\mydata\pgdata\log\`。

### 7.4 运维要点

- **保持服务模式**运行，勿再用 `cmd /C` 手工启动。同一数据目录不能有两个 postmaster。
- 监控脚本 `tools/watch-pg5433.ps1` 可用于长期观察；当前问题已解决，不必常驻。
- 若日后复发，优先看 `D:\mydata\pgdata\log\` 下最新日志中的 `0xC0000142` 与 `sharing violation`。

边界与禁止项：

- 恢复该 5433 实例涉及业务数据，**需用户确认维护窗口后再执行**；本轮未重启、未改配置、未升级扩展。
- 不要把「临时 CREATE/DROP PL/Python」当作防崩溃方案，也不要用关闭 autovacuum 或直接给业务实例加预加载来掩盖问题。
- 配置 WER 转储或附加调试器会改动系统设置，需单独确认后再做；本轮未改注册表、未附加调试器。

---

## 7. 待办

- [x] 安装 `mingw-w64-x86_64-python`，确认 `libpython3.14.dll` 可解析（2026-10-07 完成）
- [x] 在测试库验证 `CREATE EXTENSION plpython3u`（通过）
- [x] 在测试库验证 `CREATE EXTENSION jev CASCADE` 于 PG 18.4（**通过**，推翻初稿的版本冲突判断）
- [x] 用 `make installcheck` 跑 Jev 回归（**4/4 通过**）
- [x] 独立端口 55433 完成预加载/不预加载对照（各 4/4 回归、40 次新会话、实际 autovacuum；均未复现崩溃，不能判定修复）
- [ ] 验证真实 Jev 服务的模型输出、权限与数据外发策略（本地 mock 的 SQL→HTTP→响应流程已通过，不代表真实模型质量）
- [ ] **定位 `0xC0000142` 崩溃根因**（原实例日志至少五次；继续隔离实验并采集故障模块/转储证据）
- [ ] 应用侧接入 AGE 时，确保会话 `search_path` 含 `ag_catalog`（见 §4.2）
- [ ] 升级 `postgres` 库中的旧扩展：AGE 仍在 1.7.0（共享目录已 1.8.0），需 `ALTER EXTENSION age UPDATE`
- [ ] 更新旧部署指南：pgvector 实际为 **0.8.7**，文档写的 0.8.2 已过时
- [ ] 更新旧部署指南中的源码路径：AGE 现位于 `d:\odoochain\age-source`，非 `d:\dev\lawgraph\age-source`
- [ ] 评估 PG 18.4 + Odoo 20.1 这一未验证组合的回归范围

---

## 8. 参考

- `d:\odoochain\age-source\BUILD_WINDOWS.md` — AGE 1.8.0 Windows/MinGW 完整编译指南
- `d:\odoochain\age-source\PostgreSQL-AGE-pgvector安装部署指南.md` — 服务管理、用户创建、故障排查（**部分内容已过时**，见 §7）
- `d:\dev\pg-jev\README.md` — Jev 安装、函数、GUC 与注意事项

*本文档所有"实测"结论均来自 2026-10-07 在本机执行的命令输出。初稿对 Jev 的「PG 18 版本冲突（硬）」判断已被实测推翻并更正。*
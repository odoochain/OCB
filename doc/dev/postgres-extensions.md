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
| 已装扩展 | AGE 1.8.0、pgvector **0.8.6**、plpython3u（control 在，运行时缺失，见 §3） |

判定方法：`SELECT version()` 中 `compiled by gcc-...` 为正确；`compiled by msvc-...` 说明误用了 Scoop PG。

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

### 3.1 版本冲突（硬）

| 组件 | 版本要求 | 本机实测 | 结论 |
|---|---|---|---|
| AGE | PG 18.4（编译依赖） | PG 18.4 | 可用 |
| Jev | README 明确 **PG 14–17**；`META.json` 声明 `PostgreSQL >= 14.0.0` | PG **18** | **超出官方支持上限** |
| Odoo 20.1 | `MIN_PG_VERSION = 16`，无上限声明 | PG 18.4 | 满足下限，但 18 未被官方测试矩阵覆盖 |

`META.json` 只声明下限 14.0，没有上限；README 的 "14–17" 与 Dockerfile 的 `PG_MAJOR=16` 是实际验证过的范围。**PG 18 上 Jev 未经验证**。

### 3.2 plpython3u 运行时缺失（硬）

实测：

```
$ ldd $(pg_config --pkglibdir)/plpython3.dll
    libpython3.14.dll => not found
$ ls /mingw64/bin/libpython*                    -> 无
$ pacman -Q | grep mingw-w64-x86_64-python      -> 未安装
```

`plpython3u.control` 与 `plpython3--1.0.sql` 已就位，但 **MinGW 的 Python 运行时未安装**，因此 `CREATE EXTENSION plpython3u` 会因缺 `libpython3.14.dll` 失败。Jev 依赖它，故连带不可用。

### 3.3 修复 Jev 的最小路径

Jev 只用 Python 标准库（`json`、`threading`、`ssl`、`http.client`、`concurrent.futures`、`urllib.parse`），**无需任何 pip 包**，只需补 Python 运行时：

```bash
# MSYS2 bash 中；需 ABI 匹配的 MinGW Python，不是 MSYS2 usr 的 python，也不是 Scoop 的
pacman -S mingw-w64-x86_64-python          # 实测仓库可获取，3.14.5-1
ldd $(pg_config --pkglibdir)/plpython3.dll # 确认 libpython3.14.dll 已解析
```

然后：

```bash
cd /d/dev/pg-jev
make install PG_CONFIG=/mingw64/bin/pg_config
```

```sql
CREATE EXTENSION jev CASCADE;   -- CASCADE 自动创建 plpython3u；需超级用户
```

`plpython3u` 是 untrusted 语言：只有超级用户能创建扩展，且函数以服务器 OS 权限运行。

### 3.4 API key 与合规

```sql
SET jev.api_key = 'your-key';
ALTER ROLE odoo SET jev.api_key = 'your-key';
```

或在服务进程环境导出 `TYPESAFE_API_KEY`。改用本地兼容服务（如 stuntd）时设 `SET jev.api_url = 'http://127.0.0.1:8787/v1/systemone'`，无需 key。

**合规提醒**：Jev 会把行内容发送给第三方 API，不得用于不可外发的数据。可用 `jev.max_rows_per_statement` / `jev.max_chars_per_statement` 设上限。

---

## 4. 三者共存方案

### 4.1 推荐：单实例（PG 18.4 + AGE + pgvector），Jev 待验证

| 组件 | 状态 |
|---|---|
| AGE 1.8.0 | 已装可用 |
| pgvector 0.8.6 | 已装可用 |
| Jev | 需先补 MinGW Python，且 PG 18 未验证 |

前置条件：

1. 安装 `mingw-w64-x86_64-python`，确认 `libpython3.14.dll` 可解析
2. `make install` Jev 到同一个 `pg_config`（`/mingw64/bin/pg_config`）
3. 先在**测试库**验证，不要直接上生产库

### 4.2 备选：双实例隔离

若 PG 18 上 Jev 不可用，或不想让 untrusted 的 `plpython3u` 与图数据库共处一个实例：

| 实例 | 端口 | 内容 | 用途 |
|---|---|---|---|
| MinGW PG 18.4 | 5433 | AGE + pgvector | Odoo 主库、图与向量 |
| 另起 PG 16/17 | 5434 | plpython3u + Jev | 语义判断，独立进程与权限边界 |

代价：跨实例无法直接 JOIN，需在应用层搬运数据。

### 4.3 不推荐

- 把 MinGW 编译的 `age.dll` 装到 Scoop 的 MSVC PostgreSQL —— ABI 不匹配，必然失败
- 用 Git for Windows 的 bash 启动服务 —— 其 `/mingw64/bin` 下无 PostgreSQL，PATH 回退会误用 Scoop PG；始终用 `start_msys_pg.bat`
- 未验证就把 Jev 装进 Odoo 生产库 —— untrusted PL/Python 风险叠加 PG 18 未验证
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

## 6. 待办

- [ ] 安装 `mingw-w64-x86_64-python`，确认 `libpython3.14.dll` 可解析
- [ ] 在测试库验证 `CREATE EXTENSION plpython3u`
- [ ] 在测试库验证 `CREATE EXTENSION jev CASCADE` 于 PG 18.4 是否可用
- [ ] 若 PG 18 不可用，决定采用 §4.2 双实例还是等待 Jev 支持 18
- [ ] 更新旧部署指南：pgvector 实际为 **0.8.6**，文档写的 0.8.2 已过时
- [ ] 更新旧部署指南中的源码路径：AGE 现位于 `d:\odoochain\age-source`，非 `d:\dev\lawgraph\age-source`
- [ ] 评估 PG 18.4 + Odoo 20.1 这一未验证组合的回归范围

---

## 7. 参考

- `d:\odoochain\age-source\BUILD_WINDOWS.md` — AGE 1.8.0 Windows/MinGW 完整编译指南
- `d:\odoochain\age-source\PostgreSQL-AGE-pgvector安装部署指南.md` — 服务管理、用户创建、故障排查（**部分内容已过时**，见 §6）
- `d:\dev\pg-jev\README.md` — Jev 安装、函数、GUC 与注意事项

*本文档所有"实测"结论均来自 2026-10-07 在本机执行的命令输出。*
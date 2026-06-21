# PostgreSQL 数据备份迁移踩坑记录

> **日期**: 2026-06-21  
> **场景**: 将 baraka 数据库从 scoop PG (port 5432, MSVC) 迁移到 MSYS2 PG (port 5433, MinGW)  
> **PostgreSQL 版本**: 18.4  

---

## 坑 1: pg_dumpall 版本不匹配

### 现象
```
pg_dumpall: error: aborting because of server version mismatch
pg_dumpall: detail: server version: 18.4; pg_dumpall version: 17.0
```

### 原因
DBeaver 自带的 `pg_dumpall` 是 17.0 版本，而服务器是 18.4。pg_dumpall **严格要求版本匹配**，低版本无法操作高版本服务器。

### 解决方案
使用与服务器版本匹配的 pg_dumpall：
- scoop PG: `C:\Users\mirroam\scoop\apps\postgresql\current\bin\pg_dumpall.exe`
- MSYS2 PG: `C:\Users\mirroam\scoop\apps\msys2\current\mingw64\bin\pg_dumpall.exe`

---

## 坑 2: 连接用户名问题

### 现象
```
FATAL: role "mirroam" does not exist
```

### 原因
Windows 登录用户是 `mirroam`，但 PostgreSQL 中不存在同名角色。默认 psql 会用当前 Windows 用户名作为连接用户名。

### 解决方案
显式指定用户名：
```bash
pg_dump -p 5432 -h localhost -U odoo -d baraka ...
psql -p 5433 -d baraka -U odoo ...
```

---

## 坑 3: 数据库编码不匹配 (UTF-8 vs WIN1252)

### 现象
```
COPY failed for table "res_partner_industry": ERROR: character with byte sequence 
0xe5 0x86 0x9c in encoding "UTF8" has no equivalent in encoding "WIN1252"
```

### 原因
源数据库 (5432) 使用 UTF-8 编码，包含中文数据。目标数据库 (5433) 创建时使用了默认的 WIN1252 编码，无法存储 UTF-8 中文字符。

### 解决方案
重建数据库时指定 UTF-8 编码：
```sql
CREATE DATABASE baraka OWNER odoo 
  ENCODING 'UTF8' 
  LC_COLLATE 'C' 
  LC_CTYPE 'C' 
  TEMPLATE template0;
```

> **注意**: Windows 上不能使用 `en_US.UTF-8` locale，要用 `C`。

---

## 坑 4: PowerShell 中 bash 命令解析错误

### 现象
```
ParserError: Unexpected token '-c' in expression or statement
```

### 原因
PowerShell 将 `"C:\path\bash.exe" -c "command"` 中的 `-c` 解析为 PowerShell 操作符，而不是传递给 bash 的参数。

### 解决方案
将 bash 命令写入 `.bat` 文件，通过 `cmd /c` 执行：
```bat
@echo off
"C:\Users\mirroam\scoop\apps\msys2\current\usr\bin\bash.exe" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql ..."
```

---

## 坑 5: psql 中 `<->` 运算符被 PowerShell 截获

### 现象
```
The '<' operator is reserved for future use.
```

### 原因
pgvector 的距离运算符 `<->` 中的 `<` 和 `>` 被 PowerShell 解析为重定向操作符。

### 解决方案
将 SQL 写入 `.sql` 文件，用 `-f` 参数执行：
```bash
psql -p 5433 -d baraka -f query.sql
```

---

## 坑 6: psql 嵌套引号转义地狱

### 现象
Cypher 查询需要 `$$...$$` dollar quoting，嵌套在 bash -c 的双引号和 psql -c 的双引号中，转义极其复杂。

### 解决方案
所有复杂 SQL 都写入 `.sql` 文件执行，避免命令行转义：
```sql
-- test_cypher.sql
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT * FROM cypher('test_graph', $$MATCH (n) RETURN n$$) AS (v agtype);
```

---

## 坑 7: pg_restore 与 psql 恢复差异

### 现象
`pg_restore` (custom format) 恢复时出现大量错误（序列不存在、编码不匹配），而 `psql` (SQL format) 恢复成功。

### 原因
- `pg_restore` 对 schema 依赖更严格，序列必须先于表创建
- `pg_restore` 的 COPY 命令对编码检查更严格
- SQL 格式 dump 包含完整的 DDL + DML，自包含性更好

### 建议
跨编码/跨平台迁移优先使用 SQL 格式 dump：
```bash
pg_dump -p 5432 -d baraka --no-owner --no-privileges --file=dump.sql
psql -p 5433 -d baraka -f dump.sql
```

---

## 坑 8: 表所有权不一致

### 现象
恢复后所有表的 owner 是 `mirroam`（执行恢复的用户），而不是期望的 `odoo`。

### 解决方案
批量修改表所有权：
```sql
ALTER DATABASE baraka OWNER TO odoo;
ALTER SCHEMA public OWNER TO odoo;

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO odoo';
  END LOOP;
END $$;
```

---

## 坑 9: Git bash vs MSYS2 bash 混用

### 现象
部分脚本用 `C:\Program Files\Git\bin\bash.exe`，部分用 MSYS2 bash，导致找不到正确的 PG 工具。

### 原因
- Git bash 的 PATH 不包含 `/mingw64/bin`，找不到 `pg_config`、`psql` 等
- MSYS2 bash 的 PATH 包含完整的 MinGW64 工具链

### 建议
涉及 PostgreSQL 操作的脚本统一使用 MSYS2 bash：
```bat
"C:\Users\mirroam\scoop\apps\msys2\current\usr\bin\bash.exe" -c "..."
```

---

## 实际迁移步骤

以下是本次迁移的完整操作步骤，可直接复用。

### 环境信息

| 项目 | 值 |
|------|-----|
| 源数据库 | scoop PG 18.4 (MSVC), port 5432 |
| 目标数据库 | MSYS2 MinGW PG 18.4, port 5433 |
| 数据库名 | baraka |
| 数据库用户 | odoo |
| 数据量 | 530 表, ~31,000 行 |

### Step 1: 从 5432 导出 SQL dump

```bat
@echo off
"C:\Users\mirroam\scoop\apps\postgresql\current\bin\pg_dump.exe" -p 5432 -h localhost -U odoo -d baraka --encoding=UTF-8 --no-owner --no-privileges --file=D:\mydata\odoomolt\dump-baraka-5432.sql
```

> 用 scoop PG 自带的 pg_dump（版本匹配），指定 `-U odoo` 避免用户名问题。

### Step 2: 在 5433 创建数据库（UTF-8 编码）

```bat
@echo off
"C:\Users\mirroam\scoop\apps\msys2\current\usr\bin\bash.exe" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d postgres -c \"CREATE DATABASE baraka OWNER odoo ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;\""
```

> **关键**: 必须用 `LC_COLLATE 'C'`，Windows 不支持 `en_US.UTF-8`。

### Step 3: 启用扩展

```bat
psql -p 5433 -d baraka -c "CREATE EXTENSION IF NOT EXISTS age;"
psql -p 5433 -d baraka -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Step 4: 导入数据

```bat
@echo off
"C:\Users\mirroam\scoop\apps\msys2\current\usr\bin\bash.exe" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d baraka -f D:\mydata\odoomolt\dump-baraka-5432.sql"
```

> 用 SQL 格式导入（不要用 pg_restore，跨编码场景更可靠）。

### Step 5: 修复表所有权

```bat
@echo off
"C:\Users\mirroam\scoop\apps\msys2\current\usr\bin\bash.exe" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d baraka -f D:\dev\lawgraph\age-source\fix_owner.sql"
```

fix_owner.sql 内容：
```sql
ALTER DATABASE baraka OWNER TO odoo;
ALTER SCHEMA public OWNER TO odoo;

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO odoo';
  END LOOP;
END $$;
```

### Step 6: 数据验证

```sql
-- 对比关键表行数
SELECT 'res_partner' AS tbl, count(*) FROM res_partner
UNION ALL SELECT 'mail_message', count(*) FROM mail_message
UNION ALL SELECT 'ir_model_data', count(*) FROM ir_model_data
UNION ALL SELECT 'ir_attachment', count(*) FROM ir_attachment
UNION ALL SELECT 'res_users', count(*) FROM res_users
ORDER BY 1;
```

### 验证结果

| 指标 | 5432 (源) | 5433 (目标) | 状态 |
|------|-----------|-------------|------|
| 表数量 | 530 | 530 | ✅ |
| res_partner | 7 | 7 | ✅ |
| mail_message | 513 | 513 | ✅ |
| ir_attachment | 562 | 562 | ✅ |
| res_users | 4 | 4 | ✅ |
| ir_model_data | 22,331 | 22,382 | ⚠️ +51 (扩展元数据) |

### 一键迁移脚本

将以上步骤整合为 `migrate_baraka.bat`：

```bat
@echo off
setlocal

set PSQL_SCOOP=C:\Users\mirroam\scoop\apps\postgresql\current\bin
set PSQL_MSYS=C:\Users\mirroam\scoop\apps\msys2\current\usr\bin
set BASH=%PSQL_MSYS%\bash.exe
set DUMP_FILE=D:\mydata\odoomolt\dump-baraka-5432.sql
set FIX_SQL=D:\dev\lawgraph\age-source\fix_owner.sql

echo [1/5] Dump from port 5432...
"%PSQL_SCOOP%\pg_dump.exe" -p 5432 -h localhost -U odoo -d baraka --encoding=UTF-8 --no-owner --no-privileges --file=%DUMP_FILE%
if errorlevel 1 (echo FAIL & exit /b 1)

echo [2/5] Recreate database with UTF-8...
"%BASH%" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d postgres -c \"DROP DATABASE IF EXISTS baraka;\" && psql -p 5433 -d postgres -c \"CREATE DATABASE baraka OWNER odoo ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;\""
if errorlevel 1 (echo FAIL & exit /b 1)

echo [3/5] Enable extensions...
"%BASH%" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d baraka -c \"CREATE EXTENSION IF NOT EXISTS age;\" && psql -p 5433 -d baraka -c \"CREATE EXTENSION IF NOT EXISTS vector;\""

echo [4/5] Restore data...
"%BASH%" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d baraka -f %DUMP_FILE%"
if errorlevel 1 (echo FAIL & exit /b 1)

echo [5/5] Fix ownership...
"%BASH%" -c "export PATH=/mingw64/bin:/usr/bin:$PATH && psql -p 5433 -d baraka -f %FIX_SQL%"

echo === Migration complete ===
```

---

## 快速参考

| 操作 | 正确命令 |
|------|----------|
| 从 5432 导出 | `pg_dump -p 5432 -U odoo -d baraka --no-owner --file=dump.sql` |
| 导入到 5433 | `psql -p 5433 -d baraka -f dump.sql` |
| 修改表所有权 | 见 fix_owner.sql |
| 在 PowerShell 中运行 bash | 写入 .bat 文件，用 `cmd /c` 执行 |
| pgvector 距离查询 | 写入 .sql 文件，用 `-f` 执行 |

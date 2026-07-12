# CLAUDE.md

本文件给 Claude Code 和协作开发者提供本仓库的快速上手指南。

## 项目概览

- **Odoo 19.0** 服务端 + 一系列自定义/OCA 第三方 addons
- 仓库分支：`19.0-chain`（基于上游 19.0，叠加 chain/lawpad 定制）
- 主要 PR 目标分支：`18.0`

## 开发环境

**使用 `uv` 管理 Python 环境**，不要用 micromamba/conda/虚拟环境工具混合。
项目根目录已有 `pyproject.toml` + `uv.lock`，复现环境一条命令：

```bash
uv sync
```

会在 `D:\odoochain\odoo19\.venv` 下创建 venv 并按 `uv.lock` 锁定的版本安装全部依赖（走阿里云镜像，在 pyproject.toml 里已配）。

### Python 版本约束

`requires-python = ">=3.10,<3.14"` — **不要拿掉上限**。

原因：psycopg2 2.9.x 在 Windows 上目前没有 Python 3.14 的预编译 wheel，
让 uv 默认挑 3.14 会导致 `_psycopg` DLL 加载失败。
实测稳定版本：**Python 3.12.13**。

### Windows 必需的额外依赖

`pywin32` 已加入 `pyproject.toml` 主依赖。
Odoo 19 的 `odoo/tools/osutil.py` 在 Windows 上无条件 `import win32service`，
不装会导致 `odoo-bin` 启动时报 `ModuleNotFoundError: No module named 'win32service'`。

## 启动 odoo-bin

**用 venv 的 python 直接调，不要用 `uv run`**：

```bash
.venv/Scripts/python.exe odoo-bin -c odoo.conf
```

为什么不用 `uv run`：每次调用都会触发 `Building odoo19`（重打包整个 odoo 源码树到 editable install），
在本仓库规模下大约 7 分钟，而 `.venv/Scripts/python.exe` 直接调启动只要十几秒。

### 配置文件 `odoo.conf` 要点

- `db_name = forjoy`，`db_user = odoo`，密码 `odoo`，本机 PostgreSQL
  （`db_port = 5433`，不是默认 5432）
- `list_db = True` — 数据库不存在时访问任意页面会触发 db manager
- `addons_path` 链了 5 个外部目录（位置可能因机器而异，按需调整）：
  - `D:\odoochain\addons19\enterprise_addons`（含 `web_studio` 等 Enterprise 模块，多为 uninstalled）
  - `D:\odoochain\addons19\oca-knowledge`
  - `D:\odoochain\addons19\oca-ai`
  - `D:\odoochain\addons19\lawpad-social-im`
  - `D:\odoochain\addons19\odoo-lawpad`
- GeoIP 数据：`D:\odoochain\addons19\adata\GeoIP\GeoLite2-{Country,City}.mmdb`
- `http_interface =` 字段为空 → Odoo 默认绑定 0.0.0.0（19.0 起会给 warning，
  20.0 起会默认改为 127.0.0.1）。明确写一下避免歧义。

## 启动日志里的"伪"告警（可忽略）

### `addons path is not a directory: __editable__.odoo19-0.1.0.finder.__path_hook__`

启动时一定会看到这条 WARNING，**不要试图去"修"它**。

原因：`uv sync` 把本项目（`odoo19`）作为 editable install 装进 venv（PEP 660 机制）。
setuptools 为 editable 包注入了一个 `__editable__.<pkg>-<ver>.finder.__path_hook__`
字符串到 `odoo.addons` 这个命名空间包的 `__path__` 里 —— 它**长得像路径但其实是个
导入钩子标识**，不是文件系统路径。

Odoo 启动时遍历 addons 路径并对每一项调 `os.path.isdir()`，
这个钩子字符串当然不是目录，于是打一条 WARNING 然后跳过。功能完全正常。

日志中你会看到 addons path 长这样：

```
addons paths: _NamespacePath([
  'D:\\odoochain\\odoo19\\odoo\\addons',
  'D:\\odoochain\\odoo19\\odoo\\addons',     # 来自 odoo 命名空间包
  'D:\\odoochain\\odoo19\\odoo\\addons',     # editable install 再注册一次
  '__editable__.odoo19-0.1.0.finder.__path_hook__',   # ← PEP 660 钩子
  'C:\\Users\\mirroam\\AppData\\Local\\OpenERP S.A.\\Odoo\\addons\\19.0',  # Odoo 默认用户目录
  'd:\\odoochain\\odoo19\\odoo\\addons',     # 大小写不同但同一目录
  'd:\\odoochain\\odoo19\\addons',           # odoo.conf 配的
  'd:\\addons19\\oca-knowledge',
  'd:\\addons19\\oca-ai',
  'd:\\addons19\\lawpad-social-im',
  'd:\\addons19\\odoo-lawpad',
])
```

重复条目和大小写差异都是正常的（Windows 文件系统不区分大小写，Odoo 内部会去重）。
不要为了"看起来干净"去 `odoo.conf` 里删 `odoo\addons` 那一项 —— 删了反而可能让自定义
路径的优先级被打乱。

## 已知不兼容 Odoo 19 的 addon

以下模块的 `__manifest__.py` 仍是 18.0.x 版本号，启动时会被自动标记为
`installable=False`。如需在 19 上启用，需要改 manifest 版本号并修复 API 差异：

- `ai_oca_bridge_chatter`
- `ai_oca_bridge_extra_parameters`
- `lawpad_chroma`
- `lawpad_comfyui`
- `lawpad_fal_ai`
- `lawpad_replicate`
- `lawpad_social_dingding`
- `lawpad_social_feishu`
- `lawpad_social_wechat`
- `lawpad_web_widgit`

## 常用命令

```bash
# 初次/重建环境
uv sync

# 增删依赖（会自动更新 uv.lock）
uv add <pkg>
uv remove <pkg>

# 启动服务器
.venv/Scripts/python.exe odoo-bin -c odoo.conf

# 仅初始化某个数据库的某个模块
.venv/Scripts/python.exe odoo-bin -c odoo.conf -d <dbname> -i <module> --stop-after-init

# 升级模块
.venv/Scripts/python.exe odoo-bin -c odoo.conf -d <dbname> -u <module> --stop-after-init

# 查看依赖列表
uv pip list
```

## 不要做的事

- ❌ 不要用 `pip install` 往 `.venv` 里直接装包 —— 走 `uv add`，保持 lock 一致
- ❌ 不要再用 micromamba 的 odoo 环境 —— 已废弃
- ❌ 不要改 `requirements.txt`（Odoo 上游文件）作为依赖源，本项目以 `pyproject.toml` 为准
- ❌ 不要去掉 `requires-python` 的 `<3.14` 上限，除非 psycopg2 出了 3.14 的 Windows wheel

## Odoo 开发规则

> 摘选自 odoo-ai（`D:\odoochain\odoo-ai`）的 RULES.md，本地化到本仓库（Odoo **19.0**）。
> 写任何 addon 代码前先过一遍这几条。

### R1 — 版本检测（写代码前必做）

动手写 Odoo 代码前：

1. 读目标模块的 `__manifest__.py`，确认版本号（如 `19.0.1.0` → Odoo 19）
2. 看 `license` 判断 edition：`OEEL-1` → Enterprise；`LGPL-3` / `AGPL-3` / `OPL-1` → Community
3. 没有 `__manifest__.py` → 先问，不要猜

**永远不假设版本。不要给 19 的项目写 18 的代码。** 本仓库已知有一批 manifest 还停在 18.0.x
被自动标记 `installable=False`（见上文"已知不兼容"列表），改这些模块时先 bump 版本号并修 API 差异。

### R4 — 新模型必须有 ACL

每个新 `models.Model` 必须：

- 在 `security/ir.model.access.csv` 有对应条目
- 至少给 `base.group_user` 一个 `read` 权限

否则模块装不上，或者用户看不到记录。**commit 前自查：有新模型吗？有 ACL 吗？**

### R5 — 改视图 XML 时写 pre-migrate

**触发条件**：同一 commit 里 `__manifest__.py` 版本号 bump + 修改了视图 `.xml`。

**动作**：建 `migrations/<version>/pre-migrate.py`：

```python
# -*- coding: utf-8 -*-
def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE name IN ('被改视图的 name')
          AND model = '对应的模型'
    """)
```

`name` 对应 XML 里 `<record model="ir.ui.view">` 的 `<field name="name">`。
不写这个脚本，`-u` 升级时旧视图定义残留会报错。

### R6 — 先搜再写（不重复造轮子）

开发新功能前按顺序找现成实现（**Enterprise First**）：

1. Enterprise 源码：`D:\odoochain\addons19\enterprise_addons`（含 web_studio 等）
2. Community：本仓库 `odoo\addons`
3. OCA：本仓库已链的 `oca-knowledge`、`oca-ai`，或 `https://github.com/OCA?q=<keyword>`
4. 都没有再从零写

Enterprise 有结果就是定论，不用再翻 Community。用 `codegraph_search` / `Grep` 锁定后再 Read 具体文件。

### R7 — 代码标准

- **Python**：PEP8、SOLID、DRY。用 `super()`。不用废弃装饰器（`@api.multi`）。
- **ORM**：`create()` 用 `@api.model_create_multi`。
- **翻译**：`_("文本")`，**不要** `_(f"文本 {var}")`，要插值用 `_("%s 文本") % var`。
- **compute 循环**：一律 `for record in self:`，循环体内不直接用 `self.field`。
- **多公司**：`self.env['ir.sequence'].with_company(company).next_by_code(...)`。
- **XML 隐藏**：`invisible="条件"`，不用旧的 `attrs="{'invisible': [...]}"`。
- **XML ID**：`ref=` 继承前先确认目标 ID 存在。

### R13 — 安全（所有代码无例外）

**SQL —— 永远参数化，不拼接：**
```python
# ❌ 绝不
cr.execute("SELECT id FROM res_partner WHERE name = '%s'" % name)
# ✅ 永远
cr.execute("SELECT id FROM res_partner WHERE name = %s", (name,))
```

**sudo() —— 最小范围，且必须校验归属：**
```python
record = self.env['sale.order'].sudo().browse(order_id)
if record.partner_id != self.env.user.partner_id:
    raise AccessError(_("Access denied"))
```

**XSS —— 用户数据一律 `t-out`，`t-raw` 只给系统 HTML：**
```xml
<span t-raw="record.description"/>   <!-- ❌ 用户数据绝不 -->
<span t-out="record.description"/>   <!-- ✅ 自动转义 -->
```

**Controller —— auth 显式声明：**
```python
@http.route('/api/data', type='json')                 # ❌ 没声明 auth
@http.route('/api/data', type='json', auth='user')    # ✅ 显式
```

**ACL —— 见 R4，新模型 commit 前必须有 `ir.model.access.csv` 条目。**

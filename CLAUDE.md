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

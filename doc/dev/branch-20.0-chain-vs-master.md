# 20.0-chain 分支分析与 OCB 定制层说明

> **快照基准**：`b8a876d0db32`（HEAD，2026-09-22 20:14 +0800）
> 对比参照：`odoo/master`（`044878f20812`，2026-09-21）、`odoo/20.0`（`fc24224ae2de`，2026-09-21）
> 所有数据均由 git 命令实测得出，非推测。随着上游推进，提交计数与文件数会变化，结论性判断（分支定位、定制层设计）长期有效。

---

## 1. 仓库与分支拓扑

### 1.1 远端一览

| 远端 | URL | 作用 |
|---|---|---|
| `odoo` | `git@github.com:odoo/odoo.git` | 上游官方 |
| `odoochain` | `git@github.com:odoochain/ocb.git` | OCB 镜像（**master 已废弃**） |
| `nbder` | `https://cnb.cool/nbder/odoochain` | 当前分支的跟踪远端 |
| `origin` | `git@github.com:odoochain/chain19.git` | 19.x 系列 |
| `Viindoo` | `git@github.com:Viindoo/odoo.git` | 第三方参考 |

### 1.2 当前分支

- **分支名**：`20.0-chain`，跟踪 `nbder/20.0-chain`
- **HEAD**：`b8a876d0db32` `Merge remote-tracking branch 'nbder/20.0' into 20.0-chain`
- **版本号**：`20.0.0 FINAL`

```python
# odoo/release.py
version_info = (20, 0, 0, FINAL, 0, '')
```

### 1.3 血缘关系

```
odoo/20.0 (fc24224ae2de, 20.0.0 FINAL)
    │
    ├── c9f0f9fe5449  [IMP] OCB README
    ├── 75c4aa0e7966  Merge PR #1353 (acsone/20.0-packaging)
    │       ├── 3fd4308c7b40  [FIX] setup: support PEP 660 and setuptools >= 64
    │       └── a9e0936e17f4  [FIX] setup: fix building wheel
    └── b8a876d0db32  Merge nbder/20.0 into 20.0-chain   ← HEAD
```

**当前分支 = `odoo/20.0` 稳定发布线 + 一个极薄的 OCB 打包/标识补丁层。**

---

## 2. 与 `odoo/master` 的差异

### 2.1 本质区别：两条不同的发布线

| 项 | `20.0-chain` | `odoo/master` |
|---|---|---|
| 版本 | `20.0.0 **FINAL**` | `20.1.0 **ALPHA**` |
| 定位 | 已发布稳定版 | 下一版开发主干 |

分叉点 `b7326692b7e6`（2026-09-17，当时两边版本号同为 `19.5.0 alpha`）。此后：

- `odoo/master` 走了 **196** 个非合并提交
- `20.0-chain` 走了 **224** 个提交

### 2.2 文件差异量级

```
两点 diff (odoo/master HEAD):  391 files, +67939 / -41497
三点 diff (odoo/master...HEAD): 835 files, +41753 /  -7317
```

### 2.3 差异的主要构成（**不是功能分歧**）

**① 翻译文件（占本分支独有文件的 91%）**

本分支独有 117 个新文件，其中 **107 个是 `i18n/*.po`**。20.0 作为已发布版本带有完整多语言翻译，master 开发线尚未生成：

| 模块 | `20.0-chain` | `odoo/master` |
|---|---|---|
| `addons/mysubscription` | 82 文件 | 34 文件 |
| `addons/pos_sale_delivery` | 55 文件 | 7 文件 |

**② master 独有的重构与新模块**（尚未 backport 到 20.0）

- 新增 `pos_discount_self_order` 模块
- `pos_discount` 收据/打印链路重构（`receipt/pos_order_receipt.py`、`static/src/app/utils/printer/generate_printer_data.js`、`customer_display/customer_display.xml` 等在本分支不存在）
- `web`：`onWillUpdateProps` → Owl3 替代方案
- `spreadsheet`：`odoo_link` 目录结构重排（4 个文件 rename，相似度 90–100%）
- `sale`：销售仪表盘动态重载

**③ 相同修复的不同提交（backport 关系，非分歧）**

两边有大量同名提交，属 master → 20.0 的回溯，例如：

- `[FIX] pos_sale: allow removing the quotation partner filter`
- `[FIX] mrp: make draft kanban progress segments visible`
- `[IMP] l10n_ro_edi_stock: support dropship operations`
- `[FIX] spreadsheet: remove internal feature from public spreadsheets`
- `[FIX] l10n_cl: do not post demo moves of non chilean partners`

### 2.4 本分支独有的非翻译文件（仅 10 个）

```
addons/phone_validation/models/mail_activity.py
addons/resource/static/src/scss/resource_list.scss
addons/sale_loyalty_delivery/controllers/__init__.py
addons/sale_loyalty_delivery/controllers/payment.py
addons/sale_loyalty_delivery/models/payment_provider.py
addons/stock_dropshipping/models/account_move_line.py
addons/web/controllers/main.py
odoo/tools/cache/__init__.py
pyproject.toml          ← OCB 定制层
setup/pep517_odoo.py    ← OCB 定制层
```

---

## 3. OCB 定制层详解（相对 `odoo/20.0` 的全部改动）

仅 **3 个提交、5 个文件、+78/-35**，零业务代码：

```
 MANIFEST.in          |  3 +++
 README.md            | 38 ++++--------------------------
 pyproject.toml       |  4 ++++
 setup.py             |  2 +-
 setup/pep517_odoo.py | 66 ++++++++++++++++++++++++++++++++++++++
```

核心作用：**把 Odoo 从"只能 git clone 运行"变成"可用标准 Python 打包工具安装的包"**，并声明分支身份。

---

### 3.1 `c9f0f9fe5449` — [IMP] OCB README

- **作者**：Pedro M. Baeza `<pedro.baeza@tecnativa.com>`（Tecnativa，OCA 核心成员）
- **时间**：2026-09-17 18:52 +0200
- **改动**：README 从 38 行缩为 4 行

```markdown
Odoo Community Backports (OCB)
------------------------------

Please see what is OCB, its purpose and a FAQ at the [Wiki](https://github.com/OCA/OCB/wiki).

For the original Odoo README, please go to https://github.com/odoo/odoo/blob/20.0/README.md
```

**意义**：身份声明，防止与 `odoo/odoo` 官方仓库混淆。删除上游的 runbot badge、营销链接和安装指引——这些指向 odoo.com 的资源对 OCB 不适用（runbot 不测 OCB）。这是定制层中**唯一与打包无关的改动**，纯象征意义。

---

### 3.2 `3fd4308c7b40` — [FIX] setup: support PEP 660 and setuptools >= 64

- **作者**：Stéphane Bidoul `<stephane.bidoul@acsone.eu>`（ACSONE，OCA 技术负责人，`setuptools-odoo` 作者）
- **时间**：2026-09-19 12:54 +0200
- **新增**：`pyproject.toml`、`setup/pep517_odoo.py`；修改 `MANIFEST.in`

#### 要解决的结构性矛盾

Odoo 源码布局存在固有冲突：

1. 社区模块位于仓库根 `addons/`（约 900 个）
2. 运行时 Python 需从 `odoo.addons.*` 命名空间导入
3. 仓库中 `odoo/addons/` **仅含 16 个条目**（`base` + `test_*` 系列 + `.gitkeep`），**不含社区模块**

```
$ git ls-tree HEAD:odoo/addons
.gitkeep  base  test_assetsbundle  test_base  test_data_module
test_data_module_install  test_http  test_inherit  test_inherit_depends
test_inherits_depends  test_l10n  test_lint  test_main_flows
test_tests  test_translation  test_uninstall  test_web
```

Odoo 原先依赖 `setup.py` 的隐式行为 + 运行时 `addons_path` 配置兜底。但 **setuptools ≥ 64 重写了 editable install 实现**（改用 `__editable___*_finder.py` 动态查找器），不再兼容这种"运行时拼装命名空间"方式，`pip install -e .` 会产出无法导入社区模块的环境。

#### 解决方案：自定义 PEP 517 构建后端

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=41"]
build-backend = "pep517_odoo"
backend-path = ["setup"]
```

`setup/pep517_odoo.py` 包装 setuptools 原生后端，做两件事：

**① 构建期临时符号链接**

`build_sdist` / `build_wheel` 前把 `addons/*` 全部 symlink 进 `odoo/addons/`，让 setuptools 包发现机制可见；构建完在 `finally` 中逐个 `unlink` 还原，不污染工作树：

```python
@contextlib.contextmanager
def _symlink_addons():
    symlinks = []
    try:
        target_addons_path = Path("addons")
        addons_path = Path("odoo", "addons")
        link_target = Path("..", "..", "addons")
        if target_addons_path.is_dir():
            for target_addon_path in target_addons_path.iterdir():
                if not target_addon_path.is_dir():
                    continue
                addon_path = addons_path / target_addon_path.name
                if not addon_path.is_symlink():
                    addon_path.symlink_to(
                        link_target / target_addon_path.name, target_is_directory=True
                    )
                    symlinks.append(addon_path)
        yield
    finally:
        for symlink in symlinks:
            symlink.unlink()
```

**② 强制 editable 使用 `compat` 模式**

```python
config_settings["editable-mode"] = "compat"
```

`compat` 模式只安装一个 `.pth` 文件，把仓库根加入 `PYTHONPATH`，行为等同旧版 `setup.py develop`。源码注释说明了为何不用另两种模式：

- `default` 模式：与 flat layout 下 Odoo 的 addons 发现机制不兼容
- `strict` 模式：要求文件清单固定，而 Odoo 开发中频繁新增文件会令其立即失效

#### 意义

让 `pip install .`、`pip install -e .`、`python -m build` 对 Odoo 可用。这是 OCA 生态的刚性需求——OCA 用 pip/wheel 管理数百个仓库的模块依赖；上游 Odoo 自己用 deb/rpm/nightly tarball 分发，没有这个痛点，因此**上游 `odoo/20.0` 与 `odoo/master` 均不含这两个文件**（已实测确认）。

---

### 3.3 `a9e0936e17f4` — [FIX] setup: fix building wheel

- **作者**：Vincent Hatakeyama `<vincent.hatakeyama@xcg-consulting.fr>`（XCG Consulting）
- **时间**：2026-09-19 12:54 +0200（同 PR #1353 内）

#### 问题

3.2 的 symlink 方案有副作用：`find_namespace_packages()` 无参调用会扫描整个仓库，于是根目录 `addons/` 被当成顶层包收进 wheel。后果是 addons 内容被打包两次（一次作为 `addons.*`，一次经 symlink 作为 `odoo.addons.*`），wheel 体积翻倍，且在 site-packages 中污染出名为 `addons` 的顶层包，与其他 Python 库撞名。

#### 修法：双重保险

```python
# setup.py
packages=find_namespace_packages(include=("odoo", "odoo.*")),
```

```
# MANIFEST.in
include requirements.txt
include LICENSE
include README.md
include pyproject.toml
include setup/pep517_odoo.py
graft odoo
prune addons          ← 数据文件层面排除根 addons/
recursive-exclude * *.py[co]
recursive-exclude .git *
```

包发现层面收窄范围，数据文件层面显式 prune。

---

### 3.4 定制层整体评价

| 维度 | 结论 |
|---|---|
| 改动面 | 5 文件 / +78 -35，**零业务代码** |
| 性质 | 纯基础设施补丁（packaging + 身份标识） |
| 冲突风险 | 极低。4/5 文件为构建配置，上游几乎不动；`setup.py` 仅改 1 行 |
| 可持续性 | 良好。从 `odoo/20.0` 合并新 backport 时，该层基本不被触碰 |

设计思路克制且有效：**不碰任何 addon 代码，只在构建边界做适配**，维护成本接近零。这解释了它能在 Odoo 的庞大历史中作为稳定"薄壳"长期存在。

---

## 4. 实践影响与维护注意事项

### 4.1 开发环境

- 在 `20.0-chain` 上可直接 `pip install -e .` 建立开发环境
- 直接用上游 `odoo/20.0` 则**不行**：setuptools ≥ 64 下会装出无法导入社区模块的坏环境

### 4.2 合并上游时的保护点

从 `odoo/20.0` 或 `nbder/20.0` 合并后，确认以下 5 处未被覆盖：

1. `setup.py` 中 `find_namespace_packages(include=("odoo", "odoo.*"))` ——**最易被上游覆盖的一行**
2. `MANIFEST.in` 中 `include pyproject.toml` / `include setup/pep517_odoo.py` / `prune addons`
3. `pyproject.toml` 存在且 `build-backend = "pep517_odoo"`
4. `setup/pep517_odoo.py` 存在
5. `README.md` 为 OCB 版本

快速校验：

```powershell
git diff --stat odoo/20.0...HEAD
# 预期：仅 MANIFEST.in / README.md / pyproject.toml / setup.py / setup/pep517_odoo.py 共 5 个文件
```

若输出包含其他文件，说明 chain 分支已引入额外改动，需单独评估。

### 4.3 已知陷阱

**① `odoochain/master` 已废弃**

停在 `7a03e36365db`（2024-10-07，版本 `18.1.0 alpha`），与当前分支相距 **32083 个提交**，无可比性。谈"master"时须明确指 `odoo/master` 还是 `odoochain/master`。

**② GitButler 残留分支**

| 分支 | 指向 | 说明 |
|---|---|---|
| `gitbutler/target` | `9c9b65c2118e`（2024-09-25） | 陈旧，与 20.0 工作无关 |
| `gitbutler/workspace` | `3d2c4ff3516b`（2026-07-12，merge odoo/19.0） | 19.0 时代遗留 |

在 20.0 线上作业时勿误用这两个引用作为基线。

**③ `prune addons` 不影响运行时**

该规则只作用于 sdist/wheel 打包清单，源码树中的 `addons/` 仍由运行时 `addons_path` 正常加载。

---

## 5. 复现本分析的命令

```powershell
# 分支定位
git status -sb
git log -1 --format="%ci %h %s" HEAD
git show HEAD:odoo/release.py | Select-String "version_info ="

# 与各基线的落差（behind / ahead）
git rev-list --left-right --count odoo/master...HEAD
git rev-list --left-right --count odoo/20.0...HEAD

# 定制层全貌
git diff --stat odoo/20.0...HEAD
git log --oneline --graph HEAD --not odoo/20.0

# 与 master 的差异分布（按模块）
git diff --numstat odoo/master HEAD |
  ForEach-Object { ($_ -split "`t")[2] } |
  ForEach-Object { ($_ -split "/")[0..1] -join "/" } |
  Group-Object | Sort-Object Count -Descending | Select-Object -First 25 Count,Name

# 区分翻译文件与真实代码差异
$a = git diff --name-only --diff-filter=A odoo/master HEAD
($a | Where-Object { $_ -match '/i18n/' }).Count   # 翻译
$a | Where-Object { $_ -notmatch '/i18n/' }        # 真实新增
```

> PowerShell 注意：`git` 子命令中含 `$?`、`2>$null`、嵌套引号时，内联 `-Command` 易触发解析错误；建议写入 `.ps1` 临时脚本后以 `-File` 执行。

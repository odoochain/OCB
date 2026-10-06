# PR #67 与 PR #68 的作用与分工

> 快照日期：2026-10-06
> 仓库：`odoochain/OCB`（https://github.com/odoochain/OCB）
> 状态：两个 PR 均为 **Draft**，静态校验通过，构建与数据库回归**未执行**

---

## 0. 一句话区分

| PR | 一句话作用 | 在自主路线中的地位 |
|---|---|---|
| **#67** | 把 OCB 的精华层移植到 **`chain`（= 上游 master 主线）**，让主线从"纯上游镜像"变成"有自主能力的开发线" | **关键路径**，主线差异化的唯一来源 |
| **#68** | 把 **`20.0` 稳定线**同步到官方 `odoo/20.0`，同时保住 OCB 定制层 | **参考基线**，非关键路径 |

两者不冲突、不互为前提：一个建能力，一个保基线。

---

## 1. 前置概念：两条线不是一回事

这是理解两个 PR 的前提。仓库里存在两条互不等价的开发线：

| 分支 | 实际内容 | 版本号 | 定位 |
|---|---|---|---|
| `chain` | `odoo/master` 的纯镜像 | `20.1.0 ALPHA` | **开发主干**，跟踪上游 master |
| `20.0` | `OCA/OCB` 定制层 + 官方 20.0 | `20.0.0 FINAL` | **稳定基线**，面向生产 |

`chain` 与 `odoo/20.0` 在 `b7326692b7e6`（2026-09-17）分叉后从未同步。**把 `20.0` 的东西往 `chain` 合，或者反过来，都是跨发布线操作**，必须逐次评估。

---

## 2. PR #67：OCB 精华层移植到 master 主线

### 基本信息

| 项 | 值 |
|---|---|
| 链接 | https://github.com/odoochain/OCB/pull/67 |
| 目标分支 | `chain` @ `0bf91508de2a`（≡ `odoo/master`） |
| 源分支 | `chain-ocb-backport` @ `65300ca83347` |
| 提交数 | **4**（全部为 cherry-pick，非 squash） |
| 改动量 | 35 文件，`+108 / −65` |
| 合并状态 | `MERGEABLE` |

### 它解决什么问题

在 PR #67 之前，`chain` 与 `odoo/master` **逐提交完全相同**（`git rev-list --count` 为 `0 / 0`）——即零自主改动。这条"开发主干"实际上没有任何自研内容，无法承载任何自主开发路线。

PR #67 给 `chain` 装上第一层自主能力：**OCB 的打包基础设施 + 模块安装策略**。

### 来源映射

四个提交全部来自 `OCA/OCB:20.0`，用 `cherry-pick -x` 移植，保留原作者、作者日期与来源哈希：

| 本 PR 提交 | OCB 来源 | 作用 |
|---|---|---|
| `cab43ee2121c` | `c9f0f9fe5449` | README 身份标识 |
| `5ad917d39380` | `3fd4308c7b40` | PEP 517/660 打包支持 |
| `47b278f0ad60` | `a9e0936e17f4` | wheel 包发现修复 |
| `65300ca83347` | `ecba93571a15` | 30 个模块 `auto_install` 策略 |

对应 OCB 侧两个 PR 记录：`75c4aa0e7966`（OCA/OCB#1353 打包）、`ea0a6f3e857a`（OCA/OCB#1358 自动安装）。**这两个是 OCB 自己的合并记录，无内容，未移植。**

### 三部分内容

#### 2.1 打包基础设施（5 文件中的 4 个）

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | 声明 `build-backend = "pep517_odoo"`，让 pip/build 走自定义后端 |
| `setup/pep517_odoo.py` | 新增 66 行后端：构建期把 `addons/*` 符号链接进 `odoo/addons/`，`finally` 中清理；强制 editable 用 `compat` 模式 |
| `setup.py` | `find_namespace_packages(include=("odoo", "odoo.*"))`，收窄包发现范围 |
| `MANIFEST.in` | `include pyproject.toml` / `include setup/pep517_odoo.py` / `prune addons` |

**为什么上游没有这层**：Odoo 源码布局有固有冲突——社区模块在仓库根 `addons/`，运行时却要从 `odoo.addons.*` 导入。上游用 deb/rpm/nightly 分发，没有 pip 安装需求；setuptools ≥ 64 重写 editable 实现后，`pip install -e .` 会装出无法导入社区模块的环境。OCA 生态必须用 pip/wheel 管理数百仓库，所以 OCB 补了这层。

#### 2.2 身份标识

`README.md`：38 行 → 4 行，声明这是 OCB 分支并指向 OCA Wiki。

#### 2.3 模块安装策略（30 个 manifest）

**这是 PR #67 中唯一有业务语义的部分，也是长期维护成本的来源。**

按变更方向分三类：

| 方向 | 数量 | 含义 |
|---|---:|---|
| `True` → `False` | 16 | 真正关闭自动安装 |
| `[...]` → `False` | 2 | `account_peppol`、`l10n_fr_pdp` |
| `[...]` → `True` | 12 | 全部 `spreadsheet_dashboard_*` + `spreadsheet_account` |

合计：`False` 18 个 / `True` 12 个。

**关闭的（18）**：`account_edi_ubl_cii`、`account_peppol`、`account_qr_code_sepa`、`base_import_module`、`base_install_request`、`iap`、`iap_crm`、`l10n_fr_pdp`、`mail_bot`、`mail_plugin`、`mysubscription`、`partner_autocomplete`、`privacy_lookup`、`project_todo`、`sale_margin`、`sale_pdf_quote_builder`、`sms`、`web_unsplash`

**收紧的（12）**：`spreadsheet_account`、`spreadsheet_dashboard_{event_sale, hr_expense, hr_timesheet, im_livechat, pos_hr, pos_restaurant, sale, sale_timesheet, stock_account, website_sale, website_sale_slides}`

第三类容易误读：`auto_install: ['sale']` 原本是"任一依赖被依赖就装"，改成 `True` 后要求 `depends` 全部装齐才触发。**方向与 PR 意图一致（都是减少自动安装），但它改写的是 `chain` 上更精细的条件式写法**，属于粒度退化，需知晓。

### 冲突处理

唯一冲突：`addons/sale_margin/__manifest__.py`。

```
<<<<<<< HEAD
    "auto_install": False,
=======
    "auto_install": True,
    "assets": { ... labeled_field_short_labels.js ... },
>>>>>>> ecba93571a15
```

解决：**保留 OCB 的 `auto_install: False` + 接受上游新增的 `assets` 段**。未使用整文件 ours/theirs（那会丢掉 `assets`）。

### 已验证 / 未验证

**已通过**：4 个提交、作者与来源哈希保留；35 文件范围精确；30 个 `auto_install` 值与 OCB 一致且其余字段不变；658 个 manifest 可解析；32 个 Python 文件语法编译通过；`odoo/release.py` 未变（`20.1a1`）；`odoo-bin --version` 输出 `Odoo Server 20.1a1`。

**未执行**：wheel/sdist/editable 构建、PostgreSQL 安装与升级、`auto_install` 行为回归。**因此保持 Draft。**

---

## 3. PR #68：官方 20.0 稳定线同步

### 基本信息

| 项 | 值 |
|---|---|
| 链接 | https://github.com/odoochain/OCB/pull/68 |
| 目标分支 | `20.0` @ `ea0a6f3e857a`（= OCA/OCB 20.0 原样） |
| 源分支 | `sync/20.0-upstream-20261006` @ `9672931e5982` |
| 提交数 | 1 个真实合并提交（双父） |
| 带入上游 | **715** 个官方 20.0 提交 |
| 改动量 | 6,769 文件，`+877,266 / −303,948` |
| 合并状态 | `MERGEABLE` / `CLEAN` |

### 上游快照

`odoo/odoo:20.0` @ `22a96230cf06390979aa162b3b19e95e1b15a6e1`（2026-10-06，`[FIX] mail: order a message sent while the channel loads`）

**不含任何 master / 20.1 开发线内容。**

### 它解决什么问题

同步前 `OCA/OCB:20.0` 相对官方 `odoo:20.0` **落后 699 个提交**，同时保有 6 个 OCB 独有提交。这条线既没有上游修复，也不再是干净的官方基线。

PR #68 把它拉回同步，同时保住 OCB 定制层。

### 合并方式

沿用本仓库 19.0 线的既有惯例（`Merge remote-tracking branch 'odoo/19.0'`）：

```
9672931e5982  ea0a6f3e857a (OCB)  +  22a96230cf06 (上游)  →  Merge remote-tracking branch 'odoo/20.0' into 20.0
```

保留完整上游历史与作者署名。未 rebase、未 squash。

### 冲突处理

同样只有 `addons/sale_margin/__manifest__.py` 一处，原因与 PR #67 **完全相同**。

### 已验证 / 未验证

**已通过**：合并提交双父正确；与上游的差异**恰好是 35 个文件的 OCB 定制层**，无其他偏离；5 个打包/README 文件与 OCB 基线逐字节一致；30 个 `auto_install` 值完整保留；`release.py` = `20.0.0 FINAL`；657 个 manifest 解析通过；32 个 Python 文件编译通过；全树无冲突标记；`odoo-bin --version` 输出 `Odoo Server 20.0`。

**未执行**：PostgreSQL 新建库安装、现有库升级（715 个提交可能含 schema 与数据变更）、mail/web/account/stock/pos/sale 回归、前端资产构建、wheel/sdist/editable 构建。**因此保持 Draft。**

---

## 4. 两个 PR 的关系

### 为什么都要做

- #67 解决"**没有自主能力**"：主线与上游完全相同，无法承载自研。
- #68 解决"**稳定基线不可用**"：`20.0` 线落后 699 个提交，无法作为生产或参考基线。

### 冲突重复出现暴露的长期成本

`sale_margin/__manifest__.py` 在 **#67 和 #68 中以完全相同的原因冲突两次**。这不是巧合——`ecba93571a15` 改的就是 `auto_install` 字段，而上游后续提交（`296f6de41291` 引入 `assets`）也改同一个文件的相邻区域。

**推论**：只要 `chain` 保留这 30 个 manifest 改动，每次同步上游 master 都可能在该区域反复冲突。这是 PR #67 附带的**长期合并税**，需要在自主路线中显式应对（见 `development-route.md` §5）。

---

## 5. 已解决：分支命名冲突（2026-10-06）

```
本地 20.0        fc24224ae2de   已删除
odoochain/20.0   ea0a6f3e857a   OCB 20.0 线（PR #68 的目标分支）
```

删除前已验证本地 `20.0` 是官方 `odoo/20.0` 的祖先，**未丢失任何提交**。远端 `odoochain/20.0` 不受影响，PR #68 的基线无变化。

同时已为 `chain` 设置 upstream = `odoo/master`（现落后 62 个提交），裸 `git push` 会被 Git 拒绝，不会误推上游。

---

## 6. 20.0 线的角色：仅作参考

2026-10-06 决定：**`20.0` 稳定线仅作参考，不用于生产。** 这直接影响 PR #68 的门禁标准。

### 关键判断：两个 PR 的边际风险都很小

| PR | 与上游的差异面 | 风险来源 |
|---|---|---|
| #67 | 35 文件（vs `odoo/master`） | 仅这 35 文件 |
| #68 | 35 文件（vs `odoo/20.0`） | 仅这 35 文件 |

两个 PR 带入的其余部分（#67 的 62 个 master 提交、#68 的 715 个官方提交）**是 Odoo 自己已测试过的代码**。我们的边际贡献只有 35 个文件：

- 4 个打包文件 + 1 个 README：对运行时无影响
- 30 个 `__manifest__.py`：只改 `auto_install` 一个键

因此**门禁应按 35 行的差异面来定，而不是按 715/62 个提交的总量来定**。

### 门禁分级

| PR | 建议门禁 | 理由 |
|---|---|---|
| **#67** | 完整门禁：构建 + `auto_install` 行为回归 + 关键模块安装 | 主线，缺它就没有自主层 |
| **#68** | 轻量门禁：OCB 层完整保留 + 构建可用 + `sale_margin` 冒烟 | 参考线，上游代码由 Odoo 负责测试 |

**这是"仅作参考"决策的直接收益：省下的门禁预算全部投向 PR #67 和未来的 master 同步。**

若未来要把 `20.0` 升为生产基线，必须补齐完整门禁（尤其 715 个提交的数据库升级测试），届时本节需重新评估。

---

## 7. 相关文档

- 自主开发路线与上游同步策略：`development-route.md`
- 构建与数据库回归门禁方案：`test-gates.md`
- 20.0 线与 master 线的拓扑分析（早期笔记）：`branch-20.0-chain-vs-master.md`

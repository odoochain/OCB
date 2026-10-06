# 自主开发路线：以 master 为主线，吸纳 OCB 精华

> 制定日期：2026-10-06
> 适用范围：`d:/odoochain/odoochain`（远端 `odoochain/OCB`）
> 配套文档：`pr67-pr68-roles.md`

---

## 1. 北极星

> **以上游 `odoo/odoo` 的 `master` 为主线持续跟踪开发，吸收 OCA/OCB 中对我们有价值的精华，形成我们自己的自主开发路线。**

| 承诺 | 含义 | 衡量标准 |
|---|---|---|
| **主线跟踪 master** | 开发线永远建立在 master 之上，不 fork 停在旧版本 | `chain` 与 `odoo/master` 差距可查、可解释 |
| **吸纳精华** | 有选择地吸收，不全盘照搬也不全盘拒绝 | 每项都有来源哈希、作者署名、纳入理由 |
| **自主路线** | 我们的改动可识别、可审查、可回滚 | 自主层与上游差异恒定且可验证 |

---

## 2. 现状基线（2026-10-06 实测）

| 指标 | 值 |
|---|---|
| `chain` HEAD | `0bf91508de2a` |
| 官方 `master` HEAD | `a9be6c3ec8ac`（`[FIX] l10n_gcc_invoice: display product name on invoice`） |
| `chain` 落后 | **62** 个提交 |
| `chain` 领先 | **0** 个（PR #67 未合并） |
| `chain` 版本 | `20.1.0 ALPHA` |

**必须正视的信号**：本次会话期间（2026-10-06 单日）官方 master 至少推进两次（`9eda22d1e785` → `a9be6c3ec8ac`）。master 是活跃开发线，**同步节奏必须比 20.0 稳定线频繁得多**。

---

## 3. 三层架构

```
┌─────────────────────────────────────────────────────┐
│  L3  功能分支    feat/*   我们的新功能，一次一分支      │
├─────────────────────────────────────────────────────┤
│  L2  自主层      吸收的 OCB 精华 + 我们的基建（35 文件）│
├─────────────────────────────────────────────────────┤
│  L1  上游基线    odoo/master，零改动                  │
└─────────────────────────────────────────────────────┘
```

**铁律：L2 永远保持"薄"。** 某个改动若可以让上游自己拥有、或可放入 OCA 独立仓库，就不要放进 L2。

---

## 4. 分支模型

| 分支 | 定位 | 上游关系 |
|---|---|---|
| `chain` | **开发主干** = master + L2 | 合并 `odoo/master` |
| `20.0` | **参考基线** = 官方 20.0 + L2（**仅作参考，不用于生产**） | 合并 `odoo/20.0` |
| `feat/*` | 功能分支，从 `chain` 切出 | 合并回 `chain` |
| `sync/*` | 同步分支，合上游后开 PR | PR 合并后删除 |

### 已解决：upstream 与分支命名（2026-10-06）

- `chain` 已设置 upstream = `odoo/master`。`git status` 现在提示落后，裸 `git push` 会被 Git 拒绝（`push.default=simple` 下 upstream 名与分支名不匹配即报错），**不会误推上游 master**。推送请显式写 `git push odoochain chain:chain`。
- 本地 `20.0`（`fc24224ae2de`）已删除。删除前已验证它是官方 `odoo/20.0` 的祖先，**未丢失任何提交**。远端 `odoochain/20.0`（`ea0a6f3e857a`）是 OCB 线，不受影响。

---

## 5. 自主层构成与长期成本

| 组 | 文件数 | 上游是否改动 | 冲突风险 |
|---|---:|---|---|
| 打包层（`pyproject.toml`、`setup.py`、`MANIFEST.in`、`setup/pep517_odoo.py`） | 4 | **从不** | 极低 |
| 身份标识（`README.md`） | 1 | 从不 | 无 |
| 安装策略（30 个 `__manifest__.py`） | 30 | **经常** | **中** |

打包层近乎零成本——上游从未碰过这 5 个文件。**成本集中在 30 个 manifest。**

### 真实风险是静默回退，不是冲突数量

`sale_margin/__manifest__.py` 已在 PR #67 与 #68 中以**完全相同的原因冲突两次**。更隐蔽的风险是：**若某次同步中冲突被"取上游"解决，OCB 的 `auto_install` 策略会被静默改回 `True`，且不产生任何报错。**

**每次同步后必须跑策略校验**（已实测可用）：

```bash
python - <<'PY'
import ast, subprocess
OCB = 'ea0a6f3e857a77ff68d23e2fa7d2a01cda13dc1b'   # OCB 20.0 基线
files = subprocess.check_output(
    ['git','diff-tree','--no-commit-id','--name-only','-r',
     'ecba93571a156a0501ff4e9ce7a39ecc056737d2']).decode().split()
load = lambda rev,f: ast.literal_eval(
    subprocess.check_output(['git','show',f'{rev}:{f}']))
bad = [f for f in files
       if load('HEAD',f)['auto_install'] != load(OCB,f)['auto_install']]
print('策略校验：', 'PASS' if not bad else f'FAIL {bad}')
PY
```

```bash
git diff --stat odoo/master...chain
# 预期恰好 35 文件；出现其他文件即说明同步污染了工作树
```

### 三个应对选项（供决策）

| 选项 | 做法 | 优点 | 代价 |
|---|---|---|---|
| **A. 维持现状**（推荐起步） | 保留 30 个 manifest，每次同步手工解冲突 + 跑校验 | 简单，实测通常仅 1 处冲突 | 每次同步需人工介入 |
| **B. 策略移出主线** | `chain` 只留打包层；策略做成独立补丁或 addon | 主线更薄，同ync近乎零成本 | 需额外机制，部署时选择性应用 |
| **C. 推动上游收敛** | 提交 OCA/OCB 讨论推动采纳 | 根治 | 受制于上游接受度 |

**建议先执行 A，同时评估 B。** 冲突面小，A 成本可控；B 在策略模块继续增长后才划算。

---

## 6. 上游同步流程

### 6.1 同步 master 到 chain

```bash
git fetch odoo master
git switch -c sync/master-YYYYMMDD odoo/master
git merge --no-ff chain          # 把自主层叠加到新 master 上
# 解冲突 → 校验 → 开 PR
```

**顺序关键**：从 `odoo/master` 切分支再合 `chain`（自主层在上），冲突只发生在自主层文件上。

合并信息沿用仓库惯例：`Merge remote-tracking branch 'odoo/master' into chain`

### 6.2 冲突处理规则

1. **只允许按语义手工解**，禁止 `-X ours` / `-X theirs` 整文件取舍
2. `odoo/release.py` 版本号变化**应当接受**（跟随 master）
3. 30 个 manifest 冲突：取我们的 `auto_install` 值，其余取上游
4. 打包层若冲突：一旦出现说明上游开始改这套基建，需重新评估

### 6.3 同步后必做校验

- [ ] `git diff --stat odoo/master...chain` 恰好 35 文件
- [ ] 30 个 `auto_install` 策略校验通过
- [ ] `git diff --check` 无新增空白问题
- [ ] 全树无冲突标记
- [ ] `odoo-bin --version` 正常输出
- [ ] 全量 manifest 可解析、变更 Python 文件可编译

### 6.4 建议节奏

| 频率 | 动作 |
|---|---|
| **每周** | 同步 master，跑静态校验，开 PR |
| **每日**（可选） | 仅 `git fetch` + 查看落后数，不做合并 |
| 上游高风险变更时 | 立即同步并重点回归 |

落后 62 个提交属可控范围。**但 master 单日推进两次意味着：不设固定节奏，必然持续累积。**

---

## 7. OCB/OCA 精华吸纳机制

### 当前白名单（已吸纳）

| 来源 | 内容 | 纳入理由 |
|---|---|---|
| `3fd4308c7b40` | PEP 517/660 打包 | OCA 生态刚性需求，上游不提供 |
| `a9e0936e17f4` | wheel 包发现修复 | 上一条的必要修正 |
| `c9f0f9fe5449` | README 标识 | 身份声明 |
| `ecba93571a15` | `auto_install` 策略 | 降低自动安装带来的意外行为 |

### 候选吸纳流程

```bash
git fetch https://github.com/OCA/OCB.git 20.0
git cherry -v <官方20.0> <OCB20.0>    # 去重：确认是否已有等价补丁
```

**去重工具 `git cherry` 的实测价值**：本次用它发现 715 个 master 补丁中约 **627 个在官方 20.0 已有 patch-id 等价版本**（含 POS 订单保护 `95086bd9429a`、发票提交后发送 `cf48e0a8df70`、数据库恢复加固 `b927730f3000`）。**"上游有而我们没有"很多时候是假象**，必须先做 patch-id 比对。

### 判断标准

应进自主层，当且仅当：

- ✅ 上游不打算提供，且我们需要
- ✅ 属基础设施/构建/部署形态，不改变业务语义
- ✅ 能独立验证，风险可控
- ❌ **ORM、框架级重构**（`unlink()` 重构、`env.ref()` 行为变更）——跟随 master，不自制
- ❌ **移除兼容接口的清理类提交**（删除 `Reactive` 基类、`.less` 支持）——会破坏第三方模块
- ❌ 需要数据库迁移的功能——跟随上游版本

### 未开发的潜力：OCA 模块生态

当前只接入 `OCA/OCB`（源码 backports + 打包层）。OCA 更大的价值在**模块仓库生态**（`server-ux`、`accounting-tools` 等）。

两者层面不同：OCB 改 Odoo 本体，OCA 模块是**旁路扩展**，天然不与上游 master 冲突。这可能是比"改本体"更安全的自主增值方向。**建议作为后续独立议题评估。**

---

## 8. 红线

1. **不把 master 整体合入 20.0**——两条线跨发布线，会带入 ORM 重构等破坏性变更
2. **不用 squash 合并**——会丢外部贡献者署名与 cherry-pick 回指
3. **不在未验证状态下把 PR 标为 Ready**——本仓库无项目 CI（仅 dependency-graph 工作流），验证只能靠人工
4. **不静默解冲突**——尤其 `auto_install` 策略，取上游即等于放弃自主决策
5. **不扩大自主层而不自知**——每次同步后校验 35 文件边界

---

## 9. 待决事项

| # | 事项 | 状态 |
|---|---|---|
| 1 | 本地 `20.0` 分支改名或删除 | **已解决**（2026-10-06）已确认是官方 20.0 的祖先，删除无损失，已删除 |
| 2 | 为 `chain` 设置 upstream = `odoo/master` | **已解决**（2026-10-06）已完成 |
| 3 | 提交 `auto_install` 策略选 A / B / C | **待决**（建议先执行 A） |
| 4 | 是否引入 OCA 模块仓库 | **待决**（建议作为独立议题） |
| 5 | PR #67 / #68 的构建与数据库回归执行方式 | **已定**，见 `test-gates.md` |
| 6 | ~~20.0 稳定线的角色~~ | **已定**（2026-10-06）**仅作参考**，不用于生产 |

---

## 10. 关联文档

- `pr67-pr68-roles.md` — 两个 PR 的作用、分工与冲突记录
- `test-gates.md` — 构建与数据库回归门禁的执行方案
- `branch-20.0-chain-vs-master.md` — 20.0 线与 master 线的拓扑分析（早期笔记）

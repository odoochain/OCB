# 构建与数据库回归门禁：执行方案

> 制定日期：2026-10-06
> 关联：`pr67-pr68-roles.md`、`development-route.md`

---

## 1. 问题根因

不是"没人愿意跑测试"，而是**门禁缺少可复现的载体**：

| 障碍 | 实测状态 |
|---|---|
| 本地 Python 环境不完整 | `.venv` = 3.12.13，有 `psycopg2`/`packaging`，**缺 pip / setuptools / build / wheel** |
| 无本地 PostgreSQL **服务端** | 仅有 msys2 的 `psql`/`pg_ctl`/`initdb` 客户端；无 postgres 服务 |
| 无容器运行时 | 无 docker / podman（有 `wsl.exe`） |
| 仓库无 CI | `.github/` 下只有 issue 与 PR 模板；远端仅一个内置 dependency-graph 工作流 |
| 无分支保护 | `chain` 无 protection（API 返回 404） |

**结论：验证只能靠人工临时搭建，每次都不可复现。这是路线文档中"手动门禁"一条的根本成因。**

---

## 2. 环境探测结论（决定方案的关键事实）

| 探测项 | 结果 | 影响 |
|---|---|---|
| `uv` | **0.12.23** 可用 | 可秒级创建带 setuptools 的环境 |
| 目录符号链接 | **可以创建**（已实测创建并清理成功） | **`setup/pep517_odoo.py` 的构建期 symlink 步骤本机可行** |
| 仓库可见性 | **public** | GitHub Actions 标准 runner **免费无限** |
| Actions 权限 | 已启用，`allowed_actions: all` | 可直接加工作流 |
| 自建 runner | 0 个 | 用 GitHub 托管 runner，无需自建 |
| 远端默认分支 | `19.0`（**不是** chain/master） | 工作流需显式指定触发分支 |

符号链接这条最关键：OCB 打包层在构建期要把 `addons/*` 链进 `odoo/addons/`。若本机不支持，该门禁只能上 Linux CI。**实测支持，因此构建门禁可本地执行，不必等 CI。**

---

## 3. 三档门禁与分工

### 档位 1：静态门禁 —— 本地，每次同步必跑

**零依赖**，用现有 `.venv` 即可，全部秒级完成：

```bash
python - <<'PY'
import ast, subprocess, sys
from pathlib import Path
def run(*a): return subprocess.check_output(['git',*a], text=True, encoding='utf-8')
fails = []

# 1) 自主层范围未被污染
changed = set(run('diff','--name-only','odoo/master...HEAD').split())
if len(changed) > 35:
    fails.append(f'autonomous layer grew: {len(changed)} files (expect <= 35)')

# 2) 30 个 auto_install 策略未被上游静默改回
OCB = 'ea0a6f3e857a77ff68d23e2fa7d2a01cda13dc1b'
files = run('diff-tree','--no-commit-id','--name-only','-r',
            'ecba93571a156a0501ff4e9ce7a39ecc056737d2').split()
load = lambda rev,f: ast.literal_eval(run('show',f'{rev}:{f}'))
bad = [f for f in files if load('HEAD',f)['auto_install'] != load(OCB,f)['auto_install']]
if bad: fails.append(f'auto_install policy regressed: {bad}')

# 3) 全量 manifest 可解析
mans = list(Path('addons').glob('*/__manifest__.py')) + list(Path('odoo/addons').glob('*/__manifest__.py'))
for f in mans:
    try: ast.literal_eval(f.read_text(encoding='utf-8'))
    except Exception as e: fails.append(f'manifest broken: {f}: {e}')

# 4) 无冲突标记
r = subprocess.run(['git','grep','-I','-l','-E',r'^(<<<<<<<|>>>>>>>|\|\|\|\|\|\|\|)','HEAD'],
                   capture_output=True, text=True)
if r.returncode == 0: fails.append(f'conflict markers: {r.stdout.split()}')

# 5) release.py 未被自定义修改
if run('show','HEAD:odoo/release.py') != run('show','odoo/master:odoo/release.py'):
    fails.append('odoo/release.py diverges from upstream master')

print('\n'.join(fails) if fails else 'STATIC GATES: PASS')
sys.exit(1 if fails else 0)
PY
```

**建议固化为脚本**（如 `tools/verify-autonomous-layer.ps1`）提交进仓库，避免每次手敲。

---

### 档位 2：构建门禁 —— 本地可执行，**现在就做**

这是 PR #67 的核心验证（打包层正是 PR #67 的主要内容），**不需要数据库**。

环境已具备（`uv` + symlink 可用）：

```powershell
# 1) 建隔离环境（uv 秒级完成，不污染现有 .venv）
uv venv D:\odoochain\buildenv --python 3.12
uv pip install --python D:\odoochain\buildenv\Scripts\python.exe "setuptools>=64" build wheel

# 2) 构建 sdist 与 wheel（产物输出到仓库外）
D:\odoochain\buildenv\Scripts\python.exe -m build --no-isolation --outdir D:\odoochain\buildout

# 3) 关键断言：wheel 中不得出现顶层 addons/ 重复打包
#    （验证 a9e0936 的 prune addons + find_namespace_packages(include=...)）

# 4) editable 安装并验证 compat 模式生效
uv pip install --python D:\odoochain\buildenv\Scripts\python.exe -e . --no-build-isolation --no-deps
# 断言 A：生成的是 .pth（compat 模式），而非 __editable___*_finder.py（default 模式）
Get-ChildItem D:\odoochain\buildenv\Lib\site-packages -Filter "__editable__*"
# 断言 B：.pth 内容为项目根路径
Get-Content D:\odoochain\buildenv\Lib\site-packages\__editable__.odoo-*.pth
# 断言 C：从无关目录导入 odoo 能解析到项目内
cd D:\; D:\odoochain\buildenv\Scripts\python.exe -c "import odoo; print(list(odoo.__path__))"

# 5) 确认构建未污染工作树（pep517_odoo.py 的 finally 应已清理符号链接）
git status --porcelain
(Get-ChildItem odoo/addons).Count   # 应为 17（base + 15 个 test_* + .gitkeep）
```

**需预置**：`D:\odoochain\buildenv`、`D:\odoochain\buildout` 目录，以及 `dist/`、`*.egg-info` 的 gitignore 条目。

---

### 档位 3：数据库门禁 —— 交给 GitHub Actions

**本机无 PostgreSQL 服务端**，硬搭一套（msys2 initdb）脆弱且不可复现。而仓库为 **public**、Actions **已启用**、**0 自建 runner** —— 用 `services: postgres` 是最优解，且**一次搭建、长期受益于所有后续 PR**。

建议工作流（`.github/workflows/gates.yml`）分层：

| Job | 内容 | 触发 | 预计耗时 |
|---|---|---|---|
| **A** | 档位 1 静态门禁 | 每次 push / PR | ~1 min |
| **B** | 档位 2 构建门禁（sdist + wheel + editable） | 每次 push / PR | ~5 min |
| **C** | `odoo-bin -d testdb -i base --stop-after-init`（`services: postgres:16`） | 每次 push / PR | ~10 min |
| **D** | 目标模块测试（按改动模块动态选择） | 仅 `sync/*` 与 `feat/*` | ~15 min |
| **E** | 20.0 库升级测试（先装 20.0 基线库，再用同步分支升级） | **手动 / 定时** | ~30 min |

**纪律要求**：

- **不要**在 CI 跑 Odoo 全量测试套件（数千测试 + JS 测试需浏览器），会超时且无反馈价值
- Job E 手动触发，因为 20.0 线**仅作参考**，不值得每次占用配额
- Odoo 仓库约 1–2 GB，checkout 偏慢，Job A/B 建议开 cache
- 工作流需显式指定触发分支（远端默认分支是 `19.0`，不是 `chain`）

---

## 3.5 档位 2 已执行结果（2026-10-06，在 `chain-ocb-backport` 上）

环境：Python 3.12.13、**setuptools 84.0.0**、build 1.6.1、wheel 0.48.0（`uv 0.12.23` 创建，位于仓库外的 `D:\odoochain\buildenv`）

| 断言 | 结果 |
|---|---|
| `python -m build --wheel` 成功 | ✅ 117 秒，产出 `odoo-20.1a1-py3-none-any.whl`，259.1 MB / 58,540 条目 |
| **wheel 无顶层 `addons/` 重复打包** | ✅ PASS（核心断言，验证 `a9e0936` 的 `prune addons` + `find_namespace_packages(include=...)`） |
| 社区模块进入 `odoo/addons/` | ✅ `sale` / `stock` / `web` / `account` 的 `__init__.py` 均在 wheel 内 |
| editable 安装走 compat 模式 | ✅ 生成 `__editable__.odoo-20.1a1.pth`，内容为项目根；**无** `__editable___*_finder.py` |
| 从无关目录 `import odoo` | ✅ 解析到 `['D:\\odoochain\\odoochain\\odoo']` |
| **构建后工作树干净** | ❌ **FAIL — 残留 163 个符号链接** |
| sdist 构建 | ⬜ 未执行 |
| editable 环境可运行 Odoo | ⬜ 未执行（`--no-deps` 未装运行时依赖，属档位 3 范畴） |

### 符号链接残留：根因与结论

**现象**：`setup/pep517_odoo.py` 的 `_symlink_addons()` 在 `finally` 中连续 `unlink()` **655 次**（`addons/` 下 655 个模块目录）。本环境的批量删除保护拦截了该操作：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":500,"threshold":500,...}
ERROR Backend subprocess exited when trying to invoke build_wheel
```

清理被拦断 → 构建 **exit 1** → `odoo/addons/` 残留 163 个符号链接（目录项从 17 增至 180）→ `git status` 出现 164 条 untracked。

**结论（务必区分）**：

- 这是**本环境特有**的守卫导致，**不能据此判定 OCB 代码有缺陷**。在正常机器或 Linux CI 上，655 次 `unlink()` 可正常完成。
- 但它暴露了一个真实性质：清理过程**非原子、不抗中断**。任何中断（守卫、Ctrl-C、磁盘错误）都会留下数百个 untracked 条目，污染工作树。
- 首次构建曾成功（exit 0）且同样残留 163 个，说明残留与构建成败无关，只与清理被拦断有关。

**处置**：

- 已清理完毕，工作树经新进程复核为 17 项 / 0 符号链接 / `git status` 仅剩 `doc/dev/`。
- **PR #67 应在描述中记录此现象**，并说明本机未通过该项，Linux CI 需复验。
- **CI 必须加 `git status --porcelain` 断言**，否则此类污染会被漏掉。

### 门禁脚本的更正

原方案中 `python -c "import odoo.addons.sale"` **是错误断言**。实测：Odoo 20 的 `odoo/` **没有 `__init__.py`**（命名空间包，`odoo.__file__ is None` 属正常），且工作树中社区模块**不在 `odoo/addons/` 下**——它们位于根 `addons/`，由 Odoo 运行时通过 `addons_path` 发现，不是靠 `odoo.addons.*` 包命名空间导入。

因此 editable 的正确断言是「`.pth` 指向项目根 + 从无关目录可 `import odoo`」，已在上文 §3 档位 2 中更正。

### sdist 验证结果（2026-10-06）

`python -m build --sdist` 耗时 288.6 秒，**未产出归档**（退出 1）：内容已组装到 `Creating tar archive`，随后 setuptools 删除临时目录 `odoo-20.1a1/`（48,647 个文件）与符号链接清理**再次被同一个守卫拦断**，构建前端中止。

由于归档未落盘，改用**构建日志取证**，四项 MANIFEST.in 断言均可判定：

| 断言 | 证据 | 结果 |
|---|---|---|
| `setup/pep517_odoo.py` 进入 sdist | `copying setup\pep517_odoo.py -> odoo-20.1a1\setup` | ✅ |
| `pyproject.toml` 进入 sdist | `copying pyproject.toml -> odoo-20.1a1` | ✅ |
| 顶层 `addons/` 被 prune | 日志中 `creating odoo-20.1a1\addons\` 出现 **0** 次 | ✅ |
| 社区模块经 `odoo/addons/` 进入 | `creating odoo-20.1a1\odoo\addons\sale` | ✅ |

**仍未覆盖**：`backend-path` 解析路径——即「**从已生成的 sdist 再构建 wheel**」。这是 OCB 后端唯一未验证的分支，理论上由 `include setup/pep517_odoo.py` + `backend-path = ["setup"]` 共同保证，但本机无法产出归档故无法实测。**建议在 Linux CI 上补做。**

### 构建产物残留的处理

sdist 失败后在仓库根留下临时目录 `odoo-20.1a1/`（48,647 文件，untracked）。已删除，工作树经复核恢复为 17 项 / 0 符号链接 / `git status` 仅 `doc/dev/`。

**教训：本机执行构建必须在结束后检查 `git status` 与根目录临时目录**，守卫拦断清理会同时留下符号链接和 sdist 临时目录两类污染。

---

## 4. 强制执行：分支保护

CI 建好后必须加保护，否则"门禁"只是建议：

| 分支 | 规则 |
|---|---|
| `chain` | 禁止直接推送；必须经 PR；必须通过 Job A+B+C；**禁止 squash merge** |

当前有 `admin` 权限，可直接配置。

---

## 5. 门禁分级（按 PR 重要性）

结合 `20.0` 线**仅作参考**的决策：

| PR | 门禁档位 | 理由 |
|---|---|---|
| **#67** | **A + B + C + D** | 开发主干，缺它就没有自主层 |
| **#68** | **A + B + C 精简版** | 参考线；715 个提交由 Odoo 自行测试，我们的边际面只有 35 文件 |

**关键判断：两个 PR 相对各自上游的差异都只有 35 个文件**（4 打包 + 1 README + 30 manifest）。其余带入的提交是 Odoo 已测过的代码。**门禁应按 35 行的差异面定，不按 715/62 个提交的总量定。**

若将来把 `20.0` 升为生产基线，必须补齐 Job E，`pr67-pr68-roles.md` §6 需重新评估。

---

## 6. 分工建议

| 事项 | 执行者 | 备注 |
|---|---|---|
| 档位 1 脚本固化 | 可交给我 | 纯本地，零风险 |
| 档位 2 构建验证 | 可交给我 | 环境已具备，**建议立即执行** |
| 档位 3 CI 工作流 | 需你确认后我再写 | 会写入 `.github/workflows/`，属仓库改动 |
| Job E / 20.0 升级测试 | 你或指定维护者 | 20.0 仅作参考，优先级最低 |
| 分支保护配置 | 需你确认 | 属仓库策略变更 |
| 门禁结果的最终判定 | 人工审查者 | CI 只提供证据，不替代判断 |

---

## 7. 现状与下一步

**当前**：PR #67 与 #68 均因构建/数据库门禁未执行而保持 Draft。

**建议顺序**：

1. 立刻执行档位 2 构建验证（环境已就绪，无依赖）→ 大概率解除 PR #67 的一半阻塞
2. 固化档位 1 脚本 → 两个 PR 都能快速自证
3. 你确认后编写 CI 工作流（A/B/C/D）→ 长期自动化
4. 加 `chain` 分支保护 → 门禁从建议变强制
5. PR #68 按精简门禁处理，**不必等 Job E**

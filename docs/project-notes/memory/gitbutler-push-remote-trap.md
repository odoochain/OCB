---
name: gitbutler-push-remote-trap
description: "本仓库 but push 会推到无权限的 odoo 官方上游；可写 fork 是拼错的 remote \"orgin\"，推送要用 git push orgin"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

推送自定义分支的坑与正解。

`but push <branch>` 在本仓库会把分支 `--force` 推到 GitButler 的 target remote **`odoo`**（`git@github.com:odoo/odoo.git`，Odoo 官方上游），报错 `ERROR: Permission to odoo/odoo.git denied to odoochain`。

remote 清单：`odoo`→官方上游(无写权限)、`Viindoo`→Viindoo/odoo.git、**`orgin`**（拼写少一个 i，本应是 origin）→ `git@github.com:odoochain/chain19.git`（个人可写 fork）。

**Why:** GitButler 的 target/push remote 指向官方 `odoo`，个人没有官方写权限；而 `but push` 不支持指定 remote。

**How to apply:** 推送自定义分支直接用 `git push orgin <branch>`（这是 `but push` 局限下的正当 fallback，不违背"优先用 but"的精神）。`19.0-chain` 对 `orgin/19.0-chain` 是 fast-forward 关系，普通 push 即可、无需 force。

**已调查并决定不改 GitButler（2026-06-25）：** 想让 `but push` 原生走 orgin 需改 GitButler push remote，但 **CLI 不支持**（`but config target` 只设 base 分支、无 push remote 选项；`but config forge` 只管认证）。真相源是 `.git/gitbutler/but.sqlite` 的 `vb_state` 表（字段 `default_target_push_remote_name='origin'`、`default_target_remote_name='origin'`，而 git 里根本没有 origin remote；`virtual_branches.toml` 仅为镜像，sqlite 用 `toml_last_seen_sha256` 检测 toml 外部改动）。且 sqlite 的 stack head 与 git 已不完全同步。结论：手改 sqlite 风险高（损坏 workspace）、收益低（仅省敲 remote 名），**长期就用 `git push orgin`**。真要改，用 `but gui` 图形界面设 push remote 最安全（官方支持 fetch≠push 分离）。

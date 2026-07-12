---
name: winget-seekdb-mismatch
description: "winget 升级列表里的 \"seekdb\" 是误配的 SysManage Agent，非本机 OceanBase SeekDB，已 pin 屏蔽"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

`winget upgrade` 会把本机名为 "seekdb" 的已安装项误关联到社区源里 moniker 恰好叫 seekdb 的无关包 `sysmanage.sysmanage-agent`（SysManage Agent，Bryan Everly 的开源主机/车队管理 daemon，AGPL-3.0），显示 "1.3.0.0 → 3.0.x" 的假升级提示。

**真相**：本机装的是 OceanBase seekdb 1.3.0.0（向量数据库，exe 在 `D:\programs\seekdb\bin\seekdb.exe`，端口 2881），与那个运维 agent 毫无关系。若执行 `winget upgrade` 会装进 SysManage Agent 的 MSI，纯负收益。

**已处理**：2026-07-12 执行 `winget pin add --id sysmanage.sysmanage-agent`，升级列表里该行已消失。

**要真升级 OceanBase SeekDB**：走 OceanBase 官方发布页，不是 winget；先 `winget pin remove --id sysmanage.sysmanage-agent` 解 pin，再备份 `D:\mydata\seekdb` + 查 breaking changes + 确认匹配的 pyseekdb（当前客户端见 [[seekdb-setup-status]]），且等 agent-memory 端到端测试跑通后再动。

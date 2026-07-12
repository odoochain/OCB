---
name: seekdb-setup-status
description: SeekDB V1.3.0 安装在 Windows 上的配置 — 端口/路径/密码/客户端项目位置
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

# SeekDB 安装配置

SeekDB V1.3.0 (OceanBase AI-native database) 已在 Windows 上以 server 模式安装并验证通过。

**服务端**:
- 二进制: `D:\programs\seekdb\bin\seekdb.exe`
- 数据目录: `D:\mydata\seekdb`
- 配置文件: `D:\mydata\seekdb\etc\seekdb.cnf`
- 端口: 2881 (MySQL 协议)
- 启动命令: `seekdb.exe --service --base-dir=D:/mydata/seekdb --port=2881 --parameter memory_limit=2G --parameter cpu_count=4`
- 用户: root, 密码在系统环境变量 `SEEKDB_PASSWORD`

**客户端项目**: `D:\dev\lawgraph\seekdb\`
- Python 3.12.13, uv 管理
- pyseekdb 1.4.0
- 连接方式: `pyseekdb.Client(host='127.0.0.1', port=2881, database='test', user='root', password=os.environ['SEEKDB_PASSWORD'])`

**用途**: agent 记忆持久化，作为 PG/AGE 的补充。架构: SAG (知识检索) + PG/AGE (图推理) + SeekDB (agent memory)

**Why:** SAG 用 PG+pgvector 做知识检索，但 agent 对话记忆需要高效的向量+全文混合搜索和 COW 沙箱(Fork/Merge)能力，SeekDB 的这些特性更适合。

**How to apply:** 连接 SeekDB 时须从系统环境变量读密码；Windows 上仅支持 server 模式（不支持 embedded）。[[sag-setup-status]]

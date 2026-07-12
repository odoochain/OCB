---
name: vexdb-lite-vs-seekdb-decision
description: 向量层选型决策——agent-memory 用 SeekDB，VexDB-Lite 作为 SAG/Odoo 层替换 pgvector 的候选，二者不同层不互替
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

2026-07-12 评估 `github.com/odoochain/VexDB-Lite`（fork 自清华 `VexDB-THU/VexDB-Lite`，07-11 建 fork，C/C++ 向量索引扩展，插进 PG/DuckDB/SQLite，MIT 开源版 + 商用版 VexDB，无 release）后定的架构方向。

**Why:** VexDB-Lite 与 SeekDB 不是同一层的东西，不能直接二选一。VexDB-Lite 是**向量索引扩展**（README 自己的对比表就是 pgvector vs vexdb-lite vs VexDB），对标的是 **pgvector**；它的强项是"原生 PG 同库 + 自研 graph_index 更快"。但它**没有**中文全文分词、混合检索（向量+全文 RRF）、Fork/Merge 沙箱——而这三样正是当初选 SeekDB 的核心理由（见 [[seekdb-setup-status]] 和计划文档），对中文法律场景的记忆召回是刚需。

**How to apply:**
- **agent-memory 继续用 SeekDB**（2881），不因 VexDB-Lite 改路线——混合检索+IK 中文分词+沙箱是记忆质量命脉，PG 路线要叠 pg_jieba+应用层 RRF 等于重造 SeekDB 已有轮子。
- **VexDB-Lite 定位 = 替换 pgvector**：留作 SAG(5433) / Odoo ai.memory 向量层的候选（纯向量 + 要和 PG 业务数据同库 + 要更快图索引），后续评估，非现在。
- 现实约束：本项目在 Windows 开发，编译 C++ 的 PG 扩展折腾；VexDB-Lite 无 release、fork 才 1 天，暂不入核心链路。
- "原生 PG 比 SeekDB 强"这个观察正确，但它证明的是 VexDB-Lite 该去替 pgvector，不是替 SeekDB。

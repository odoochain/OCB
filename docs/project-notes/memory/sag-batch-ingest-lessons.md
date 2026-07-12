---
name: sag-batch-ingest-lessons
description: SAG 批量导入法律文档的经验教训 — 超时、JSON截断、PG 断连、去重清理、模型选择
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

# SAG 批量导入经验

226 篇海南地方法规成功导入 SAG，最终 223 条唯一文档。详细报告见 `D:\dev\lawgraph\SAG\docs\hainan-law-ingest-report.md`。

**关键教训**:
- **LLM_TIMEOUT_MS** 对长法规文档必须 ≥180s，60s 会导致 25/226 失败
- **Qwen3-8B** 对特定长文档会 JSON 截断，切 **Qwen2.5-32B-Instruct** 可解决（Qwen3-30B-A3B 在硅基流动已禁用）
- **SAG AI 设置存数据库**，改 `.env` 不够，必须通过 `PUT /api/settings/ai` 更新（需传完整对象）
- PG 重启会导致 SAG 崩溃（连接池无 error handler），需重启 SAG
- 多轮重试会产生重复文档，需用 SQL `ROW_NUMBER() OVER (PARTITION BY title ORDER BY created_at DESC)` 去重，按依赖顺序删 event_entities → events → source_chunks → document_sections → documents

**工具**: [[sag-setup-status]]
- 批量导入: `SAG/scripts/batch-ingest-laws.ts`
- 独立 embedding 服务: `D:\dev\lawgraph\embedding-server\` (端口 11435)

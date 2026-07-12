---
name: sag-setup-status
description: SAG (Zleap-AI/SAG) multi-hop retrieval system setup status and configuration details
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

SAG 多跳文档检索系统**全链路打通**,embedding + LLM + rerank + multi-hop search 均验证通过。

**Why:** 用 SAG 替代纯 PG+AGE 做法律知识库的多跳关系推理。
**How to apply:** 后续 Stage 3 要写 Odoo forjoy 数据导出器。

## 当前状态 (2026-06-30)

### Stage 1: 基础设施 ✅
- PostgreSQL 18.4 端口 5433 (MSYS2 MinGW build), 启动命令: `start_pg.bat start`
- sag_lite 数据库: pgvector + 7 migrations + 11 entity types (seeded)
- SAG API 启动: `cd D:\dev\lawgraph\SAG && npx tsx src/index.ts` (端口 4173)
- Windows 兼容性修复: commit a919153

### Stage 2: AI 端点配置 ✅ (全链路打通)
- **Embedding**: 硅基流动 `BAAI/bge-m3` (原生 1024 维, 匹配 SAG vector(1024))
- **LLM**: 硅基流动 `Qwen/Qwen3-8B` (事件/实体抽取用)
- **Rerank**: 硅基流动 `BAAI/bge-reranker-v2-m3` (129ms per query)
- AI Settings 通过 `PUT /api/settings/ai` 持久化到 DB(embedding + LLM)
- Rerank model 通过 `.env` RERANK_MODEL 配置
- 代码修复已提交 (commit a382439):
  - `embedding-client.ts`: bge-m3 等固定维度模型不传 dimensions 参数
  - `rerank-client.ts`: `/rerank` 端点(非 `/reranks`)

### Stage 3: Odoo 数据导出器 (未开始)

## 已验证的 API key
- 硅基流动 `sk-uydmawnw...`: embedding + LLM + rerank 均可用
- 智谱旧 key `f44969...`: 余额为 0, 不可用
- 智谱 code plan key `98d7b9e5...`: 只对 CodeBuddy IDE 插件有效, 裸 API 不可用

## 测试项目
- Project ID: `1d253cc3-6237-4a3a-8123-00ee77979b82` (法律知识库测试)
- Document: 民事诉讼管辖权规定 (4 chunks, 4 events)
- Vector search score 0.707 命中正确段落
- Multi-hop search 完整 8 步 pipeline: embedding → BM25 → event retrieval → coarse rank → rerank → chunk fetch, 总耗时 ~520ms

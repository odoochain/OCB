# Agent Memory 独立服务设计

## Context

架构目标：SAG（知识检索）+ PG/AGE（图推理）+ **SeekDB（agent memory）**。
SeekDB V1.3.0 已装好跑通（localhost:2881），pyseekdb 1.4.0 客户端验证通过。

Odoo 19 的 `ai` 插件已有 `ai.memory` 模型（pgvector 1536维，IVFFlat），功能完整但受限于 Odoo ORM 和单一的 pgvector cosine 检索。SeekDB 提供 vector+fulltext 混合搜索、IK 中文分词、Fork/Merge COW 沙箱——这些能力是 pgvector 不具备的。

策略：**先独立后桥接**——第一阶段做独立 SeekDB memory 服务跑通，第二阶段再考虑和 Odoo ai.memory 数据同步。

## 技术栈

- **Python 3.12 + FastAPI + uvicorn**
- **pyseekdb** 直连 SeekDB（无 HTTP 中转）
- 项目位置：`D:\dev\lawgraph\agent-memory\`
- 依赖管理：uv（和 seekdb 项目同模式）
- 复用已有的 embedding server（localhost:11435，bge-m3，1024维）

## 数据模型

### SeekDB 中的 Collection 设计

一个 database `agent_memory`，下设两个 collection：

#### 1. `memories` — 核心记忆存储

每条记录的字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | UUID，主键 |
| document | string | 记忆内容文本（自动 embedding + fulltext 索引） |
| metadata.agent_id | string | agent 标识 |
| metadata.user_id | string | 用户标识 |
| metadata.memory_type | string | episodic/semantic/procedural/preference（对齐 Odoo ai.memory） |
| metadata.importance | float | 0-1，重要度 |
| metadata.access_count | int | 访问次数 |
| metadata.last_accessed | string | 最后访问时间（ISO 8601） |
| metadata.source | string | 来源标识（sag/odoo/chat/manual） |
| metadata.session_id | string | 关联会话 ID（可选） |
| metadata.expires_at | string | 过期时间（可选） |
| metadata.tags | string | 逗号分隔标签 |
| metadata.created_at | string | 创建时间 |

#### 2. `conversations` — 对话历史

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | UUID |
| document | string | 消息内容 |
| metadata.session_id | string | 会话 ID |
| metadata.role | string | user/assistant/system/tool |
| metadata.agent_id | string | agent 标识 |
| metadata.user_id | string | 用户标识 |
| metadata.turn_index | int | 轮次序号 |
| metadata.created_at | string | 时间戳 |
| metadata.parent_id | string | 父消息 ID（可选，用于分支对话） |

### Schema 配置

- **Vector index**: HNSW, 1024 维, cosine 距离
- **Fulltext index**: IK 分词器（中文法律内容友好）
- **Embedding function**: 自定义，指向 localhost:11435 (bge-m3)

## REST API 设计

基于 FastAPI，端口 **11436**（紧跟 embedding server 的 11435）。

### Memory 端点

```
POST   /v1/memories                    — 创建记忆
GET    /v1/memories/{id}               — 获取单条
PUT    /v1/memories/{id}               — 更新记忆
DELETE /v1/memories/{id}               — 删除记忆
POST   /v1/memories/search             — 混合搜索（vector + fulltext + metadata filter）
POST   /v1/memories/batch              — 批量创建
DELETE /v1/memories/batch              — 批量删除（按 filter）
POST   /v1/memories/extract            — 从对话中提取记忆（调 LLM）
```

### Conversation 端点

```
POST   /v1/conversations               — 记录对话消息
GET    /v1/conversations/{session_id}   — 获取会话历史
DELETE /v1/conversations/{session_id}   — 删除会话
POST   /v1/conversations/search        — 搜索对话内容
```

### 管理端点

```
GET    /health                          — 健康检查
GET    /v1/stats                        — 统计信息（记忆数、会话数等）
POST   /v1/maintenance/compress         — 触发记忆压缩
POST   /v1/maintenance/cleanup          — 清理过期记忆
POST   /v1/fork                         — Fork 当前数据库（COW 沙箱）
POST   /v1/merge                        — Merge 回主库
```

### 搜索请求示例

```json
POST /v1/memories/search
{
  "query": "用户对合同审查的偏好",
  "agent_id": "legal-assistant",
  "user_id": "user-001",
  "memory_types": ["preference", "semantic"],
  "top_k": 5,
  "min_importance": 0.3,
  "hybrid": true
}
```

## 项目结构

```
D:\dev\lawgraph\agent-memory\
  pyproject.toml
  .env
  src/
    agent_memory/
      __init__.py
      main.py              — FastAPI app + uvicorn 启动
      config.py            — 环境配置（Pydantic Settings）
      models.py            — Pydantic 请求/响应模型
      store.py             — SeekDB 存储层（pyseekdb 封装）
      embedding.py         — 自定义 EmbeddingFunction（调 localhost:11435）
      search.py            — 搜索逻辑（混合搜索 + 衰减排序 + 重排）
      memory_ops.py        — 记忆生命周期（提取、压缩、清理）
      conversation.py      — 对话历史管理
```

## 关键实现细节

### 自定义 EmbeddingFunction

pyseekdb 支持注册自定义 embedding function。实现 `EmbeddingFunction` 协议，
`__call__` 方法内 HTTP 调用 `localhost:11435/v1/embeddings`（bge-m3），
返回 1024 维向量。这样 `collection.add(documents=...)` 会自动生成 embedding。

### 衰减排序（对齐 Odoo ai.memory 逻辑）

从 Odoo 的 `get_effective_weight` 移植：
```
weight = (importance + min(access_count * 0.1, 0.5)) * exp(-decay_rate * age_days)
```

SeekDB 向量搜索返回 top_k*4 候选，Python 层做衰减重排后返回 top_k。

### 混合搜索

利用 SeekDB 原生 `hybrid_search`：
- **knn 腿**：query embedding → cosine 相似度
- **query 腿**：IK 分词全文检索
- **RRF 融合**：`rank_window_size=60, rank_constant=60`
- **metadata 过滤**：agent_id, user_id, memory_type, importance >= threshold, 未过期

### 记忆压缩（对齐 Odoo cron_compress_memories）

定期任务（可通过 API 或 cron 触发）：
1. 找到 > 7 天、access_count > 0、无 summary 的记忆
2. 按 (agent_id, user_id) 分组
3. 3+ 条时调 LLM 总结为一条 semantic 记忆
4. 存入新记忆，标记旧记忆为 archived

### Fork/Merge 沙箱

SeekDB 的杀手特性——agent 可以 fork 一份 memory 做试探性推理：
- `POST /v1/fork` → `admin.fork_database("agent_memory", "agent_memory_sandbox_xxx")`
- 在沙箱中自由读写
- `POST /v1/merge` → 把沙箱结果合并回主库（策略可选 fail/theirs/ours）
- 回收沙箱 `admin.delete_database("agent_memory_sandbox_xxx")`

## 与 Odoo ai.memory 的桥接（第二阶段，本次不实现）

预留设计方向：
1. **Odoo → SeekDB 同步**：写一个轻量 Odoo addon `ai_seekdb_bridge`，在 `ai.memory` 的 create/write 上挂 `@api.model_create_multi` 后处理，异步推送到 agent-memory 服务
2. **Embedding 维度对齐**：Odoo 用 1536 (OpenAI)，我们用 1024 (bge-m3)。桥接时需要在 SeekDB 侧用 Odoo 的 embedding 原样存储（建一个 1536 维的 collection），或者用 bge-m3 重新生成 1024 维
3. **双向查询**：agent-memory 服务提供 `/v1/memories/search` 时可选择同时查 Odoo（通过 Odoo JSON-RPC）

## 实施步骤

1. **初始化项目** — uv init, 安装 fastapi/uvicorn/pyseekdb/httpx
2. **实现 embedding.py** — 自定义 BgeM3EmbeddingFunction
3. **实现 store.py** — SeekDB 连接、collection 创建（含 Schema 配置）
4. **实现 models.py** — Pydantic 请求/响应模型
5. **实现 main.py** — FastAPI 路由：CRUD + search + health
6. **实现 search.py** — 混合搜索 + 衰减排序
7. **实现 conversation.py** — 对话历史管理
8. **实现 memory_ops.py** — 提取/压缩/清理（LLM 调用部分可先 stub）
9. **端到端测试** — 启动服务，curl 验证全部端点

## 验证

1. `cd D:\dev\lawgraph\agent-memory && uv sync` 安装依赖
2. 确保 SeekDB (2881) 和 embedding-server (11435) 在运行
3. `uv run python -m agent_memory.main` 启动服务 (11436)
4. 测试流程：
   - `POST /v1/memories` 创建几条测试记忆
   - `POST /v1/memories/search` 混合搜索验证
   - `GET /v1/memories/{id}` 单条获取
   - `POST /v1/conversations` 记录对话
   - `GET /v1/conversations/{session_id}` 获取历史
   - `GET /health` 确认服务正常
5. 验证 SeekDB 中的数据：用 pyseekdb 客户端直连检查 collection 内容

---

## 进度快照（2026-07-02）

### Odoo 19 主仓库

| 事项 | 状态 | 说明 |
|------|------|------|
| 合入上游 odoo/19.0 | ✅ 完成 | 207 commit merged，无冲突，commit `771908a9` |
| Remote 名称修正 | ✅ 完成 | `orgin` → `origin` |
| GitButler target 更新 | ✅ 完成 | common base 从 2024-09-25 → 2026-07-02 |
| 自定义开发 | ✅ 在线 | CodeBuddy（4 commit）、AGE/GraphRAG 文档、dev env 配置 |
| 与 upstream 同步 | ✅ 同步 | 本地 = origin/19.0-chain |

### Agent Memory 服务（`D:\dev\lawgraph\agent-memory\`）

| 模块 | 状态 | 说明 |
|------|------|------|
| pyproject.toml + uv sync | ✅ 完成 | |
| embedding.py | ✅ 完成 | BgeM3EmbeddingFunction → localhost:11435 |
| config.py | ✅ 完成 | Pydantic Settings, env_prefix `AGENT_MEMORY_` |
| store.py | ✅ 完成 | SeekDB 连接, HNSW 1024维 + IK 分词 |
| models.py | ✅ 完成 | 4 种记忆类型, CRUD + search 模型 |
| main.py | ✅ 完成 | 10 个 REST 端点 |
| search.py | ✅ 完成 | hybrid_search + RRF + 衰减重排 |
| .env 密码 | ✅ 已修复 | `AGENT_MEMORY_SEEKDB_PASSWORD` 已写入 .env |
| **端到端测试** | 🔄 待做 | 需启动 SeekDB + embedding server |
| memory_ops.py | ❌ 未实现 | 记忆提取/压缩/清理 |
| Fork/Merge 沙箱端点 | ❌ 未实现 | SeekDB COW 特性封装 |

### 基础设施

| 服务 | 端口 | 启动方式 |
|------|------|----------|
| SeekDB | 2881 | `D:\programs\seekdb\bin\seekdb.exe --service --base-dir=D:/mydata/seekdb --port=2881 --parameter memory_limit=2G --parameter cpu_count=4` |
| Embedding server (bge-m3) | 11435 | `cd D:\dev\lawgraph\embedding-server && npx tsx server.ts` |
| Agent Memory | 11436 | `cd D:\dev\lawgraph\agent-memory && .venv\Scripts\python.exe -m agent_memory.main` |
| SAG (知识检索) | 4173 | TypeScript/Fastify，PostgreSQL+pgvector |
| PostgreSQL | 5433 | 本机，db_user=odoo |

---

## 下一步计划（按优先级）

### P0 — 近期（本周可做）

1. **完成 agent-memory 端到端测试**
   - 前置：手动启动 SeekDB (2881) 和 embedding server (11435)
   - 启动 agent-memory (11436)
   - curl 跑通全部端点：create → search → get → update → delete → batch → conversations → health → stats
   - 验证 SeekDB 中的实际数据

2. **实现 `memory_ops.py`**
   - 记忆压缩：>7 天 + access_count>0 的记忆按 (agent_id, user_id) 分组 → LLM 总结
   - 过期清理：删除 expires_at 已过的记忆
   - 记忆提取：从对话内容中自动提取记忆（对接硅基流动 Qwen3）
   - 对应端点：`POST /v1/maintenance/compress`、`POST /v1/maintenance/cleanup`、`POST /v1/memories/extract`

3. **实现 Fork/Merge 沙箱端点**
   - `POST /v1/fork` — fork database 用于 agent 试探性推理
   - `POST /v1/merge` — 合并沙箱结果回主库（fail/theirs/ours 策略）
   - SeekDB AdminClient 的 `fork_database` / `delete_database` 封装

### P1 — 中期

4. **拆分 GitButler 虚拟分支**
   - codebuddy 分支 — CodeBuddy 相关 4 个 commit
   - dev-env 分支 — pyproject.toml、workspace 配置、tooling deps
   - docs 分支 — AGE/GraphRAG 文档、odoo_install
   - 各分支可独立 push/PR

5. **SAG + Agent Memory 联调**
   - SAG (4173) 负责知识检索，agent-memory (11436) 负责长期记忆
   - SAG 调 agent-memory 的 `/v1/memories/search` 获取用户偏好/历史
   - agent-memory 调 SAG 的检索接口补充语义记忆

### P2 — 远期

6. **Odoo ai.memory 桥接**
   - 写 `ai_seekdb_bridge` addon
   - Odoo `ai.memory` create/write hook → 异步推送到 agent-memory
   - Embedding 维度对齐（1536 vs 1024）
   - 双向查询支持（agent-memory 可选同时查 Odoo JSON-RPC）

7. **清理历史实验性文件**
   - 移除不再需要的 bmad、pyenv install、备份 test_packing.py 等临时 commit 内容

---

## odoo-ai 生态分析与启发（2026-07-02）

> 源码位置：`D:\odoochain\odoo-ai`（v3.0.1，作者 Geraldow / Alesco 秘鲁）

### 项目定位

Odoo 开发专用的 Claude Code 技能生态系统，把模块开发流程结构化为 **SDD（Spec-Driven Development）**——先规格后编码，多 agent 协作。

### 核心架构

| 层 | 组件 | 作用 |
|---|------|------|
| Skills 层 | 12 个 sdd-* 技能 + odoo-ai hub + odoo-contribute | Claude Code `/slash-command` 技能 |
| 记忆层 | **Engram**（Go，`engram.sh`） | 跨会话持久记忆，key-value 观察存储 |
| 代码索引层 | **CodeGraph** | tree-sitter AST 解析（我们已在用） |
| 编排层 | **Iris MCP Server** | 多 agent 编排（Claude / Antigravity / Codex / Copilot） |
| 同步层 | **engram-drive** | Google Drive 团队记忆共享 |

### SDD 工作流（9 阶段）

```
sdd-init → sdd-explore → sdd-propose → sdd-spec → sdd-design → sdd-tasks → sdd-apply → sdd-verify → sdd-archive
```

每阶段独立 skill（sub-agent），通过 Engram topic_key（`sdd/{change-name}/{phase}`）传递制品。另有 `sdd-ff`（快速跳过中间阶段）、`sdd-continue`（恢复中断）、`sdd-report`（生成报告）。

### 最精华的设计点

1. **Engram 记忆约定** — 确定性命名（`sdd/{change-name}/{artifact-type}`），两步恢复协议（`mem_search` → `mem_get_observation`），解决 LLM 上下文丢失的核心痛点
2. **持久化契约（Persistence Contract）** — 三种模式（engram / openspec / none），每个 skill 统一遵循
3. **RULES.md 规则系统** — 13 条 Odoo 开发铁律（版本检测 R1、分支安全 R2、ACL 强制 R4、SQL 注入防护 R13、Enterprise First R6/R10）
4. **skill-evolver** — 自进化：检测反复出现的模式 → 自动提议变成新 skill 规则
5. **Phase→Adapter 路由** — 不同阶段用不同 AI 引擎，静态路由降低 token 消耗

### Engram vs 我们的 Agent Memory 对比

| 维度 | Engram | Agent Memory（我们的） |
|------|--------|----------------------|
| 存储 | Go 本地进程，文件系统 | SeekDB（向量+全文+IK 中文分词） |
| 搜索 | 关键字匹配，topic_key 精确查找 | **hybrid_search（向量+全文+RRF 融合）** |
| 中文 | 无特殊支持 | **IK 分词器原生支持** |
| 团队共享 | Google Drive 文件同步 | REST API，多客户端可直连 |
| 沙箱 | 无 | **SeekDB Fork/Merge COW** |
| 衰减排序 | 无 | Odoo ai.memory 兼容的 effective_weight 衰减 |

### 可借鉴落地的设计

#### 1. topic_key 结构化命名空间（优先级：高）

Engram 的确定性命名（`sdd/{change}/proposal`）让记忆检索从模糊搜索变为精确匹配。我们的 agent-memory metadata 里应增加 `topic_key` 字段：

```python
# models.py — MemoryCreate 增加
topic_key: str | None = None  # 结构化命名空间，如 "sdd/add-contract-module/spec"
```

```python
# store.py — metadata 增加 topic_key
meta["topic_key"] = req.topic_key or ""
```

```python
# search.py — 支持按 topic_key 精确检索
if req.topic_key:
    where_filter["$and"].append({"topic_key": {"$eq": req.topic_key}})
```

这使得 agent-memory 既支持模糊语义搜索（hybrid_search），又支持确定性精确检索（topic_key），比纯 Engram 更灵活。

#### 2. RULES.md 规则整合到 CLAUDE.md（优先级：高）

从 odoo-ai 的 R1-R13 中筛选适用于我们 Odoo 19 开发的规则，整合到 `D:\odoochain\odoo19\CLAUDE.md`：

- **R1 版本检测** — 读 `__manifest__.py` 确认版本再写代码
- **R4 ACL 强制** — 新模型必须有 `ir.model.access.csv`
- **R5 pre-migrate** — 版本 bump + XML 修改时强制写迁移脚本
- **R6 Enterprise First** — 搜索 API 时先查 Enterprise 源码
- **R7 代码标准** — `@api.model_create_multi`、`_("text")` 不用 f-string、`t-out` 替代 `t-raw`
- **R13 安全** — SQL 参数化、sudo() 最小范围、controller auth 显式声明

#### 3. SDD 工作流复用（优先级：中）

两种路径：

- **路径 A — 直接安装 odoo-ai skills**：运行 `install.ps1`，获得完整 SDD 工作流。但依赖 Engram（Go），需要额外安装
- **路径 B — 用 agent-memory 替代 Engram 做后端**：修改 SDD skills 的持久化层，把 `mem_save/mem_search/mem_get_observation` 指向我们的 agent-memory REST API。这样 SDD 工作流获得向量搜索+中文分词+沙箱能力

推荐 **先 A 后 B**：先安装验证 SDD 工作流的价值，再逐步替换后端。

#### 4. skill-evolver 自进化机制（优先级：中低）

`/skill-evolve "描述"` 自动检测重复模式并提议新规则。这个思路可以和 agent-memory 结合：
- agent 把每次开发中的模式发现存入 agent-memory（memory_type=procedural）
- 定期查询 procedural 记忆中的高频模式
- 自动提议转化为 CLAUDE.md 规则或 skill

### 我们能超越 odoo-ai 的方向

1. **中文法律场景** — Engram 无中文分词，我们的 IK 分词器是原生优势
2. **Fork/Merge 沙箱** — agent 可以 fork 一份 memory 做试探性推理，Engram 没有这个能力
3. **Odoo 数据库桥接** — odoo-ai 的记忆完全外挂（Engram），不与 Odoo 数据库联通；我们计划做 ai.memory 双向同步
4. **向量语义搜索** — Engram 只有关键字匹配，我们的 hybrid_search（bge-m3 向量 + IK 全文 + RRF 融合）在语义理解上远超

### 行动项汇总

| # | 行动 | 优先级 | 依赖 |
|---|------|--------|------|
| A1 | agent-memory 增加 `topic_key` 字段 | P0 | ✅ 完成（2026-07-10，静态验证通过；端到端行为验证待服务启动） |
| A2 | 从 RULES.md 摘选规则写入 CLAUDE.md | P0 | ✅ 完成（2026-07-10，R1/R4/R5/R6/R7/R13 已本地化到 Odoo 19） |
| A3 | 运行 `install.ps1` 安装 odoo-ai skills | P1 | Engram + Go |
| A4 | 评估 Engram 安装（`go install engram`） | P1 | Go runtime |
| A5 | 设计 agent-memory 作为 SDD 持久化后端的适配层 | P1 | A1 + 端到端测试通过 |
| A6 | 借鉴 skill-evolver 做模式自动发现 | P2 | agent-memory 稳定运行 |

---

## 向量层选型决策：VexDB-Lite vs SeekDB（2026-07-12）

> 评估对象：`github.com/odoochain/VexDB-Lite`（fork 自清华 `VexDB-THU/VexDB-Lite`，
> 2026-07-11 建 fork；C/C++ 向量索引扩展，可插入 PG / DuckDB / SQLite；
> MIT 开源版 + 商用版 VexDB；当前无 release，上游仍活跃开发）

### 核心结论：各司其职（已采纳）

VexDB-Lite 与 SeekDB **不是同一层的东西，不能直接二选一替换**。

- **VexDB-Lite = 向量索引扩展**，对标 **pgvector**（其 README 的对比表就是 `pgvector vs vexdb-lite vs VexDB`）。
  强项：原生 PG 同库 + 自研 `graph_index` 图索引（比 pgvector 的 HNSW/IVFFlat 快）。
- **SeekDB = 多模态数据库**（OceanBase 内核），提供向量 + 全文 + SQL + 沙箱。

### 能力对比

| 维度 | pgvector | VexDB-Lite | SeekDB |
|------|:--:|:--:|:--:|
| 原生 PG 扩展（与 Odoo/SAG 同库） | ✅ | ✅ | ❌（独立服务 2881） |
| 向量 ANN 检索 | ✅ 基础 | ✅ 自研图索引，更快 | ✅ HNSW |
| 中文全文分词（IK） | ❌ | ❌ | ✅ 原生 |
| 混合检索（向量+全文 RRF） | ❌ | ❌ | ✅ 原生 |
| Fork/Merge 沙箱（COW） | ❌ | ❌ | ✅ 原生 |
| 成熟度 | 稳定 | fork 1 天 / 无 release / 需自编译 C++ PG 扩展 | 已装好跑通 |

### 分层定位（最终架构方向）

| 层 | 选型 | 理由 |
|----|------|------|
| **agent-memory**（长期记忆，11436） | **SeekDB 不变** | 中文法律记忆召回靠"向量 + IK 全文混合检索"，还要 Fork/Merge 沙箱；VexDB-Lite 这三样都没有。转 PG 路线需叠 `pg_jieba/zhparser` + 应用层自写 RRF = 重造 SeekDB 已有轮子。 |
| **SAG(4173) / Odoo ai.memory 向量层** | **VexDB-Lite 候选**（替换 pgvector） | 纯向量 + 要与 PG 业务数据同库 + 图索引比 pgvector 快；"原生 PG"优势在此才兑现。后续评估，非现在。 |

### 不现在把 memory 转 PG 的三个理由

1. VexDB-Lite 缺的正是当初选 SeekDB 的三个核心理由（中文全文、混合检索、沙箱）
2. 本项目在 **Windows** 开发，编译 C++ 的 PG 扩展并装进 PostgreSQL 折腾
3. odoochain 的 fork 才 1 天、上游无 release，暂不入核心链路

### 后续可选行动（不急）

| # | 行动 | 优先级 | 依赖 |
|---|------|--------|------|
| B1 | 在 SAG 的 PostgreSQL(5433) 上试装 VexDB-Lite 扩展跑 POC，实测 Windows 编译可行性 + 图索引 vs pgvector 性能 | P2 | 需要给 SAG 提速时 |
| B2 | 若 POC 通过，评估 SAG/Odoo 向量层从 pgvector 迁移到 VexDB-Lite | P2 | B1 通过 |

> 决策记忆：`memory/vexdb-lite-vs-seekdb-decision.md`

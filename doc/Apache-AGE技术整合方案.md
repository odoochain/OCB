# Apache AGE + GraphRAG 技术整合方案

> **整理日期**: 2026-06-21  
> **目标**: 在 odoo、lawgraph、lawpaddle 项目群中应用 AGE 图数据库和 GraphRAG 技术

---

## 一、现有项目生态概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        项目群架构                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌────────────────┐   │
│  │ lawPaddle       │    │ lawgraph        │    │ odoo/baraka    │   │
│  │ -desktop        │    │                 │    │                │   │
│  │ (Electron App)  │    │ - age-source    │    │ (法律实践管理) │   │
│  │                 │    │ - graphify      │    │ 530 tables     │   │
│  │ - freellmapi    │    │ - pgvector      │    │ AGE + pgvector │   │
│  │ - litellm       │    │ - Agent-Memory  │    │ 已启用         │   │
│  │ - headroom      │    │ - legal-skills  │    │                │   │
│  └────────┬────────┘    └────────┬────────┘    └────────┬───────┘   │
│           │                      │                      │           │
│           └──────────────────────┼──────────────────────┘           │
│                                  │                                  │
│                    ┌─────────────▼─────────────┐                    │
│                    │    PostgreSQL 18.4         │                    │
│                    │    ┌───────────────────┐   │                    │
│                    │    │ Apache AGE 1.7.0  │   │                    │
│                    │    │ pgvector 0.8.2    │   │                    │
│                    │    └───────────────────┘   │                    │
│                    └───────────────────────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 二、整合机会分析

### 2.1 graphify + Apache AGE

**现状**: graphify 使用 NetworkX 在内存中构建代码知识图谱，输出 JSON/SVG/Obsidian。

**整合方案**: 将图谱持久化到 AGE，支持 Cypher 查询。

```
graphify 流程:
detect() → extract() → build_graph() → cluster() → analyze() → report()

整合后:
detect() → extract() → build_graph() → cluster() → analyze() → report()
                                         │
                                         ▼
                                    ┌─────────┐
                                    │  AGE    │
                                    │ (持久化) │
                                    └─────────┘
                                         │
                                         ▼
                                    Cypher 查询
```

**具体实现**:
```python
# graphify/export.py 新增 AGE 导出
def export_to_age(G, graph_name):
    """将 NetworkX 图导出到 Apache AGE"""
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # 创建图
            cur.execute(f"SELECT create_graph('{graph_name}')")
            
            # 批量创建节点
            for node, attrs in G.nodes(data=True):
                cur.execute(f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        CREATE (n:CodeNode {{id: %s, label: %s, type: %s}})
                    $$) AS (v agtype)
                """, (node, attrs.get('label', ''), attrs.get('type', '')))
            
            # 批量创建边
            for src, dst, attrs in G.edges(data=True):
                cur.execute(f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (a {{id: %s}}), (b {{id: %s}})
                        CREATE (a)-[:{attrs['relation'].upper()}]->(b)
                    $$) AS (r agtype)
                """, (src, dst))
```

**收益**:
- 图谱持久化，支持跨 session 查询
- Cypher 支持多跳查询：`MATCH (a)-[*2..3]->(b) RETURN path`
- 与 SQL 混合查询：图数据 + 关系数据联合分析

---

### 2.2 TencentDB-Agent-Memory + AGE

**现状**: 四层记忆系统（L0 对话捕获 → L1 记忆提取 → L2 场景归纳 → L3 用户画像），使用 SQLite 或腾讯云向量数据库。

**整合方案**: 用 AGE 存储记忆之间的关系网络。

```
当前存储:
┌──────────────┐
│ SQLite/TVCDB │ ← 向量搜索 + 关键词
│ (记忆条目)   │
└──────────────┘

整合后:
┌──────────────┐    ┌──────────────────┐
│ SQLite/TVCDB │    │ Apache AGE       │
│ (记忆内容)   │    │ (记忆关系图)     │
│ (向量索引)   │    │                  │
└──────────────┘    │ Memory -[RELATES_TO]-> Memory
                    │ Memory -[MENTIONS]-> Entity
                    │ Memory -[FROM_SESSION]-> Session
                    └──────────────────┘
```

**具体实现**:
```sql
-- 在 baraka 数据库中创建 Agent 记忆图
SELECT create_graph('agent_memory');

-- 记忆关系表
CREATE TABLE agent_memory.memories (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    memory_type TEXT,  -- L0/L1/L2/L3
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 实体抽取后存入图
CREATE OR REPLACE FUNCTION agent_memory.build_memory_graph(memory_id BIGINT)
RETURNS VOID AS $$
BEGIN
    -- 从记忆内容中抽取实体
    -- 在 AGE 中创建节点和关系
    PERFORM * FROM cypher('agent_memory', format($$
        MERGE (m:Memory {id: %s})
        SET m.content = %L, m.type = %L
    $$, memory_id, content, memory_type)) AS (v agtype);
END;
$$ LANGUAGE plpgsql;
```

**收益**:
- 记忆之间的关系可视化
- 多跳推理：`这个用户的偏好为什么变了？` → 追溯记忆链条
- 与 GraphRAG 结合：向量召回 + 图推理

---

### 2.3 Odoo/baraka + AGE

**现状**: baraka 数据库包含 530 张 Odoo 表，涵盖账户、产品、合作伙伴、消息等。

**整合方案**: 构建法律业务知识图谱。

```
当前关系表:
┌─────────────────┐    ┌─────────────────┐
│ res_partner     │    │ account_move     │
│ (合作伙伴)      │───▶│ (会计凭证)      │
└─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│ mail_message    │
│ (消息记录)      │
└─────────────────┘

整合后 AGE 图谱:
┌─────────────────────────────────────────────────────────┐
│                    legal_knowledge                      │
│                                                         │
│  (Client)-[:HAS_CASE]->(Case)-[:INVOLVES]->(Party)     │
│       │                    │                            │
│       │                    ▼                            │
│       │              (Document)-[:CITES]->(Law)         │
│       │                    │                            │
│       ▼                    ▼                            │
│  (Contact)-[:WORKS_AT]->(Company)                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**具体实现**:
```sql
-- 创建法律知识图谱
SELECT create_graph('legal_knowledge');

-- 从 Odoo 数据构建图谱
CREATE OR REPLACE FUNCTION legal_knowledge.build_from_odoo()
RETURNS VOID AS $$
BEGIN
    -- 客户节点
    PERFORM * FROM cypher('legal_knowledge', $$
        MATCH (p:res_partner)
        WHERE p.is_company = false
        CREATE (c:Client {name: p.name, email: p.email})
    $$) AS (v agtype);

    -- 公司节点
    PERFORM * FROM cypher('legal_knowledge', $$
        MATCH (p:res_partner)
        WHERE p.is_company = true
        CREATE (co:Company {name: p.name})
    $$) AS (v agtype);

    -- 案件关系（假设已有案件表）
    PERFORM * FROM cypher('legal_knowledge', $$
        MATCH (c:Client), (ca:Case)
        WHERE c.name = ca.client_name
        CREATE (c)-[:HAS_CASE]->(ca)
    $$) AS (r agtype);
END;
$$ LANGUAGE plpgsql;
```

**收益**:
- 客户关系网络可视化
- 案件关联分析：`这个客户还有哪些相关案件？`
- 文档引用图谱：`哪些案件引用了这条法规？`

---

### 2.4 Legal Skill Packs + GraphRAG

**现状**: lawgraph 下有多个法律 AI 技能包（诉讼、公司、知识产权等）。

**整合方案**: 为法律 AI Agent 添加 GraphRAG 能力。

```
当前流程:
用户问题 → 向量搜索 → LLM 生成回答

整合后 GraphRAG 流程:
用户问题 → 实体识别 → 图检索 + 向量检索 → 融合生成
              │              │         │
              ▼              ▼         ▼
         法律实体        关系链    相关文档
         (案例/法条)    (引用/修订) (判决书)
```

**具体实现**:
```sql
-- 法律知识图谱
SELECT create_graph('legal_graphrag');

-- 法规节点
CREATE TABLE legal_graphrag.laws (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    article TEXT,
    content TEXT,
    embedding vector(1024)
);

-- 案例节点
CREATE TABLE legal_graphrag.cases (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    title TEXT,
    judgment_date DATE,
    embedding vector(1024)
);

-- 法律 GraphRAG 检索函数
CREATE OR REPLACE FUNCTION legal_graphrag.hybrid_retrieve(query TEXT, top_k INT DEFAULT 5)
RETURNS TABLE(source TEXT, content TEXT, score FLOAT) AS $$
BEGIN
    -- 向量检索相关法规
    RETURN QUERY
    SELECT 'law'::TEXT, l.content,
           (1 - (l.embedding <=> get_embedding(query)))::FLOAT
    FROM legal_graphrag.laws l
    ORDER BY l.embedding <=> get_embedding(query)
    LIMIT top_k;

    -- 图检索相关案例引用链
    RETURN QUERY
    SELECT 'case'::TEXT,
           (c.title || ' 引用 ' || l.name)::TEXT,
           0.8::FLOAT
    FROM cypher('legal_graphrag', format($$
        MATCH (c:Case)-[:CITES]->(l:Law)
        WHERE l.name CONTAINS %L
        RETURN c, l
        LIMIT %s
    $$, query, top_k)) AS (c agtype, l agtype);
END;
$$ LANGUAGE plpgsql;
```

**收益**:
- 法律推理更精准：结合法条引用关系
- 多跳推理：`这条法规被哪些案例引用？引用它的案例判决结果如何？`
- 知识更新：法规修订时自动更新关联图谱

---

## 三、实施优先级

| 优先级 | 整合项 | 难度 | 收益 | 建议 |
|--------|--------|------|------|------|
| P0 | baraka + AGE 法律图谱 | ⭐⭐ | ⭐⭐⭐ | 立即开始，数据已就绪 |
| P1 | Agent-Memory + AGE | ⭐⭐⭐ | ⭐⭐⭐ | 提升 Agent 记忆推理能力 |
| P2 | Legal Skill + GraphRAG | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 法律 AI 核心能力 |
| P3 | graphify + AGE | ⭐⭐ | ⭐⭐ | 代码知识图谱持久化 |

## 四、快速启动：baraka 法律图谱

```sql
-- 1. 创建图谱
SELECT create_graph('legal_knowledge');

-- 2. 从 res_partner 构建客户/公司节点
SELECT * FROM cypher('legal_knowledge', $$
    MATCH (p:res_partner {is_company: false})
    CREATE (c:Client {name: p.name, id: p.id})
    RETURN c
$$) AS (client agtype);

-- 3. 查询客户关系
SELECT * FROM cypher('legal_knowledge', $$
    MATCH (c:Client)-[r]->(n)
    RETURN c.name, type(r), labels(n)
$$) AS (client agtype, rel agtype, target agtype);
```

## 五、下一步行动

1. **立即**: 在 baraka 数据库中创建法律知识图谱原型
2. **本周**: 完成 Agent-Memory + AGE 集成方案设计
3. **下周**: 为 Legal Skill Pack 添加 GraphRAG 检索函数
4. **持续**: 优化图谱性能，添加索引和分区

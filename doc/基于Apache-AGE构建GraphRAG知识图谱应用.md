# 基于 Apache AGE 构建 GraphRAG 知识图谱应用

> **来源**: 腾讯云 - 云数据库 PostgreSQL AI 能力  
> **原文**: https://www.tencentcloud.com/zh/document/product/409/80412  
> **整理日期**: 2026-06-21

---

## 概述

GraphRAG 是将知识图谱与 RAG 结合的高级检索范式。通过实体抽取构建知识图谱（存储在 Apache AGE 中），结合向量检索（pgvector），实现比纯向量 RAG 更精准的多跳推理能力。

## GraphRAG vs 传统 RAG

| 维度 | 传统 RAG | GraphRAG |
|------|----------|----------|
| 检索方式 | 纯向量相似度 | 图遍历 + 向量混合 |
| 多跳推理 | 不支持 | 通过图关系推理 |
| 实体关系 | 隐含在文本中 | 显式存储为图结构 |
| 全局理解 | 局限于单个 chunk | 通过图获得全局视角 |
| 适用场景 | 简单问答 | 复杂推理、关系查询 |

## 架构设计

```
┌──────────────────────────────────────────────────────┐
│                GraphRAG 系统                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  文档输入 → 实体抽取 → 图谱构建 → 索引建立           │
│                                                      │
│  用户查询 → 实体识别 → 图检索 + 向量检索 → 融合生成   │
│                                                      │
├──────────────────────────────────────────────────────┤
│  存储层                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐   │
│  │ Apache AGE   │  │ pgvector     │  │ 关系表    │   │
│  │ (知识图谱)   │  │ (文档向量)   │  │ (元数据)  │   │
│  └──────────────┘  └──────────────┘  └───────────┘   │
│                                                      │
│  AI 层                                               │
│  ┌─────────────────────────────────────────────┐     │
│  │ tencentdb_ai（实体抽取 / 关系识别 / 生成）  │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

## 数据库准备

```sql
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- 设置 search_path
SET search_path = ag_catalog, "$user", public;

-- 创建知识图谱
SELECT create_graph('knowledge_graph');

-- 文档存储表
CREATE TABLE graphrag.documents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON graphrag.documents
USING hnsw (embedding vector_cosine_ops);

-- 实体表（辅助索引）
CREATE TABLE graphrag.entities (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT,
    embedding vector(1024),
    source_doc_id BIGINT REFERENCES graphrag.documents(id),
    UNIQUE(name, entity_type)
);

CREATE INDEX ON graphrag.entities
USING hnsw (embedding vector_cosine_ops);
```

> **注意**: 向量维度需与使用的大模型输出维度一致。常见模型维度：
> - OpenAI text-embedding-3-small：1536维
> - BGE-M3：1024维
> - ChatGLM Embedding：1024维

## 核心流程

### 1. 实体抽取

```sql
-- 使用大模型从文档中抽取实体和关系
CREATE OR REPLACE FUNCTION graphrag.extract_entities(doc_content TEXT)
RETURNS JSONB AS $$
DECLARE
    result TEXT;
BEGIN
    SELECT tencentdb_ai.chat_completions(
        '<your-llm-model>',
        '请从以下文本中抽取实体和关系，以 JSON 格式返回。' ||
        '格式：{"entities": [{"name": "实体名", "type": "类型", "description": "描述"}], ' ||
        '"relations": [{"source": "源实体", "target": "目标实体", "relation": "关系类型", "description": "描述"}]}' ||
        E'\n\n文本：' || doc_content
    ) INTO result;

    RETURN result::JSONB;
END;
$$ LANGUAGE plpgsql;
```

### 2. 图谱构建（含安全校验）

来自 LLM 的 `entity.type` / `relation.relation` 会作为 Cypher 标签拼入查询，**必须使用白名单校验**，禁止任意字符串进入 Cypher：

```sql
-- 允许的实体类型与关系类型白名单
CREATE TABLE IF NOT EXISTS graphrag.allowed_entity_types (type TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS graphrag.allowed_relation_types (type TEXT PRIMARY KEY);

INSERT INTO graphrag.allowed_entity_types(type) VALUES
    ('Person'), ('Company'), ('Product'), ('Technology'), ('Concept')
ON CONFLICT DO NOTHING;

INSERT INTO graphrag.allowed_relation_types(type) VALUES
    ('WORKS_AT'), ('USES'), ('HAS_FEATURE'), ('RELATED_TO'), ('PART_OF')
ON CONFLICT DO NOTHING;

-- 将抽取的实体存入图
CREATE OR REPLACE FUNCTION graphrag.build_graph(doc_id BIGINT)
RETURNS VOID AS $$
DECLARE
    doc_content TEXT;
    extracted JSONB;
    entity JSONB;
    relation JSONB;
    e_type TEXT;
    r_type TEXT;
BEGIN
    SELECT content INTO doc_content FROM graphrag.documents WHERE id = doc_id;
    extracted := graphrag.extract_entities(doc_content);

    -- 创建实体节点（白名单校验类型）
    FOR entity IN SELECT * FROM jsonb_array_elements(extracted->'entities')
    LOOP
        e_type := entity->>'type';
        IF NOT EXISTS (SELECT 1 FROM graphrag.allowed_entity_types WHERE type = e_type) THEN
            RAISE NOTICE 'Skip entity with disallowed type: %', e_type;
            CONTINUE;
        END IF;

        PERFORM * FROM cypher('knowledge_graph', format($$
            MERGE (n:%I {name: %L})
            SET n.description = %L, n.doc_id = %s
        $$, e_type, entity->>'name', entity->>'description', doc_id))
        AS (v agtype);
    END LOOP;

    -- 创建关系（白名单校验关系类型）
    FOR relation IN SELECT * FROM jsonb_array_elements(extracted->'relations')
    LOOP
        r_type := relation->>'relation';
        IF NOT EXISTS (SELECT 1 FROM graphrag.allowed_relation_types WHERE type = r_type) THEN
            RAISE NOTICE 'Skip relation with disallowed type: %', r_type;
            CONTINUE;
        END IF;

        PERFORM * FROM cypher('knowledge_graph', format($$
            MATCH (a {name: %L}), (b {name: %L})
            MERGE (a)-[r:%I]->(b)
            SET r.description = %L
        $$, relation->>'source', relation->>'target',
            r_type, relation->>'description'))
        AS (r agtype);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

**关键安全点**：
- 节点标签 / 关系类型：使用 `%I` 安全标识符 + 白名单双重校验
- 属性值：使用 `%L` 安全转义
- 不通过白名单：直接跳过并打日志，不允许任意字符串落入 Cypher

### 3. GraphRAG 检索

```sql
-- 混合检索：图遍历 + 向量搜索
CREATE OR REPLACE FUNCTION graphrag.hybrid_retrieve(query TEXT, top_k INT DEFAULT 5)
RETURNS TABLE(source TEXT, content TEXT, score FLOAT) AS $$
BEGIN
    -- 向量检索文档
    RETURN QUERY
    SELECT 'vector'::TEXT, d.content,
           (1 - (d.embedding <=> tencentdb_ai.get_embedding('bge-m3', query)))::FLOAT
    FROM graphrag.documents d
    ORDER BY d.embedding <=> tencentdb_ai.get_embedding('bge-m3', query)
    LIMIT top_k;

    -- 图检索相关实体
    RETURN QUERY
    SELECT 'graph'::TEXT,
           (a->>'name' || ' --[' || r->>'relation' || ']--> ' || b->>'name')::TEXT,
           0.8::FLOAT
    FROM cypher('knowledge_graph', format($$
        MATCH (a)-[r]->(b)
        WHERE a.name CONTAINS %L OR b.name CONTAINS %L
        RETURN properties(a) as a, properties(r) as r, properties(b) as b
        LIMIT %s
    $$, query, query, top_k)) AS (a agtype, r agtype, b agtype);
END;
$$ LANGUAGE plpgsql;
```

### 4. 生成回答

```sql
-- GraphRAG 问答
CREATE OR REPLACE FUNCTION graphrag.answer(question TEXT)
RETURNS TEXT AS $$
DECLARE
    context TEXT;
    answer TEXT;
BEGIN
    SELECT string_agg('[' || source || '] ' || content, E'\n')
    INTO context
    FROM graphrag.hybrid_retrieve(question, 5);

    SELECT tencentdb_ai.chat_completions(
        '<your-llm-model>',
        '基于以下知识图谱信息和文档内容回答问题。图谱信息标记为 [graph]，文档内容标记为 [vector]。' ||
        E'\n\n上下文：\n' || COALESCE(context, '无') ||
        E'\n\n问题：' || question
    ) INTO answer;

    RETURN answer;
END;
$$ LANGUAGE plpgsql;
```

## 使用示例

```sql
-- 导入文档并构建图谱
INSERT INTO graphrag.documents (title, content, embedding)
VALUES (
    'PostgreSQL 与 AI',
    '腾讯云 PostgreSQL 通过 tencentdb_ai 插件支持在 SQL 中直接调用大模型...',
    tencentdb_ai.get_embedding('bge-m3', '腾讯云 PostgreSQL 通过 tencentdb_ai 插件支持在 SQL 中直接调用大模型')
);

-- 构建图谱
SELECT graphrag.build_graph(1);

-- GraphRAG 问答
SELECT graphrag.answer('PostgreSQL 支持哪些 AI 能力？');
```

## 实践建议

1. **实体去重**：使用 `MERGE` 避免重复实体
2. **增量更新**：新文档只增量构建，不全量重建
3. **图索引**：为频繁查询的属性创建索引
4. **社区发现**：利用图算法做文档聚类
5. **混合召回**：图上下文 + 向量文档互补
6. **白名单保护**：实体类型 / 关系类型必须经过白名单，杜绝来自 LLM 的任意字符串注入

## 相关文档

- [Apache AGE 图数据库使用指南](https://www.tencentcloud.com/document/product/409/80361)
- [pgvector 向量扩展使用指南](https://www.tencentcloud.com/document/product/409/80360)
- [tencentdb_ai 插件功能介绍](https://www.tencentcloud.com/document/product/409/72652)

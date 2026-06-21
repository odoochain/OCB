# Apache AGE 图数据库使用指南

> **来源**: 腾讯云 - 云数据库 PostgreSQL AI 能力  
> **原文**: https://www.tencentcloud.com/zh/document/product/409/80361  
> **整理日期**: 2026-06-21

---

## 概述

Apache AGE（A Graph Extension）是 PostgreSQL 的图数据库扩展，允许在 PostgreSQL 中使用 openCypher 查询语言进行图数据的存储和查询。

**核心特点**：
- 在 PostgreSQL 内原生支持属性图模型
- 使用 openCypher 语法（兼容 Neo4j 查询语法）
- 可与 SQL 混合查询，实现图 + 关系数据联合分析
- 支持 ACID 事务

## 前提条件

云数据库 PostgreSQL 实例版本 ≥ 13。

## 安装与启用

```sql
-- 创建 Apache AGE 扩展
CREATE EXTENSION IF NOT EXISTS age;

-- 将 ag_catalog 加入 search_path
SET search_path = ag_catalog, "$user", public;

-- 或永久设置（推荐）
ALTER DATABASE mydb SET search_path = ag_catalog, "$user", public;
```

## 核心概念

| 概念 | 说明 |
|------|------|
| Graph（图） | 一个命名的图空间，包含节点和边 |
| Vertex（节点） | 图中的实体，可带标签和属性 |
| Edge（边） | 节点之间的关系，有方向、可带属性 |
| Label（标签） | 节点或边的类型分类 |
| Property（属性） | 节点或边上的 key-value 键值对 |

## 图操作

### 创建图

```sql
SELECT create_graph('knowledge_graph');
```

### 创建节点

```sql
-- 创建带标签和属性的节点
SELECT * FROM cypher('knowledge_graph', $$
    CREATE (n:Person {name: '张三', age: 30, role: 'Engineer'})
    RETURN n
$$) AS (node agtype);

-- 批量创建节点
SELECT * FROM cypher('knowledge_graph', $$
    CREATE (a:Person {name: '李四', role: 'Manager'}),
           (b:Company {name: '腾讯云', industry: 'Cloud'}),
           (c:Technology {name: 'PostgreSQL', type: 'Database'})
    RETURN a, b, c
$$) AS (a agtype, b agtype, c agtype);
```

### 创建关系（边）

```sql
-- 创建节点之间的关系
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person {name: '张三'}), (c:Company {name: '腾讯云'})
    CREATE (p)-[r:WORKS_AT {since: '2020-01-01'}]->(c)
    RETURN r
$$) AS (rel agtype);

-- 创建使用关系
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person {name: '张三'}), (t:Technology {name: 'PostgreSQL'})
    CREATE (p)-[r:USES {level: 'expert'}]->(t)
    RETURN r
$$) AS (rel agtype);
```

### 查询

```sql
-- 查找所有 Person 节点
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (n:Person)
    RETURN n.name, n.role
$$) AS (name agtype, role agtype);

-- 查找关系路径
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person)-[r:WORKS_AT]->(c:Company)
    RETURN p.name, c.name, r.since
$$) AS (person agtype, company agtype, since agtype);

-- 多跳查询
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person)-[:WORKS_AT]->(c:Company),
          (p)-[:USES]->(t:Technology)
    RETURN p.name, c.name, t.name
$$) AS (person agtype, company agtype, tech agtype);

-- 路径查询（2-3 跳）
SELECT * FROM cypher('knowledge_graph', $$
    MATCH path = (a:Person)-[*2..3]->(b)
    RETURN path
$$) AS (path agtype);
```

### 更新与删除

```sql
-- 更新节点属性
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person {name: '张三'})
    SET p.age = 31
    RETURN p
$$) AS (node agtype);

-- 删除关系
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person {name: '张三'})-[r:USES]->(t:Technology)
    DELETE r
$$) AS (result agtype);

-- 删除节点（需先删除关联的边）
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (t:Technology {name: 'PostgreSQL'})
    DETACH DELETE t
$$) AS (result agtype);
```

## SQL 与 Cypher 混合查询

Apache AGE 的强大之处在于可以将图查询结果与关系表 JOIN：

```sql
-- 图查询结果与关系表联合
SELECT g.person_name, u.email, u.department
FROM (
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (p:Person)-[:WORKS_AT]->(c:Company {name: '腾讯云'})
        RETURN p.name AS person_name
    $$) AS (person_name agtype)
) g
JOIN users u ON u.name = g.person_name::text;
```

## 典型应用场景

### 知识图谱

```sql
-- 构建产品知识图谱
SELECT create_graph('product_kg');

SELECT * FROM cypher('product_kg', $$
    CREATE (pg:Product {name: 'PostgreSQL', category: 'Database'}),
           (vec:Feature {name: '向量检索', desc: '基于 pgvector'}),
           (ai:Feature {name: 'AI 调用', desc: '基于 tencentdb_ai'}),
           (pg)-[:HAS_FEATURE]->(vec),
           (pg)-[:HAS_FEATURE]->(ai)
    RETURN pg, vec, ai
$$) AS (pg agtype, vec agtype, ai agtype);
```

### GraphRAG（图增强的 RAG）

```
-- 实体提取后存入图，检索时图 + 向量混合召回：
-- 1. 向量召回相关文档
-- 2. 从图中找到相关实体的关系链
-- 3. 将图上下文 + 文档内容一起送给大模型
```

### Agent 记忆关系图

```sql
-- 记录 Agent 之间的交互关系
SELECT * FROM cypher('agent_memory', $$
    CREATE (a1:Agent {name: 'Planner', role: 'planning'}),
           (a2:Agent {name: 'Researcher', role: 'research'}),
           (a1)-[:DELEGATES {task: '调研竞品', timestamp: '2026-01-15'}]->(a2)
    RETURN a1, a2
$$) AS (a1 agtype, a2 agtype);
```

## 性能建议

1. **创建索引**：为频繁查询的属性创建索引
   ```sql
   CREATE INDEX ON knowledge_graph."Person" ((properties->>'name'));
   ```

2. **限制跳数**：合理设置路径查询的跳数上限，避免全图遍历

3. **分区存储**：大规模图建议分区存储

## 注意事项

- 需要将 `ag_catalog` 添加到 `search_path`
- Cypher 查询通过 `cypher()` 函数调用，结果需要指定列类型
- 所有 Cypher 返回值类型为 `agtype`（Apache AGE 自定义的 JSON-like 类型）

## 相关文档

- [pgvector 向量扩展使用指南](https://www.tencentcloud.com/document/product/409/80360)
- [基于 Apache AGE 构建 GraphRAG 知识图谱应用](https://www.tencentcloud.com/document/product/409/80412)
- [Apache AGE 官方文档](https://age.apache.org/age-manual/master/index.html)
- [openCypher 规范](https://opencypher.org/)

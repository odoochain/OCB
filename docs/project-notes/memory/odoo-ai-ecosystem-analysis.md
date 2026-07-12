---
name: odoo-ai-ecosystem-analysis
description: odoo-ai v3 生态分析：SDD 工作流、Engram 记忆系统、RULES.md 规则体系，以及对我们 agent-memory 项目的启发
metadata: 
  node_type: memory
  type: project
  originSessionId: 8dea7d62-474f-4991-b0f2-eb987206cc4c
---

odoo-ai（v3.0.1，`D:\odoochain\odoo-ai`）是 Odoo 开发专用的 Claude Code 技能生态，核心是 SDD（Spec-Driven Development）工作流 + Engram 跨会话记忆 + CodeGraph AST 索引。

**Why:** 其 SDD 工作流（9 阶段：init→explore→propose→spec→design→tasks→apply→verify→archive）和 RULES.md 规则体系（R1-R13）对我们的 Odoo 19 开发有直接参考价值。Engram 的确定性 topic_key 命名约定（`sdd/{change}/{phase}`）解决了 LLM 上下文丢失问题，但其搜索能力（纯关键字）弱于我们的 agent-memory（hybrid_search + IK 中文分词）。

**How to apply:**
- 在 agent-memory 的 metadata 中增加 `topic_key` 字段，支持确定性精确检索
- 从 RULES.md 摘选 R1（版本检测）、R4（ACL 强制）、R5（pre-migrate）、R7（代码标准）、R13（安全）整合到 CLAUDE.md
- 考虑安装 odoo-ai skills（`install.ps1`）获得 SDD 工作流，长期用 agent-memory 替代 Engram 做后端
- 详细对比和行动项见计划文档 [[sag-setup-status]]

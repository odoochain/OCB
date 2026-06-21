# CodeBuddy Agent SDK 集成文档

## 概述

在 Odoo 19 项目中集成 CodeBuddy AI 编程助手，支持两种调用模式：
- **HTTP API 模式**：直接调用 CodeBuddy REST API（推荐）
- **SDK 模式**：通过 `codebuddy-agent-sdk` 调用

两种模式均支持 Token 自动刷新。

---

## 开发过程

### 1. 安装 SDK

```bash
uv add codebuddy-agent-sdk>=0.3.176
```

SDK 自带 `codebuddy-headless.exe` CLI 二进制（约 148MB），位于：
```
.venv/Lib/site-packages/codebuddy_agent_sdk/bin/codebuddy-headless.exe
```

### 2. 研究认证方式

通过分析 `xz-copilot-hub` 项目，发现 CodeBuddy 支持两种认证方式：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **API Key** | 通过 `CODEBUDDY_API_KEY` 环境变量 | SDK 模式 |
| **Bearer Token** | 通过 `Authorization: Bearer <token>` 请求头 | HTTP API 模式 |

HTTP API 端点（OpenAI 兼容格式）：
- 内网：`https://copilot.tencent.com/v2/chat/completions`
- 公网：`https://www.codebuddy.ai/v2/chat/completions`

### 3. 实现统一适配器

创建 `codebuddy_adapter.py`，封装两种模式的调用逻辑：

```
codebuddy_adapter.py
├── CodeBuddyConfig        # 配置管理
├── CodeBuddyAuth          # OAuth 认证流程
│   ├── start_auth()       # 获取认证 URL
│   ├── poll_token()       # 轮询 token
│   ├── save_token()       # 保存 token 到文件
│   ├── refresh_token()    # 刷新 token
│   └── authenticate()     # 完整认证流程
├── CodeBuddyHTTPClient    # HTTP API 调用
│   ├── query()            # 流式查询（自动刷新）
│   └── query_text()       # 文本查询
├── CodeBuddySDKClient     # SDK 调用
└── CodeBuddyClient        # 统一入口
```

### 4. 实现 Token 自动刷新

触发条件：API 返回 `401` 或 `429` 时自动触发刷新

刷新策略：
1. 优先使用 `refresh_token` 静默刷新
2. 无 `refresh_token` 时，打开浏览器交互式登录
3. 只重试一次，避免死循环

---

## 文件结构

```
odoo19/
├── .env                          # 环境变量配置
├── .codebuddy_creds/             # Token 凭证目录（已加入 .gitignore）
│   └── codebuddy_token_1.json    # Token 文件
├── codebuddy_adapter.py          # 统一适配器
├── codebuddy_cli.py              # CLI 入口
└── docs/
    └── codebuddy-integration.md  # 本文档
```

---

## 配置

### 环境变量（.env）

```bash
# 认证模式：auto | api_key | token | sdk
CODEBUDDY_AUTH_MODE=api_key

# API Key（api_key 模式使用）
CODEBUDDY_API_KEY=ck_xxx

# 网络环境：internal | ioa | public
CODEBUDDY_INTERNET_ENVIRONMENT=internal

# Token 凭证目录（token 模式使用，可选）
CODEBUDDY_CREDS_DIR=D:\dev\lawpaddle\xz-copilot-hub\.codebuddy_creds

# 模型
CODEBUDDY_MODEL=glm-5.1

# 自动刷新开关
CODEBUDDY_AUTO_REFRESH=true
```

### Token 文件格式

```json
{
    "bearer_token": "ck_fpqq5q8gf6rk.xxx",
    "user_id": "0c027598-f00b-4515-b6a7-156b34685180",
    "created_at": 1781990563,
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "...",
    "session_state": "...",
    "scope": "...",
    "domain": "..."
}
```

---

## 使用方法

### CLI 命令

```bash
# 交互式登录获取 token
python codebuddy_cli.py auth

# 查看 token 状态
python codebuddy_cli.py status

# 提问（429/401 时自动刷新）
python codebuddy_cli.py "解释Odoo的ORM机制"
```

### Python 代码调用

```python
import asyncio
from codebuddy_adapter import CodeBuddyClient, load_config

async def main():
    config = load_config()
    client = CodeBuddyClient(config)

    # 单次查询
    result = await client.query_text("你的问题")
    print(result)

    # 流式查询
    async for chunk in client.query_stream(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你的问题"},
        ]
    ):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

### 在 Odoo 模块中调用

```python
from odoo import models, api
from codebuddy_adapter import CodeBuddyClient, load_config

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def ask_codebuddy(self, question):
        config = load_config()
        client = CodeBuddyClient(config)
        return asyncio.run(client.query_text(question))
```

---

## 自动刷新机制

### 流程

```
API 请求 → 429/401 → 检查 refresh_token
                      ├── 有 → 调用 /v2/plugin/auth/refresh → 保存新 token → 重试
                      └── 无 → 打开浏览器交互式登录 → 保存新 token → 重试
```

### Token 过期判断

```python
# 提前 5 分钟视为过期
is_expired = time.time() >= (created_at + expires_in - 300)
```

---

## 可用模型

| 模型 ID | 说明 |
|---------|------|
| `glm-5.1` | GLM 5.1（默认） |
| `glm-5.0` | GLM 5.0 |
| `glm-5.0-turbo` | GLM 5.0 Turbo |
| `deepseek-v4-pro` | DeepSeek V4 Pro |
| `deepseek-v4-flash` | DeepSeek V4 Flash |
| `minimax-m3-play` | MiniMax M3 |
| `kimi-k2.6` | Kimi K2.6 |

---

## 故障排除

### 429 额度用尽

```
ValueError: CodeBuddy API error 429: 额度已用尽
```

**解决**：到 https://www.codebuddy.cn/profile/usage 充值

### Token 过期

自动刷新会触发：
1. 尝试 `refresh_token` 静默刷新
2. 失败则打开浏览器交互式登录

### SDK 模式 429

SDK 和 HTTP API 共享同一账户额度，充值后两种模式均可使用。

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `codebuddy_adapter.py` | 统一适配器（584 行） |
| `codebuddy_cli.py` | CLI 入口（65 行） |
| `.env` | 环境变量配置 |
| `.codebuddy_creds/*.json` | Token 凭证文件 |
| `.gitignore` | 已添加 `.codebuddy_creds/` |

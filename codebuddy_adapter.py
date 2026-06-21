"""CodeBuddy 统一适配器 — 支持 SDK 和 HTTP API 两种模式，含自动刷新"""

import os
import json
import time
import secrets
import base64
import uuid
import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# --- 配置 ---

CODEBUDDY_API_ENDPOINTS = {
    "internal": "https://copilot.tencent.com",
    "ioa": "https://copilot.tencent.com",
    "public": "https://www.codebuddy.ai",
}

DEFAULT_CREDS_DIR = Path(__file__).parent / ".codebuddy_creds"


@dataclass
class CodeBuddyConfig:
    auth_mode: str = "auto"           # "auto" | "api_key" | "token" | "sdk"
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    internet_env: str = "internal"    # "internal" | "ioa" | "public"
    api_endpoint: Optional[str] = None
    creds_dir: Optional[Path] = None
    model: str = "glm-5.1"
    max_turns: int = 10
    permission_mode: str = "bypassPermissions"
    auto_refresh: bool = True


def load_config() -> CodeBuddyConfig:
    """从环境变量加载配置"""
    return CodeBuddyConfig(
        auth_mode=os.getenv("CODEBUDDY_AUTH_MODE", "auto"),
        api_key=os.getenv("CODEBUDDY_API_KEY"),
        internet_env=os.getenv("CODEBUDDY_INTERNET_ENVIRONMENT", "internal"),
        api_endpoint=os.getenv("CODEBUDDY_API_ENDPOINT"),
        creds_dir=Path(os.getenv("CODEBUDDY_CREDS_DIR", str(DEFAULT_CREDS_DIR))),
        model=os.getenv("CODEBUDDY_MODEL", "glm-5.1"),
        auto_refresh=os.getenv("CODEBUDDY_AUTO_REFRESH", "true").lower() == "true",
    )


def get_api_endpoint(config: CodeBuddyConfig) -> str:
    if config.api_endpoint:
        return config.api_endpoint.rstrip("/")
    return CODEBUDDY_API_ENDPOINTS.get(config.internet_env, CODEBUDDY_API_ENDPOINTS["internal"])


# --- Token 文件管理 ---

@dataclass
class Credential:
    bearer_token: str
    user_id: str
    created_at: int
    file_path: Path
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None


def load_credentials(creds_dir: Path) -> List[Credential]:
    """加载所有 token 凭证文件"""
    creds = []
    if not creds_dir.exists():
        return creds

    for fp in sorted(creds_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if "bearer_token" in data:
                creds.append(Credential(
                    bearer_token=data["bearer_token"],
                    user_id=data.get("user_id", "unknown"),
                    created_at=data.get("created_at", 0),
                    file_path=fp,
                    expires_in=data.get("expires_in"),
                    refresh_token=data.get("refresh_token"),
                ))
        except Exception as e:
            logger.warning(f"Failed to load credential {fp.name}: {e}")
    return creds


def is_token_expired(cred: Credential) -> bool:
    """检查 token 是否过期"""
    if not cred.expires_in or not cred.created_at:
        return False  # 没有过期信息，假设未过期
    expiry_time = cred.created_at + cred.expires_in
    # 提前 5 分钟视为过期
    return time.time() >= (expiry_time - 300)


# Token 轮换状态
_token_index = 0


def get_next_bearer_token(config: CodeBuddyConfig) -> Optional[str]:
    """从凭证文件获取下一个可用的 bearer token（轮换）"""
    global _token_index
    creds_dir = config.creds_dir or DEFAULT_CREDS_DIR
    credentials = load_credentials(creds_dir)
    if not credentials:
        return None

    # 过滤掉过期的
    valid = [c for c in credentials if not is_token_expired(c)]
    if not valid:
        return credentials[0].bearer_token  # fallback

    # 轮换
    token = valid[_token_index % len(valid)].bearer_token
    _token_index += 1
    return token


# --- OAuth 认证流程 ---

class CodeBuddyAuth:
    """CodeBuddy OAuth 认证流程（基于 xz-copilot-hub 的实现）"""

    def __init__(self, config: CodeBuddyConfig):
        self.config = config
        self.base_url = get_api_endpoint(config)
        self.state_endpoint = f"{self.base_url}/v2/plugin/auth/state"
        self.token_endpoint = f"{self.base_url}/v2/plugin/auth/token"

    def _get_auth_headers(self, include_state: bool = False) -> Dict[str, str]:
        request_id = uuid.uuid4().hex
        headers = {
            "Host": httpx.URL(self.base_url).host,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json" if include_state else "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "close",
            "X-Requested-With": "XMLHttpRequest",
            "X-Domain": httpx.URL(self.base_url).host,
            "X-No-Authorization": "true",
            "X-No-User-Id": "true",
            "X-No-Enterprise-Id": "true",
            "X-No-Department-Info": "true",
            "User-Agent": "CLI/1.0.8 CodeBuddy/1.0.8",
            "X-Product": "SaaS",
            "X-Request-ID": request_id,
        }
        if include_state:
            span_id = secrets.token_hex(8)
            headers.update({
                "b3": f"{request_id}-{span_id}-1-",
                "X-B3-TraceId": request_id,
                "X-B3-SpanId": span_id,
                "X-B3-Sampled": "1",
            })
        return headers

    async def start_auth(self) -> Dict[str, Any]:
        """启动认证流程，返回 auth_url 和 auth_state"""
        nonce = secrets.token_hex(8)
        url = f"{self.state_endpoint}?platform=CLI&nonce={nonce}"
        headers = self._get_auth_headers()

        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, json={"nonce": nonce}, headers=headers, timeout=30)

        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0 and result.get("data"):
                data = result["data"]
                return {
                    "success": True,
                    "auth_state": data.get("state"),
                    "auth_url": data.get("authUrl"),
                    "token_url": f"{self.token_endpoint}?state={data.get('state')}",
                }

        return {"success": False, "error": f"Auth start failed: {resp.status_code}"}

    async def poll_token(self, auth_state: str, timeout: float = 300, interval: float = 5) -> Dict[str, Any]:
        """轮询 token，直到成功或超时"""
        url = f"{self.token_endpoint}?state={auth_state}"
        headers = self._get_auth_headers(include_state=True)
        start = time.time()

        async with httpx.AsyncClient(verify=False) as client:
            while time.time() - start < timeout:
                resp = await client.get(url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0 and result.get("data", {}).get("accessToken"):
                        data = result["data"]
                        return {
                            "success": True,
                            "access_token": data["accessToken"],
                            "token_type": data.get("tokenType", "Bearer"),
                            "expires_in": data.get("expiresIn"),
                            "refresh_token": data.get("refreshToken"),
                            "session_state": data.get("sessionState"),
                            "scope": data.get("scope"),
                            "domain": data.get("domain"),
                        }
                    elif result.get("code") == 11217:
                        logger.info("Waiting for user login...")
                    else:
                        logger.warning(f"Unexpected auth response: {result}")
                await asyncio.sleep(interval)

        return {"success": False, "error": "Auth timeout"}

    def _parse_user_id(self, token: str) -> str:
        """从 JWT token 解析 user_id"""
        try:
            if "." in token:
                parts = token.split(".")
                if len(parts) >= 2:
                    payload_part = parts[1]
                    missing_padding = len(payload_part) % 4
                    if missing_padding:
                        payload_part += "=" * (4 - missing_padding)
                    payload = base64.urlsafe_b64decode(payload_part)
                    jwt_data = json.loads(payload.decode("utf-8"))
                    return jwt_data.get("email") or jwt_data.get("preferred_username") or jwt_data.get("sub") or "unknown"
        except Exception:
            pass
        return "unknown"

    def save_token(self, token_data: Dict[str, Any]) -> Path:
        """保存 token 到文件"""
        creds_dir = self.config.creds_dir or DEFAULT_CREDS_DIR
        creds_dir.mkdir(parents=True, exist_ok=True)

        bearer_token = token_data["access_token"]
        user_id = self._parse_user_id(bearer_token)
        timestamp = int(time.time())

        credential = {
            "bearer_token": bearer_token,
            "user_id": user_id,
            "created_at": timestamp,
            "token_type": token_data.get("token_type", "Bearer"),
        }
        if token_data.get("expires_in"):
            credential["expires_in"] = token_data["expires_in"]
        if token_data.get("refresh_token"):
            credential["refresh_token"] = token_data["refresh_token"]
        if token_data.get("session_state"):
            credential["session_state"] = token_data["session_state"]
        if token_data.get("scope"):
            credential["scope"] = token_data["scope"]
        if token_data.get("domain"):
            credential["domain"] = token_data["domain"]

        safe_uid = "".join(c for c in user_id if c.isalnum() or c in "._-")[:20]
        filename = f"codebuddy_{safe_uid}_{timestamp}.json"
        filepath = creds_dir / filename

        filepath.write_text(json.dumps(credential, indent=4, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Token saved: {filename} (user: {user_id})")
        return filepath

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """使用 refresh_token 刷新"""
        url = f"{self.base_url}/v2/plugin/auth/refresh"
        headers = self._get_auth_headers()
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, json={"refreshToken": refresh_token}, headers=headers, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0 and result.get("data", {}).get("accessToken"):
                return {"success": True, **result["data"]}
        return {"success": False, "error": f"Refresh failed: {resp.status_code}"}

    async def authenticate(self, open_browser: bool = True) -> Optional[str]:
        """完整的认证流程：启动 → 打开浏览器 → 轮询 → 保存"""
        start_result = await self.start_auth()
        if not start_result["success"]:
            logger.error(f"Auth start failed: {start_result}")
            return None

        auth_url = start_result["auth_url"]
        auth_state = start_result["auth_state"]
        print(f"\n请在浏览器中登录 CodeBuddy:")
        print(f"  {auth_url}\n")

        if open_browser:
            try:
                webbrowser.open(auth_url)
            except Exception:
                pass

        token_result = await self.poll_token(auth_state)
        if not token_result["success"]:
            logger.error(f"Auth failed: {token_result}")
            return None

        self.save_token(token_result)
        return token_result["access_token"]



# --- HTTP API 模式 ---

def _sanitize_value(v):
    """清理单个值中的 surrogate 字符"""
    if isinstance(v, str):
        return "".join(c if ord(c) < 0xD800 or ord(c) > 0xDFFF else "\ufffd" for c in v)
    if isinstance(v, list):
        return [_sanitize_value(item) for item in v]
    if isinstance(v, dict):
        return {k: _sanitize_value(val) for k, val in v.items()}
    return v


def _sanitize_payload(payload: dict) -> dict:
    """清理 JSON payload 中所有字符串的 surrogate 字符"""
    return _sanitize_value(payload)

class CodeBuddyHTTPClient:
    """直接调用 CodeBuddy REST API（OpenAI 兼容格式）"""

    def __init__(self, config: CodeBuddyConfig):
        self.config = config
        self.base_url = get_api_endpoint(config)
        # 本地代理用 /v1，官方 API 用 /v2
        if "127.0.0.1" in self.base_url or "localhost" in self.base_url:
            self.api_url = f"{self.base_url}/v1/chat/completions"
        else:
            self.api_url = f"{self.base_url}/v2/chat/completions"

    def _get_auth(self) -> Dict[str, str]:
        """获取认证信息"""
        api_key = self.config.api_key
        bearer_token = self.config.bearer_token

        if api_key:
            return {
                "type": "api_key",
                "api_key": api_key,
                "user_id": "anonymous",
            }

        if bearer_token:
            return {
                "type": "bearer",
                "bearer_token": bearer_token,
                "user_id": "anonymous",
            }

        # 尝试从凭证文件加载
        token = get_next_bearer_token(self.config)
        if token:
            return {
                "type": "bearer",
                "bearer_token": token,
                "user_id": "anonymous",
            }

        return None

    def _build_headers(self, auth: Dict[str, Any]) -> Dict[str, str]:
        """构建请求头"""
        parsed = httpx.URL(self.base_url)
        domain = parsed.host or "copilot.tencent.com"
        is_proxy = "127.0.0.1" in self.base_url or "localhost" in self.base_url

        request_id = uuid.uuid4().hex

        if is_proxy:
            # 本地代理只需认证头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth.get('api_key') or auth.get('bearer_token', '')}",
            }
            return headers

        # 官方 API 需要完整头
        conversation_id = str(uuid.uuid4())
        conversation_request_id = secrets.token_hex(16)
        conversation_message_id = uuid.uuid4().hex

        headers = {
            "Host": domain,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "x-stainless-arch": "x64",
            "x-stainless-lang": "js",
            "x-stainless-os": "Windows",
            "x-stainless-package-version": "5.10.1",
            "x-stainless-retry-count": "0",
            "x-stainless-runtime": "node",
            "x-stainless-runtime-version": "v22.13.1",
            "X-Conversation-ID": conversation_id,
            "X-Conversation-Request-ID": conversation_request_id,
            "X-Conversation-Message-ID": conversation_message_id,
            "X-Request-ID": request_id,
            "X-Agent-Intent": "craft",
            "X-IDE-Type": "CLI",
            "X-IDE-Name": "CLI",
            "X-IDE-Version": "1.0.7",
            "X-Domain": domain,
            "User-Agent": "CLI/1.0.7 CodeBuddy/1.0.7",
            "X-Product": "SaaS",
            "X-User-Id": auth.get("user_id", "b5be3a67-237e-4ee6-9b9a-0b9ecd7b454b"),
        }

        auth_type = auth["type"]
        if auth_type == "api_key":
            headers["Authorization"] = f"Bearer {auth['api_key']}"
            headers["X-API-Key"] = auth["api_key"]
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth['bearer_token']}"

        return headers

    async def query(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = True,
        _retry: bool = True,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """发送请求并流式返回结果，支持 429/401 自动刷新"""
        auth = self._get_auth()
        if not auth:
            raise ValueError("No authentication available. Set CODEBUDDY_API_KEY or add token files.")

        headers = self._build_headers(auth)
        payload = {
            "model": model or self.config.model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }

        # 清理 payload 中的 surrogate 字符
        payload = _sanitize_payload(payload)

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream("POST", self.api_url, json=payload, headers=headers) as response:
                if response.status_code == 429 and _retry and self.config.auto_refresh:
                    # 429 = 限流，先重试一次（退避）
                    error_text = (await response.aread()).decode("utf-8", errors="ignore")
                    logger.warning("API error 429, retrying after delay...")
                    await asyncio.sleep(1.0)  # 退避 1 秒
                    async for chunk in self.query(messages, model=model, stream=stream, _retry=False, **kwargs):
                        yield chunk
                    return

                if response.status_code == 401 and _retry and self.config.auto_refresh:
                    # 401 = 认证失败，尝试刷新
                    error_text = (await response.aread()).decode("utf-8", errors="ignore")
                    logger.warning("API error 401, attempting token refresh...")
                    refreshed = await self._try_refresh_auth()
                    if refreshed:
                        async for chunk in self.query(messages, model=model, stream=stream, _retry=False, **kwargs):
                            yield chunk
                        return
                    raise ValueError(f"CodeBuddy API error 401: {error_text}")

                if response.status_code != 200:
                    error_text = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ValueError(f"CodeBuddy API error {response.status_code}: {error_text}")

                buffer = ""
                async for chunk in response.aiter_text(chunk_size=8192):
                    if not chunk:
                        continue
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or line.startswith(":") or "[DONE]" in line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue

    async def _try_refresh_auth(self) -> bool:
        """401 时尝试刷新认证（refresh_token 或交互式登录）"""
        creds_dir = self.config.creds_dir or DEFAULT_CREDS_DIR
        credentials = load_credentials(creds_dir)

        # 尝试用 refresh_token
        for cred in credentials:
            if cred.refresh_token:
                auth_obj = CodeBuddyAuth(self.config)
                result = await auth_obj.refresh_token(cred.refresh_token)
                if result.get("success"):
                    auth_obj.save_token(result)
                    logger.info("Token refreshed via refresh_token")
                    return True

        # 没有 refresh_token，尝试重新认证（交互式）
        logger.info("No refresh_token, starting interactive auth...")
        auth_obj = CodeBuddyAuth(self.config)
        new_token = await auth_obj.authenticate(open_browser=True)
        if new_token:
            logger.info("Interactive auth succeeded")
            return True

        return False

    async def query_text(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """单次查询，返回文本结果"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in self.query(messages, model=model, stream=True, **kwargs):
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                result += content
        return result


# --- SDK 模式 ---

class CodeBuddySDKClient:
    """通过 codebuddy-agent-sdk 调用"""

    def __init__(self, config: CodeBuddyConfig):
        self.config = config

    async def query(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        from codebuddy_agent_sdk import query, CodeBuddyAgentOptions, AssistantMessage

        # 将 messages 转为 prompt（SDK 只接受单条 prompt）
        prompt = messages[-1]["content"] if messages else ""
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)

        options = CodeBuddyAgentOptions(
            permission_mode=self.config.permission_mode,
            max_turns=1,
            model=model or self.config.model,
            env={"CODEBUDDY_INTERNET_ENVIRONMENT": self.config.internet_env},
        )
        if system_msg:
            options.system_prompt = system_msg

        result = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text"):
                        result += block.text
        return result


# --- 统一入口 ---

class CodeBuddyClient:
    """统一的 CodeBuddy 客户端，自动选择 SDK 或 HTTP API 模式"""

    def __init__(self, config: Optional[CodeBuddyConfig] = None):
        self.config = config or load_config()
        self._http_client: Optional[CodeBuddyHTTPClient] = None
        self._sdk_client: Optional[CodeBuddySDKClient] = None

    @property
    def mode(self) -> str:
        """确定实际使用的模式"""
        if self.config.auth_mode == "sdk":
            return "sdk"
        if self.config.auth_mode == "token":
            return "http"
        if self.config.auth_mode == "api_key":
            return "http"
        # auto: 有凭证文件或明确了 HTTP 参数就用 HTTP，否则尝试 SDK
        if self.config.creds_dir and (self.config.creds_dir / "*.json").name:
            creds = load_credentials(self.config.creds_dir)
            if creds:
                return "http"
        return "sdk"

    @property
    def http_client(self) -> CodeBuddyHTTPClient:
        if self._http_client is None:
            self._http_client = CodeBuddyHTTPClient(self.config)
        return self._http_client

    @property
    def sdk_client(self) -> CodeBuddySDKClient:
        if self._sdk_client is None:
            self._sdk_client = CodeBuddySDKClient(self.config)
        return self._sdk_client

    async def query_text(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: Optional[str] = None,
    ) -> str:
        """单次文本查询"""
        if self.mode == "http":
            return await self.http_client.query_text(prompt, system_prompt, model)
        return await self.sdk_client.query(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model,
        )

    async def query_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """流式查询，逐块 yield 文本"""
        if self.mode == "http":
            async for chunk in self.http_client.query(messages, model=model):
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
        else:
            text = await self.sdk_client.query(messages, model)
            yield text

"""CodeBuddy 工具链纯函数单测（不连接 DB / 网络）。"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import pytest

# 让测试能 import 仓库根目录下的 odoo_query / codebuddy_adapter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import odoo_query  # noqa: E402
import codebuddy_adapter as cba  # noqa: E402


# --- odoo_query._strip_sql_fence ---

def test_strip_sql_fence_plain():
    assert odoo_query._strip_sql_fence("SELECT 1") == "SELECT 1"


def test_strip_sql_fence_sql_block():
    assert odoo_query._strip_sql_fence("```sql\nSELECT 1\n```") == "SELECT 1"


def test_strip_sql_fence_plain_block():
    assert odoo_query._strip_sql_fence("```\nSELECT 2\n```") == "SELECT 2"


def test_strip_sql_fence_prose_around_block():
    text = "这是查询：\n```sql\nSELECT * FROM res_partner\n```\n完成"
    assert odoo_query._strip_sql_fence(text) == "SELECT * FROM res_partner"


def test_strip_sql_fence_preserves_trailing_l():
    # 回归：旧的 strip("```sql") 会把结尾的 l / 列名字符删掉
    sql = "SELECT col FROM account_move_line"
    assert odoo_query._strip_sql_fence(sql) == sql


def test_strip_sql_fence_empty():
    assert odoo_query._strip_sql_fence("") == ""


# --- odoo_query._is_readonly_sql ---

@pytest.mark.parametrize("sql", [
    "SELECT * FROM res_partner",
    "select 1",
    "   SELECT 1",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "EXPLAIN SELECT 1",
    "SHOW server_version",
    "-- 注释\nSELECT 1",
])
def test_is_readonly_sql_allows(sql):
    assert odoo_query._is_readonly_sql(sql) is True


@pytest.mark.parametrize("sql", [
    "DELETE FROM res_partner",
    "DROP TABLE x",
    "UPDATE res_partner SET name='x'",
    "INSERT INTO x VALUES (1)",
    "TRUNCATE res_partner",
    "ALTER TABLE x ADD COLUMN y int",
    "",
    "   ",
    "-- 只有注释",
])
def test_is_readonly_sql_rejects(sql):
    assert odoo_query._is_readonly_sql(sql) is False


# --- codebuddy_adapter.is_token_expired ---

def _cred(**kw):
    base = dict(bearer_token="t", user_id="u", created_at=0, file_path=Path("x"))
    base.update(kw)
    return cba.Credential(**base)


def test_token_expired_no_info():
    assert cba.is_token_expired(_cred()) is False


def test_token_expired_future():
    assert cba.is_token_expired(_cred(created_at=int(time.time()), expires_in=3600)) is False


def test_token_expired_past():
    assert cba.is_token_expired(_cred(created_at=int(time.time()) - 7200, expires_in=3600)) is True


# --- codebuddy_adapter.CodeBuddyAuth._parse_user_id ---

def _make_auth():
    return cba.CodeBuddyAuth(cba.CodeBuddyConfig())


def test_parse_user_id_valid_jwt():
    payload = base64.urlsafe_b64encode(json.dumps({"email": "a@b.com"}).encode()).decode().rstrip("=")
    token = "header." + payload + ".sig"
    assert _make_auth()._parse_user_id(token) == "a@b.com"


def test_parse_user_id_sub_fallback():
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "uid-123"}).encode()).decode().rstrip("=")
    token = "h." + payload + ".s"
    assert _make_auth()._parse_user_id(token) == "uid-123"


def test_parse_user_id_malformed():
    assert _make_auth()._parse_user_id("not-a-jwt") == "unknown"


# --- codebuddy_adapter._sanitize_value / _sanitize_payload ---

def test_sanitize_value_surrogate():
    out = cba._sanitize_value("abc\ud800def")
    assert "\ud800" not in out
    assert out == "abc�def"


def test_sanitize_value_nested():
    out = cba._sanitize_value({"a": ["x\ud800", {"b": "y\udfff"}]})
    assert out["a"][0] == "x�"
    assert out["a"][1]["b"] == "y�"


def test_sanitize_payload():
    out = cba._sanitize_payload({"messages": [{"role": "user", "content": "hi\ud800"}]})
    assert out["messages"][0]["content"] == "hi�"


# --- codebuddy_adapter.get_api_endpoint ---

def test_get_api_endpoint_public():
    assert cba.get_api_endpoint(cba.CodeBuddyConfig(internet_env="public")) == "https://www.codebuddy.ai"


def test_get_api_endpoint_internal():
    assert cba.get_api_endpoint(cba.CodeBuddyConfig(internet_env="internal")) == "https://copilot.tencent.com"


def test_get_api_endpoint_explicit_strips_slash():
    cfg = cba.CodeBuddyConfig(api_endpoint="http://localhost:8080/")
    assert cba.get_api_endpoint(cfg) == "http://localhost:8080"


# --- codebuddy_adapter.load_config (TLS 开关) ---

def test_load_config_tls_verify_default(monkeypatch):
    monkeypatch.delenv("CODEBUDDY_TLS_VERIFY", raising=False)
    assert cba.load_config().tls_verify is True


def test_load_config_tls_verify_false(monkeypatch):
    monkeypatch.setenv("CODEBUDDY_TLS_VERIFY", "false")
    assert cba.load_config().tls_verify is False


def test_load_config_model(monkeypatch):
    monkeypatch.setenv("CODEBUDDY_MODEL", "glm-test")
    assert cba.load_config().model == "glm-test"

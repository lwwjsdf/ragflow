#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""Unit tests for MCP tools list endpoint."""

import asyncio
import importlib.util
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


class _DummyManager:
    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


def _load_agent_teams_module(monkeypatch):
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]

    api_pkg = ModuleType("api")
    api_pkg.__path__ = [str(repo_root / "api")]
    monkeypatch.setitem(sys.modules, "api", api_pkg)

    apps_mod = ModuleType("api.apps")
    apps_mod.__path__ = [str(repo_root / "api" / "apps")]
    apps_mod.login_user = Mock(return_value=True)
    monkeypatch.setitem(sys.modules, "api.apps", apps_mod)

    common_pkg = ModuleType("common")
    common_pkg.__path__ = [str(repo_root / "common")]
    monkeypatch.setitem(sys.modules, "common", common_pkg)

    constants_mod = ModuleType("common.constants")
    constants_mod.RetCode = SimpleNamespace(
        SUCCESS=0,
        UNAUTHORIZED=401,
        FORBIDDEN=403,
        NOT_FOUND=404,
        ARGUMENT_ERROR=101,
        OPERATING_ERROR=102,
    )
    monkeypatch.setitem(sys.modules, "common.constants", constants_mod)

    api_utils_mod = ModuleType("api.utils.api_utils")
    api_utils_mod.get_json_result = lambda data=None, message="success", code=0: {
        "code": code,
        "message": message,
        "data": data,
    }
    monkeypatch.setitem(sys.modules, "api.utils.api_utils", api_utils_mod)

    auth_mod = ModuleType("api.utils.agent_teams_auth")
    auth_mod.authenticate_by_api_key = Mock(return_value=None)
    monkeypatch.setitem(sys.modules, "api.utils.agent_teams_auth", auth_mod)

    quart_mod = ModuleType("quart")
    quart_mod.request = SimpleNamespace(headers={}, args={})
    quart_mod.redirect = lambda location, code=302: SimpleNamespace(
        status_code=code, headers={"Location": location}
    )
    monkeypatch.setitem(sys.modules, "quart", quart_mod)

    module_path = repo_root / "api" / "apps" / "restful_apis" / "agent_teams_api.py"
    spec = importlib.util.spec_from_file_location("agent_teams_api_test_module", str(module_path))
    module = importlib.util.module_from_spec(spec)
    module.manager = _DummyManager()
    monkeypatch.setitem(sys.modules, "agent_teams_api_test_module", module)
    spec.loader.exec_module(module)
    return module


class TestMcpToolsList:
    """Test suite for POST /mcp/v1/tools/list endpoint."""

    def test_missing_auth_header_returns_401(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        monkeypatch.setattr(module, "request", SimpleNamespace(headers={}))

        result = asyncio.run(module.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        assert result[0]["error"]["message"] == "Unauthorized"

    def test_invalid_auth_header_returns_401(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        module.authenticate_by_api_key.return_value = None
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "InvalidFormat"})
        )

        result = asyncio.run(module.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]

    def test_invalid_api_key_returns_401(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        module.authenticate_by_api_key.return_value = None
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer invalid_key"})
        )

        result = asyncio.run(module.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        module.authenticate_by_api_key.assert_called_once_with("invalid_key")

    def test_valid_auth_returns_tool_list(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer sk_valid123"})
        )

        result = asyncio.run(module.mcp_tools_list())

        module.authenticate_by_api_key.assert_called_once_with("sk_valid123")
        assert result["jsonrpc"] == "2.0"
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) == 2

    def test_response_contains_search_knowledge_base_tool(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer sk_valid123"})
        )

        result = asyncio.run(module.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "search_knowledge_base" in tool_names

    def test_response_contains_list_knowledge_bases_tool(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer sk_valid123"})
        )

        result = asyncio.run(module.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "list_knowledge_bases" in tool_names

    def test_search_knowledge_base_tool_structure(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer sk_valid123"})
        )

        result = asyncio.run(module.mcp_tools_list())

        tool = next(
            t for t in result["result"]["tools"] if t["name"] == "search_knowledge_base"
        )
        assert tool["description"] == "在知识库中检索与查询相关的内容，返回匹配的文本片段"
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert "query" in tool["parameters"]["properties"]
        assert "dataset_ids" in tool["parameters"]["properties"]
        assert "top_n" in tool["parameters"]["properties"]
        assert tool["parameters"]["required"] == ["query"]

    def test_list_knowledge_bases_tool_structure(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(
            module, "request", SimpleNamespace(headers={"Authorization": "Bearer sk_valid123"})
        )

        result = asyncio.run(module.mcp_tools_list())

        tool = next(
            t for t in result["result"]["tools"] if t["name"] == "list_knowledge_bases"
        )
        assert tool["description"] == "列出当前租户下的所有知识库"
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert tool["parameters"]["properties"] == {}
        assert tool["parameters"]["required"] == []

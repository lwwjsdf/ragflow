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
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.apps.restful_apis import agent_teams_api


class _DummyManager:
    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func
        return decorator


@pytest.fixture(autouse=True)
def _patch_manager(monkeypatch):
    monkeypatch.setattr(agent_teams_api, "manager", _DummyManager())


@pytest.fixture
def auth_mock(monkeypatch):
    mock = Mock(return_value=None)
    monkeypatch.setattr(agent_teams_api, "authenticate_by_api_key", mock)
    return mock


@pytest.fixture
def valid_user():
    mock_user = Mock()
    mock_user.email = "test@example.com"
    return {"tenant_id": "tenant_123", "user": mock_user}


async def _async_get_json(body):
    return body


def _make_request(headers, body=None):
    req = SimpleNamespace(headers=headers)
    req.get_json = Mock(return_value=_async_get_json(body))
    return req


class TestMcpToolsList:
    """Test suite for POST /mcp/v1/tools/list endpoint."""

    def test_missing_auth_header_returns_401(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api, "request", _make_request(headers={}, body={"jsonrpc": "2.0"})
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32001
        assert result[0]["error"]["message"] == "Unauthorized"

    def test_invalid_auth_header_returns_401(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "InvalidFormat"}, body={"jsonrpc": "2.0"}),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32001

    def test_invalid_api_key_returns_401(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer invalid_key"}, body={"jsonrpc": "2.0"}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32001
        auth_mock.assert_called_once_with("invalid_key")

    def test_invalid_jsonrpc_returns_400(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"jsonrpc": "1.0", "id": 42},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] == 42

    def test_valid_auth_returns_tool_list(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        auth_mock.assert_called_once_with("sk_valid123")
        assert result["jsonrpc"] == "2.0"
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) == 2

    def test_response_contains_search_knowledge_base_tool(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "search_knowledge_base" in tool_names

    def test_response_contains_list_knowledge_bases_tool(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "list_knowledge_bases" in tool_names

    def test_search_knowledge_base_tool_structure(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

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

    def test_list_knowledge_bases_tool_structure(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool = next(
            t for t in result["result"]["tools"] if t["name"] == "list_knowledge_bases"
        )
        assert tool["description"] == "列出当前租户下的所有知识库"
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert tool["parameters"]["properties"] == {}
        assert tool["parameters"]["required"] == []

    @pytest.mark.parametrize("rpc_id", [1, "abc", None])
    def test_request_id_echoed_in_response(self, monkeypatch, auth_mock, valid_user, rpc_id):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"jsonrpc": "2.0", "id": rpc_id},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result["id"] == rpc_id

    def test_missing_id_returns_null_id(self, monkeypatch, auth_mock, valid_user):
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"jsonrpc": "2.0"},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result["id"] is None

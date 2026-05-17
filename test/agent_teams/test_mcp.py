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

"""Unit tests for MCP tools list and call endpoints."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        monkeypatch.setattr(agent_teams_api, "request", _make_request(headers={}, body={"jsonrpc": "2.0"}))

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
            _make_request(headers={"Authorization": "Bearer invalid_key"}, body={"jsonrpc": "2.0"}),
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

    def _setup_valid_auth(self, monkeypatch, auth_mock, valid_user, body=None):
        auth_mock.return_value = valid_user
        if body is None:
            body = {"jsonrpc": "2.0", "id": 1}
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_valid123"}, body=body),
        )

    def test_valid_auth_returns_tool_list(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user)

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        auth_mock.assert_called_once_with("sk_valid123")
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) == 2

    def test_response_contains_search_knowledge_base_tool(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user)

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "search_knowledge_base" in tool_names

    def test_response_contains_list_knowledge_bases_tool(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user)

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool_names = [t["name"] for t in result["result"]["tools"]]
        assert "list_knowledge_bases" in tool_names

    def test_search_knowledge_base_tool_structure(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user)

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool = next(t for t in result["result"]["tools"] if t["name"] == "search_knowledge_base")
        assert tool["description"] == "在知识库中检索与查询相关的内容，返回匹配的文本片段"
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert "query" in tool["parameters"]["properties"]
        assert "dataset_ids" in tool["parameters"]["properties"]
        assert "top_n" in tool["parameters"]["properties"]
        assert tool["parameters"]["required"] == ["query"]

    def test_list_knowledge_bases_tool_structure(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user)

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        tool = next(t for t in result["result"]["tools"] if t["name"] == "list_knowledge_bases")
        assert tool["description"] == "列出当前租户下的所有知识库"
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "object"
        assert tool["parameters"]["properties"] == {}
        assert tool["parameters"]["required"] == []

    def test_missing_jsonrpc_returns_400(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"id": 42},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] == 42

    @pytest.mark.parametrize("body", [[], "string", 42, None])
    def test_non_dict_body_returns_400(self, monkeypatch, auth_mock, body):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body=body,
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] is None

    @pytest.mark.parametrize("rpc_id", [1, "abc", None])
    def test_request_id_echoed_in_response(self, monkeypatch, auth_mock, valid_user, rpc_id):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user, body={"jsonrpc": "2.0", "id": rpc_id})

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result["id"] == rpc_id

    def test_missing_id_returns_null_id(self, monkeypatch, auth_mock, valid_user):
        self._setup_valid_auth(monkeypatch, auth_mock, valid_user, body={"jsonrpc": "2.0"})

        result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert result["id"] is None


class TestMcpToolsCall:
    """Test suite for POST /mcp/v1/tools/call endpoint."""

    def _setup_request(self, monkeypatch, body):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_valid123"}, body=body),
        )

    def _setup_auth(self, auth_mock, valid_user):
        auth_mock.return_value = valid_user

    def test_missing_auth_header_returns_401(self, monkeypatch, auth_mock):
        monkeypatch.setattr(agent_teams_api, "request", _make_request(headers={}, body={"jsonrpc": "2.0"}))

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 401
        assert result[0]["jsonrpc"] == "2.0"
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32001

    def test_missing_jsonrpc_returns_400(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"id": 42},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] == 42

    def test_invalid_jsonrpc_returns_400(self, monkeypatch, auth_mock):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body={"jsonrpc": "1.0", "id": 42},
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] == 42

    @pytest.mark.parametrize("body", [[], "string", 42, None])
    def test_non_dict_body_returns_400(self, monkeypatch, auth_mock, body):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(
                headers={"Authorization": "Bearer sk_valid123"},
                body=body,
            ),
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] is None

    def test_invalid_tool_name_returns_error(self, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"name": "invalid_tool", "arguments": {}},
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32601
        assert "invalid_tool" in result[0]["error"]["message"]

    def test_search_missing_query_returns_error(self, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"name": "search_knowledge_base", "arguments": {}},
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32602
        assert "query" in result[0]["error"]["message"]

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_search_with_valid_params_returns_results(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
    ):
        self._setup_auth(auth_mock, valid_user)

        # Mock KB
        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        # Mock retriever
        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_result(
            {
                "chunks": [
                    {
                        "content_with_weight": "SSL config info",
                        "similarity": 0.95,
                        "docnm_kwd": "ssl_guide.pdf",
                        "kb_id": "kb_123",
                    }
                ],
                "total": 1,
            }
        )
        mock_settings.retriever = mock_retriever

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "SSL", "dataset_ids": ["kb_123"], "top_n": 5},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert "content" in result["result"]
        assert len(result["result"]["content"]) == 1
        assert result["result"]["content"][0]["type"] == "text"

        parsed = json.loads(result["result"]["content"][0]["text"])
        assert "chunks" in parsed
        assert len(parsed["chunks"]) == 1
        assert parsed["chunks"][0]["content"] == "SSL config info"
        assert parsed["chunks"][0]["score"] == 0.95
        assert parsed["chunks"][0]["document_name"] == "ssl_guide.pdf"
        assert parsed["chunks"][0]["dataset_id"] == "kb_123"

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_search_internal_error_returns_32000(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
    ):
        self._setup_auth(auth_mock, valid_user)

        # Mock KB
        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        # Mock retriever to raise exception
        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_exception(RuntimeError("Retriever failure"))
        mock_settings.retriever = mock_retriever

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "SSL", "dataset_ids": ["kb_123"], "top_n": 5},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32000
        assert result[0]["error"]["message"] == "Internal error"

    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    def test_list_knowledge_bases_returns_kb_list(self, mock_kb_service, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)

        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.name = "Test KB"
        mock_kb.doc_num = 10
        mock_kb.chunk_num = 100
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"name": "list_knowledge_bases", "arguments": {}},
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result

        parsed = json.loads(result["result"]["content"][0]["text"])
        assert "knowledge_bases" in parsed
        assert len(parsed["knowledge_bases"]) == 1
        assert parsed["knowledge_bases"][0]["id"] == "kb_123"
        assert parsed["knowledge_bases"][0]["name"] == "Test KB"
        assert parsed["knowledge_bases"][0]["document_count"] == 10
        assert parsed["knowledge_bases"][0]["chunk_count"] == 100

    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    def test_tenant_isolation_for_search(self, mock_kb_service, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)

        # tenant_123 only has kb_123, not kb_456
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test", "dataset_ids": ["kb_456"]},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32602
        assert "Invalid dataset_ids" in result[0]["error"]["message"]

    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    def test_tenant_isolation_for_list(self, mock_kb_service, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)

        mock_kb_service.get_kb_ids.return_value = []
        mock_kb_service.get_by_ids.return_value = []

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"name": "list_knowledge_bases", "arguments": {}},
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result

        parsed = json.loads(result["result"]["content"][0]["text"])
        assert parsed["knowledge_bases"] == []

    @pytest.mark.parametrize("params_value", ["string", [], 42, None])
    def test_invalid_params_type_returns_error(self, monkeypatch, auth_mock, valid_user, params_value):
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": params_value,
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32602

    def test_missing_params_key_defaults_to_empty(self, monkeypatch, auth_mock, valid_user):
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32601

    @pytest.mark.parametrize("top_n", [-5, 0, 1000])
    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_search_top_n_bounds(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
        top_n,
    ):
        self._setup_auth(auth_mock, valid_user)

        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_result({"chunks": [], "total": 0})
        mock_settings.retriever = mock_retriever

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test", "dataset_ids": ["kb_123"], "top_n": top_n},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result

        call_kwargs = mock_retriever.retrieval.call_args.kwargs
        expected_top_n = 8 if top_n <= 0 else min(top_n, 100)
        assert call_kwargs["page_size"] == expected_top_n

    @pytest.mark.parametrize("dataset_ids", ["kb_123", {"id": "kb_123"}])
    def test_search_dataset_ids_type_mismatch_returns_error(self, monkeypatch, auth_mock, valid_user, dataset_ids):
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test", "dataset_ids": dataset_ids},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["id"] == 1
        assert "error" in result[0]
        assert result[0]["error"]["code"] == -32602
        assert "dataset_ids" in result[0]["error"]["message"]

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_search_no_dataset_ids_fallback_to_tenant_kbs(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
    ):
        self._setup_auth(auth_mock, valid_user)

        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_result({"chunks": [], "total": 0})
        mock_settings.retriever = mock_retriever

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test"},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result

        call_args = mock_retriever.retrieval.call_args
        assert call_args.args[3] == ["kb_123"]

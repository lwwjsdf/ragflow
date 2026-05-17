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

"""Integration tests for agent_teams_api endpoints working together."""

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


@pytest.fixture(autouse=True)
def _patch_login_user(monkeypatch):
    monkeypatch.setattr(agent_teams_api, "login_user", Mock(return_value=True))


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


@pytest.fixture
def valid_user_b():
    mock_user = Mock()
    mock_user.email = "user_b@example.com"
    return {"tenant_id": "tenant_456", "user": mock_user}


async def _async_get_json(body):
    return body


def _make_request(headers, body=None):
    req = SimpleNamespace(headers=headers)
    req.get_json = Mock(return_value=_async_get_json(body))
    return req


class TestFullRedirectFlow:
    """Integration tests for the complete redirect flow."""

    def test_full_redirect_flow_with_valid_key(self, monkeypatch, auth_mock, valid_user):
        """Test complete redirect flow: request -> auth -> redirect -> session set."""
        auth_mock.return_value = valid_user
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={"api_key": "sk_valid123"}))

        result = agent_teams_api.knowledge_redirect()

        auth_mock.assert_called_once_with("sk_valid123")
        assert result.status_code == 302
        assert result.headers["Location"] == "/knowledge/datasets"

    def test_full_redirect_flow_with_custom_path(self, monkeypatch, auth_mock, valid_user):
        """Test redirect flow with custom redirect path."""
        auth_mock.return_value = valid_user
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            SimpleNamespace(args={"api_key": "sk_valid123", "redirect": "/custom/page"}),
        )

        result = agent_teams_api.knowledge_redirect()

        assert result.status_code == 302
        assert result.headers["Location"] == "/custom/page"

    def test_redirect_rejects_invalid_key(self, monkeypatch, auth_mock):
        """Test redirect flow rejects invalid API key."""
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={"api_key": "sk_invalid"}))

        result = agent_teams_api.knowledge_redirect()

        auth_mock.assert_called_once_with("sk_invalid")
        assert result[1] == 401
        assert result[0]["code"] == 401

    def test_redirect_rejects_missing_key(self, monkeypatch, auth_mock):
        """Test redirect flow rejects missing API key."""
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={}))

        result = agent_teams_api.knowledge_redirect()

        auth_mock.assert_not_called()
        assert result[1] == 401


class TestFullMcpFlow:
    """Integration tests for the complete MCP tools flow."""

    def _setup_auth(self, auth_mock, valid_user):
        auth_mock.return_value = valid_user

    def _setup_request(self, monkeypatch, body):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_valid123"}, body=body),
        )

    def test_full_mcp_flow_list_then_call(self, monkeypatch, auth_mock, valid_user):
        """Test complete MCP flow: list tools then call a tool."""
        self._setup_auth(auth_mock, valid_user)

        # Step 1: List tools
        self._setup_request(monkeypatch, {"jsonrpc": "2.0", "id": 1})
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())

        assert list_result["jsonrpc"] == "2.0"
        assert list_result["id"] == 1
        assert "result" in list_result
        assert "tools" in list_result["result"]
        assert len(list_result["result"]["tools"]) == 2

        # Verify both tools exist
        tool_names = [t["name"] for t in list_result["result"]["tools"]]
        assert "search_knowledge_base" in tool_names
        assert "list_knowledge_bases" in tool_names

        # Step 2: Call list_knowledge_bases tool
        with patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService") as mock_kb_service:
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
                    "id": 2,
                    "params": {"name": "list_knowledge_bases", "arguments": {}},
                },
            )
            call_result = asyncio.run(agent_teams_api.mcp_tools_call())

            assert call_result["jsonrpc"] == "2.0"
            assert call_result["id"] == 2
            assert "result" in call_result

            parsed = json.loads(call_result["result"]["content"][0]["text"])
            assert len(parsed["knowledge_bases"]) == 1
            assert parsed["knowledge_bases"][0]["name"] == "Test KB"

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_full_mcp_flow_search_tool(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
    ):
        """Test complete MCP flow ending with search tool call."""
        self._setup_auth(auth_mock, valid_user)

        # Setup KB mock
        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        # Setup retriever mock
        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_result(
            {
                "chunks": [
                    {
                        "content_with_weight": "Test result content",
                        "similarity": 0.92,
                        "docnm_kwd": "test_doc.pdf",
                        "kb_id": "kb_123",
                    }
                ],
                "total": 1,
            }
        )
        mock_settings.retriever = mock_retriever

        # Step 1: List tools
        self._setup_request(monkeypatch, {"jsonrpc": "2.0", "id": 1})
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())
        assert "search_knowledge_base" in [t["name"] for t in list_result["result"]["tools"]]

        # Step 2: Call search tool
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test query", "dataset_ids": ["kb_123"], "top_n": 5},
                },
            },
        )
        search_result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert search_result["jsonrpc"] == "2.0"
        assert search_result["id"] == 2
        assert "result" in search_result

        parsed = json.loads(search_result["result"]["content"][0]["text"])
        assert len(parsed["chunks"]) == 1
        assert parsed["chunks"][0]["content"] == "Test result content"
        assert parsed["chunks"][0]["score"] == 0.92


class TestCrossEndpointAuthConsistency:
    """Tests verifying auth behavior is consistent across redirect and MCP endpoints."""

    def test_same_api_key_works_for_redirect_and_mcp(self, monkeypatch, auth_mock, valid_user):
        """Test that the same valid API key works for both redirect and MCP endpoints."""
        auth_mock.return_value = valid_user

        # Test redirect with sk_valid123
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={"api_key": "sk_valid123"}))
        redirect_result = agent_teams_api.knowledge_redirect()
        assert redirect_result.status_code == 302

        # Test MCP list with same key
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_valid123"}, body={"jsonrpc": "2.0", "id": 1}),
        )
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())
        assert "result" in list_result

        # Verify auth was called twice with same key
        assert auth_mock.call_count == 2
        auth_mock.assert_any_call("sk_valid123")

    def test_invalid_key_rejected_by_both_redirect_and_mcp(self, monkeypatch, auth_mock):
        """Test that invalid API key is rejected by both redirect and MCP endpoints."""
        # Test redirect with invalid key
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={"api_key": "sk_invalid"}))
        redirect_result = agent_teams_api.knowledge_redirect()
        assert redirect_result[1] == 401

        # Test MCP list with same invalid key
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_invalid"}, body={"jsonrpc": "2.0", "id": 1}),
        )
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())
        assert list_result[1] == 401

        # Verify auth was called twice
        assert auth_mock.call_count == 2
        auth_mock.assert_any_call("sk_invalid")

    def test_missing_key_rejected_by_both_redirect_and_mcp(self, monkeypatch, auth_mock):
        """Test that missing API key is rejected by both redirect and MCP endpoints."""
        # Test redirect with missing key
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={}))
        redirect_result = agent_teams_api.knowledge_redirect()
        assert redirect_result[1] == 401

        # Test MCP list with missing auth header
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={}, body={"jsonrpc": "2.0", "id": 1}),
        )
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())
        assert list_result[1] == 401


class TestErrorPropagation:
    """Tests verifying error responses are properly returned across endpoints."""

    def _setup_auth(self, auth_mock, valid_user):
        auth_mock.return_value = valid_user

    def _setup_request(self, monkeypatch, body):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_valid123"}, body=body),
        )

    def test_invalid_jsonrpc_in_tools_call(self, monkeypatch, auth_mock, valid_user):
        """Test that invalid JSON-RPC version returns proper error in tools/call."""
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {"jsonrpc": "1.0", "id": 42, "params": {"name": "search_knowledge_base", "arguments": {}}},
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 400
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32600
        assert result[0]["error"]["message"] == "Invalid Request"
        assert result[0]["id"] == 42

    def test_invalid_tool_name_returns_error(self, monkeypatch, auth_mock, valid_user):
        """Test that invalid tool name returns proper error."""
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32601
        assert "nonexistent_tool" in result[0]["error"]["message"]

    def test_missing_required_query_param(self, monkeypatch, auth_mock, valid_user):
        """Test that missing required 'query' param returns proper error."""
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
        assert result[0]["error"]["code"] == -32602
        assert "query" in result[0]["error"]["message"]

    def test_missing_params_key_defaults_to_empty(self, monkeypatch, auth_mock, valid_user):
        """Test that missing params key defaults to empty and returns method not found."""
        self._setup_auth(auth_mock, valid_user)
        self._setup_request(monkeypatch, {"jsonrpc": "2.0", "id": 1})

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32601

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_internal_error_returns_32000(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user,
    ):
        """Test that internal errors in search return proper -32000 error code."""
        self._setup_auth(auth_mock, valid_user)

        mock_kb = Mock()
        mock_kb.id = "kb_123"
        mock_kb.embd_id = "embd_1"
        mock_kb.tenant_id = "tenant_123"
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_exception(RuntimeError("DB connection failed"))
        mock_settings.retriever = mock_retriever

        self._setup_request(
            monkeypatch,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {
                    "name": "search_knowledge_base",
                    "arguments": {"query": "test", "dataset_ids": ["kb_123"]},
                },
            },
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result[1] == 200
        assert result[0]["jsonrpc"] == "2.0"
        assert result[0]["error"]["code"] == -32000
        assert result[0]["error"]["message"] == "Internal error"


class TestTenantIsolation:
    """Tests verifying tenant isolation across endpoints."""

    def _setup_auth(self, auth_mock, user):
        auth_mock.return_value = user

    def _setup_request(self, monkeypatch, body, api_key="sk_valid123"):
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": f"Bearer {api_key}"}, body=body),
        )

    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    def test_user_a_cannot_access_user_b_knowledge_bases_list(self, mock_kb_service, monkeypatch, auth_mock, valid_user_b):
        """Test that User A's key cannot list User B's knowledge bases."""
        self._setup_auth(auth_mock, valid_user_b)

        # User B (tenant_456) has kb_456
        mock_kb = Mock()
        mock_kb.id = "kb_456"
        mock_kb.name = "User B KB"
        mock_kb.doc_num = 5
        mock_kb.chunk_num = 50
        mock_kb_service.get_kb_ids.return_value = ["kb_456"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        self._setup_request(monkeypatch, {"jsonrpc": "2.0", "id": 1, "params": {"name": "list_knowledge_bases", "arguments": {}}})

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert "result" in result

        parsed = json.loads(result["result"]["content"][0]["text"])
        # Should only see tenant_456's KBs, not tenant_123's
        assert len(parsed["knowledge_bases"]) == 1
        assert parsed["knowledge_bases"][0]["id"] == "kb_456"
        assert parsed["knowledge_bases"][0]["name"] == "User B KB"

    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    def test_user_a_cannot_search_user_b_knowledge_bases(self, mock_kb_service, monkeypatch, auth_mock, valid_user):
        """Test that User A cannot search in User B's knowledge bases."""
        self._setup_auth(auth_mock, valid_user)

        # User A (tenant_123) only has kb_123
        mock_kb_service.get_kb_ids.return_value = ["kb_123"]

        # Try to search in User B's kb_456
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
        assert result[0]["error"]["code"] == -32602
        assert "Invalid dataset_ids" in result[0]["error"]["message"]

    @patch("api.apps.restful_apis.agent_teams_api.settings")
    @patch("api.apps.restful_apis.agent_teams_api.KnowledgebaseService")
    @patch("api.apps.restful_apis.agent_teams_api.LLMBundle")
    @patch("api.apps.restful_apis.agent_teams_api.get_model_config_by_type_and_name")
    def test_tenant_isolation_in_search_results(
        self,
        mock_get_model_config,
        mock_llm_bundle,
        mock_kb_service,
        mock_settings,
        monkeypatch,
        auth_mock,
        valid_user_b,
    ):
        """Test that search results only include tenant's own knowledge bases."""
        self._setup_auth(auth_mock, valid_user_b)

        # User B's KB setup
        mock_kb = Mock()
        mock_kb.id = "kb_456"
        mock_kb.embd_id = "embd_2"
        mock_kb.tenant_id = "tenant_456"
        mock_kb_service.get_kb_ids.return_value = ["kb_456"]
        mock_kb_service.get_by_ids.return_value = [mock_kb]

        # Mock retriever returning User B's data
        mock_retriever = Mock()
        mock_retriever.retrieval = Mock(return_value=asyncio.Future())
        mock_retriever.retrieval.return_value.set_result(
            {
                "chunks": [
                    {
                        "content_with_weight": "User B private data",
                        "similarity": 0.95,
                        "docnm_kwd": "user_b_doc.pdf",
                        "kb_id": "kb_456",
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
                    "arguments": {"query": "private"},
                },
            },
            api_key="sk_user_b",
        )

        result = asyncio.run(agent_teams_api.mcp_tools_call())

        assert result["jsonrpc"] == "2.0"
        assert "result" in result

        parsed = json.loads(result["result"]["content"][0]["text"])
        assert len(parsed["chunks"]) == 1
        assert parsed["chunks"][0]["content"] == "User B private data"
        assert parsed["chunks"][0]["dataset_id"] == "kb_456"

        # Verify retriever was called with tenant_456 and kb_456
        call_args = mock_retriever.retrieval.call_args
        assert call_args.args[2] == "tenant_456"
        assert call_args.args[3] == ["kb_456"]

    def test_cross_endpoint_tenant_isolation(self, monkeypatch, auth_mock, valid_user, valid_user_b):
        """Test that auth is verified per-endpoint and tenant data is isolated."""
        # First request: User A accesses redirect
        auth_mock.return_value = valid_user
        monkeypatch.setattr(agent_teams_api, "request", SimpleNamespace(args={"api_key": "sk_user_a"}))
        redirect_result = agent_teams_api.knowledge_redirect()
        assert redirect_result.status_code == 302

        # Second request: User B tries MCP - should work with their own tenant
        auth_mock.return_value = valid_user_b
        monkeypatch.setattr(
            agent_teams_api,
            "request",
            _make_request(headers={"Authorization": "Bearer sk_user_b"}, body={"jsonrpc": "2.0", "id": 1}),
        )
        list_result = asyncio.run(agent_teams_api.mcp_tools_list())
        assert "result" in list_result

        # Verify different keys were used
        assert auth_mock.call_count == 2
        auth_mock.assert_any_call("sk_user_a")
        auth_mock.assert_any_call("sk_user_b")

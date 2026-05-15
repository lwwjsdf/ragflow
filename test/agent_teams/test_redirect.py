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

"""Unit tests for agent_teams_api redirect endpoint."""

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
    quart_mod.request = SimpleNamespace(args={})

    def _redirect(location, code=302):
        resp = SimpleNamespace()
        resp.status_code = code
        resp.headers = {"Location": location}
        return resp

    quart_mod.redirect = _redirect
    monkeypatch.setitem(sys.modules, "quart", quart_mod)

    module_path = repo_root / "api" / "apps" / "restful_apis" / "agent_teams_api.py"
    spec = importlib.util.spec_from_file_location("agent_teams_api_test_module", str(module_path))
    module = importlib.util.module_from_spec(spec)
    module.manager = _DummyManager()
    monkeypatch.setitem(sys.modules, "agent_teams_api_test_module", module)
    spec.loader.exec_module(module)
    return module


class TestKnowledgeRedirect:
    """Test suite for GET /knowledge redirect endpoint."""

    def test_missing_api_key_returns_401(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        monkeypatch.setattr(module, "request", SimpleNamespace(args={}))

        result = module.knowledge_redirect()

        assert result[0]["code"] == 401
        assert "api_key" in result[0]["message"].lower() or "unauthorized" in result[0]["message"].lower()
        assert result[1] == 401

    def test_invalid_api_key_returns_401(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        module.authenticate_by_api_key.return_value = None
        monkeypatch.setattr(module, "request", SimpleNamespace(args={"api_key": "invalid_key"}))

        result = module.knowledge_redirect()

        assert result[0]["code"] == 401
        assert result[1] == 401
        module.authenticate_by_api_key.assert_called_once_with("invalid_key")

    def test_valid_api_key_redirects_to_default_path(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(module, "request", SimpleNamespace(args={"api_key": "sk_valid123"}))

        result = module.knowledge_redirect()

        module.authenticate_by_api_key.assert_called_once_with("sk_valid123")
        module.login_user.assert_called_once_with(mock_user)
        assert result.status_code == 302
        assert result.headers["Location"] == "/knowledge/datasets"

    def test_valid_api_key_redirects_to_custom_path(self, monkeypatch):
        module = _load_agent_teams_module(monkeypatch)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        module.authenticate_by_api_key.return_value = {"tenant_id": "tenant_123", "user": mock_user}
        monkeypatch.setattr(module, "request", SimpleNamespace(args={"api_key": "sk_valid123", "redirect": "/custom/path"}))

        result = module.knowledge_redirect()

        module.authenticate_by_api_key.assert_called_once_with("sk_valid123")
        module.login_user.assert_called_once_with(mock_user)
        assert result.status_code == 302
        assert result.headers["Location"] == "/custom/path"

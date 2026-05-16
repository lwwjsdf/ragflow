#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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

"""Unit tests for api.utils.agent_teams_auth module."""

from unittest.mock import Mock, patch

from api.utils.agent_teams_auth import authenticate_by_api_key
from common.constants import StatusEnum


class TestAuthenticateByApiKey:
    """Test suite for authenticate_by_api_key function."""

    def test_empty_api_key_returns_none(self):
        """Test that empty or None api_key returns None."""
        assert authenticate_by_api_key("") is None
        assert authenticate_by_api_key(None) is None
        assert authenticate_by_api_key("   ") is None

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_no_token_found_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that no APIToken found returns None."""
        mock_api_token_service.query.return_value = []

        result = authenticate_by_api_key("invalid_key")

        assert result is None
        mock_api_token_service.query.assert_called_once_with(token="invalid_key")
        mock_user_service.query.assert_not_called()

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_no_valid_user_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that no valid user found returns None."""
        token_obj = Mock()
        token_obj.tenant_id = "tenant_123"
        mock_api_token_service.query.return_value = [token_obj]
        mock_user_service.query.return_value = []

        result = authenticate_by_api_key("valid_key")

        assert result is None
        mock_api_token_service.query.assert_called_once_with(token="valid_key")
        mock_user_service.query.assert_called_once_with(id="tenant_123", status=StatusEnum.VALID.value)

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_user_with_empty_access_token_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that user with empty access_token returns None."""
        token_obj = Mock()
        token_obj.tenant_id = "tenant_123"
        mock_api_token_service.query.return_value = [token_obj]

        user = Mock()
        user.email = "test@example.com"
        user.access_token = ""
        mock_user_service.query.return_value = [user]

        result = authenticate_by_api_key("valid_key")

        assert result is None

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_user_with_none_access_token_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that user with None access_token returns None."""
        token_obj = Mock()
        token_obj.tenant_id = "tenant_123"
        mock_api_token_service.query.return_value = [token_obj]

        user = Mock()
        user.email = "test@example.com"
        user.access_token = None
        mock_user_service.query.return_value = [user]

        result = authenticate_by_api_key("valid_key")

        assert result is None

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_user_service_exception_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that exception from UserService.query returns None."""
        token_obj = Mock()
        token_obj.tenant_id = "tenant_123"
        mock_api_token_service.query.return_value = [token_obj]
        mock_user_service.query.side_effect = Exception("DB error")

        result = authenticate_by_api_key("valid_key")

        assert result is None

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_valid_api_key_returns_auth_result(self, mock_user_service, mock_api_token_service):
        """Test that valid api_key returns auth result with tenant_id and user."""
        token_obj = Mock()
        token_obj.tenant_id = "tenant_123"
        mock_api_token_service.query.return_value = [token_obj]

        user = Mock()
        user.email = "test@example.com"
        user.access_token = "valid_access_token_12345"
        mock_user_service.query.return_value = [user]

        result = authenticate_by_api_key("valid_key")

        assert result is not None
        assert result["tenant_id"] == "tenant_123"
        assert result["user"] == user

    @patch("api.utils.agent_teams_auth.APITokenService")
    @patch("api.utils.agent_teams_auth.UserService")
    def test_exception_returns_none(self, mock_user_service, mock_api_token_service):
        """Test that exception during authentication returns None."""
        mock_api_token_service.query.side_effect = Exception("DB error")

        result = authenticate_by_api_key("valid_key")

        assert result is None

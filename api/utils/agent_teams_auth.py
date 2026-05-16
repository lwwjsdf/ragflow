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
"""Agent teams authentication utilities.

This module provides helper functions for authenticating requests using
agent-teams API keys. It bridges the API token service and user service
to resolve API keys into valid user objects.
"""

import logging

from api.db.services.api_service import APITokenService
from api.db.services.user_service import UserService
from common.constants import StatusEnum


def authenticate_by_api_key(api_key: str) -> dict | None:
    """Authenticate using agent-teams API key.

    Args:
        api_key: The API key to authenticate with.

    Returns:
        dict with "tenant_id" and "user" keys if authentication succeeds,
        None otherwise.
    """
    if not api_key or not api_key.strip():
        return None

    try:
        objs = APITokenService.query(token=api_key)
        if not objs:
            logging.warning(f"No APIToken found for key={api_key[:10]}...")
            return None

        token_obj = objs[0]
        tenant_id = token_obj.tenant_id

        users = UserService.query(id=tenant_id, status=StatusEnum.VALID.value)
        if not users:
            logging.warning(f"No valid user found for tenant_id={tenant_id}")
            return None

        user = users[0]
        if not user.access_token or not user.access_token.strip():
            logging.warning(f"User {user.email} has empty access_token")
            return None

        return {"tenant_id": tenant_id, "user": user}
    except Exception as e:
        logging.exception(f"authenticate_by_api_key error: {e}")
        return None

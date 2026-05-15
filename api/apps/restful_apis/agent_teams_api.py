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

from quart import redirect, request

from api.apps import login_user
from api.utils.agent_teams_auth import authenticate_by_api_key
from api.utils.api_utils import get_json_result
from common.constants import RetCode

page_name = "agent_teams"


@manager.route("/knowledge", methods=["GET"])  # noqa: F821
def knowledge_redirect():
    api_key = request.args.get("api_key")
    if not api_key:
        return get_json_result(code=RetCode.UNAUTHORIZED, message="Missing api_key"), RetCode.UNAUTHORIZED

    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return get_json_result(code=RetCode.UNAUTHORIZED, message="Invalid api_key"), RetCode.UNAUTHORIZED

    user = auth_result["user"]
    login_user(user)

    redirect_path = request.args.get("redirect", "/knowledge/datasets")
    return redirect(redirect_path)

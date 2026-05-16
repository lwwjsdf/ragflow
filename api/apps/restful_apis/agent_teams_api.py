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


@manager.route("/mcp/v1/tools/list", methods=["POST"])  # noqa: F821
async def mcp_tools_list():
    authorization = request.headers.get("Authorization")
    if not authorization:
        return (
            {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": None},
            401,
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return (
            {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": None},
            401,
        )

    api_key = parts[1]
    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return (
            {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": None},
            401,
        )

    tools = [
        {
            "name": "search_knowledge_base",
            "description": "在知识库中检索与查询相关的内容，返回匹配的文本片段",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询文本"},
                    "dataset_ids": {"type": "array", "items": {"type": "string"}, "description": "知识库ID列表"},
                    "top_n": {"type": "integer", "default": 8, "description": "返回结果数量"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_knowledge_bases",
            "description": "列出当前租户下的所有知识库",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    ]

    return {
        "jsonrpc": "2.0",
        "result": {"tools": tools},
        "id": 1,
    }

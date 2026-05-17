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

import json
import logging

from quart import redirect, request

from api.apps import login_user
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api.utils.agent_teams_auth import authenticate_by_api_key
from api.utils.api_utils import get_json_result
from common import settings
from common.constants import LLMType, RetCode

page_name = "agent_teams"

# Default and maximum values for search parameters
DEFAULT_TOP_N = 8
MAX_TOP_N = 100

# Retrieval similarity tuning constants
SIMILARITY_THRESHOLD = 0.2  # Minimum similarity score to include a chunk
VECTOR_SIMILARITY_WEIGHT = 0.3  # Weight given to vector similarity vs keyword
RETRIEVAL_TOP_CANDIDATES = 1024  # Number of candidates to retrieve before ranking


def _mcp_auth_error(rpc_id):
    return (
        {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": rpc_id},
        401,
    )


def _mcp_invalid_request_error(rpc_id):
    return (
        {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": rpc_id},
        400,
    )


def _mcp_method_not_found_error(rpc_id, method_name):
    return (
        {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method_name}"}, "id": rpc_id},
        200,
    )


def _mcp_invalid_params_error(rpc_id, message):
    return (
        {"jsonrpc": "2.0", "error": {"code": -32602, "message": message}, "id": rpc_id},
        200,
    )


def _mcp_internal_error(rpc_id, message):
    return (
        {"jsonrpc": "2.0", "error": {"code": -32000, "message": message}, "id": rpc_id},
        200,
    )


async def _authenticate_mcp_request(body):
    rpc_id = body.get("id") if isinstance(body, dict) else None

    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return _mcp_invalid_request_error(rpc_id), None

    authorization = request.headers.get("Authorization")
    if not authorization:
        return _mcp_auth_error(rpc_id), None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return _mcp_auth_error(rpc_id), None

    api_key = parts[1]
    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return _mcp_auth_error(rpc_id), None

    return None, auth_result


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


TOOLS = [
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


@manager.route("/mcp/v1/tools/list", methods=["POST"])  # noqa: F821
async def mcp_tools_list():
    """Return the list of available MCP tools."""
    body = await request.get_json(silent=True) or {}
    error, auth_result = await _authenticate_mcp_request(body)
    if error:
        return error

    return {
        "jsonrpc": "2.0",
        "result": {"tools": TOOLS},
        "id": body.get("id"),
    }


async def _handle_search_knowledge_base(tenant_id, arguments, rpc_id):
    query = arguments.get("query")
    if not query:
        return _mcp_invalid_params_error(rpc_id, "Missing required parameter: query")

    dataset_ids = arguments.get("dataset_ids", []) or []
    if dataset_ids is not None and not isinstance(dataset_ids, list):
        return _mcp_invalid_params_error(rpc_id, "Invalid parameter: dataset_ids must be a list")

    top_n = arguments.get("top_n", DEFAULT_TOP_N)
    if not isinstance(top_n, int) or top_n < 1:
        top_n = DEFAULT_TOP_N
    top_n = min(top_n, MAX_TOP_N)

    # If no dataset_ids provided, use all tenant KBs
    if not dataset_ids:
        dataset_ids = KnowledgebaseService.get_kb_ids(tenant_id)
    else:
        # Validate that all provided dataset_ids belong to the tenant
        tenant_kb_ids = set(KnowledgebaseService.get_kb_ids(tenant_id))
        requested_ids = set(dataset_ids)
        invalid_ids = requested_ids - tenant_kb_ids
        if invalid_ids:
            return _mcp_invalid_params_error(rpc_id, f"Invalid dataset_ids: {list(invalid_ids)}")

    if not dataset_ids:
        result_text = json.dumps({"chunks": [], "total": 0}, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": rpc_id,
        }

    kbs = KnowledgebaseService.get_by_ids(dataset_ids)
    if not kbs:
        result_text = json.dumps({"chunks": [], "total": 0}, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": rpc_id,
        }

    try:
        embd_nms = list(set([kb.embd_id for kb in kbs]))
        if len(embd_nms) != 1:
            return _mcp_internal_error(rpc_id, "Knowledge bases use different embedding models.")

        embd_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.EMBEDDING, embd_nms[0])
        embd_mdl = LLMBundle(tenant_id, embd_model_config)

        kbinfos = await settings.retriever.retrieval(
            query,
            embd_mdl,
            tenant_id,
            dataset_ids,
            page=1,
            page_size=top_n,
            similarity_threshold=SIMILARITY_THRESHOLD,
            vector_similarity_weight=VECTOR_SIMILARITY_WEIGHT,
            top=RETRIEVAL_TOP_CANDIDATES,
            aggs=False,
        )

        chunks = []
        for c in kbinfos.get("chunks", []):
            c.pop("vector", None)
            chunks.append(
                {
                    "content": c.get("content_with_weight", ""),
                    "score": c.get("similarity", 0.0),
                    "document_name": c.get("docnm_kwd", ""),
                    "dataset_id": c.get("kb_id", ""),
                }
            )

        result = {
            "chunks": chunks,
            "total": len(chunks),
        }
        result_text = json.dumps(result, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": rpc_id,
        }
    except Exception:
        logging.exception("search_knowledge_base failed")
        return _mcp_internal_error(rpc_id, "Internal error")


async def _handle_list_knowledge_bases(tenant_id, rpc_id):
    try:
        kb_ids = KnowledgebaseService.get_kb_ids(tenant_id)
        kbs = KnowledgebaseService.get_by_ids(kb_ids) if kb_ids else []

        kb_list = []
        for kb in kbs:
            kb_list.append(
                {
                    "id": kb.id,
                    "name": kb.name,
                    "document_count": kb.doc_num,
                    "chunk_count": kb.chunk_num,
                }
            )

        result_text = json.dumps({"knowledge_bases": kb_list}, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": rpc_id,
        }
    except Exception:
        logging.exception("list_knowledge_bases failed")
        return _mcp_internal_error(rpc_id, "Internal error")


@manager.route("/mcp/v1/tools/call", methods=["POST"])  # noqa: F821
async def mcp_tools_call():
    """Handle MCP tool calls."""
    body = await request.get_json(silent=True) or {}
    rpc_id = body.get("id") if isinstance(body, dict) else None

    error, auth_result = await _authenticate_mcp_request(body)
    if error:
        return error

    tenant_id = auth_result["tenant_id"]
    params = body.get("params", {})
    if not isinstance(params, dict):
        return _mcp_invalid_params_error(rpc_id, "Invalid params structure")
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return _mcp_invalid_params_error(rpc_id, "Invalid arguments structure")

    if tool_name == "search_knowledge_base":
        return await _handle_search_knowledge_base(tenant_id, arguments, rpc_id)
    elif tool_name == "list_knowledge_bases":
        return await _handle_list_knowledge_bases(tenant_id, rpc_id)
    else:
        return _mcp_method_not_found_error(rpc_id, tool_name)

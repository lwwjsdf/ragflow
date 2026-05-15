# Agent-Teams Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 agent-teams 与 RAGFlow 的集成，通过 API Key 认证支持页面跳转和 MCP 协议知识库检索。

**Architecture:** 新增 API Key 认证中间件、页面跳转端点和 MCP Server 端点，复用现有 Retrieval 工具逻辑，通过 tenant 隔离实现多客户数据安全。

**Tech Stack:** Python 3.12, Quart, Peewee, MCP Protocol, JWT

---

## Prerequisites

- RAGFlow 后端环境已配置 (`uv sync --python 3.12 --all-extras`)
- 数据库服务已启动 (`docker compose -f docker/docker-compose-base.yml up -d`)
- 了解 RAGFlow 的 Blueprint 路由注册机制

---

## Task 1: API Key 认证中间件

**Files:**
- Create: `api/utils/agent_teams_auth.py`
- Modify: `api/apps/__init__.py:138-195` (在 `_load_user` 函数中添加 API Key 解析逻辑)

**Context:** RAGFlow 已有 APIToken 表，存储 tenant_id 和 token 的映射关系。agent-teams 将使用此机制进行认证。

**Step 1: Write the failing test**

```python
# test/agent_teams/test_auth.py
import pytest
from api.utils.agent_teams_auth import authenticate_by_api_key


class TestAgentTeamsAuth:
    def test_authenticate_by_api_key_valid(self):
        # This test will fail until we implement the function
        result = authenticate_by_api_key("test_api_key")
        assert result is not None
        assert result["tenant_id"] == "test_tenant"

    def test_authenticate_by_api_key_invalid(self):
        result = authenticate_by_api_key("invalid_key")
        assert result is None

    def test_authenticate_by_api_key_empty(self):
        result = authenticate_by_api_key("")
        assert result is None
```

**Step 2: Run test to verify it fails**

```bash
cd /root/workspace/ragflow
uv run pytest test/agent_teams/test_auth.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'api.utils.agent_teams_auth'"

**Step 3: Create the auth utility module**

```python
# api/utils/agent_teams_auth.py
import logging
from api.db.services.api_service import APITokenService
from api.db.services.user_service import UserService, TenantService
from common.constants import StatusEnum


def authenticate_by_api_key(api_key: str) -> dict | None:
    """Authenticate a request using an API key for agent-teams integration.
    
    Args:
        api_key: The API key provided by agent-teams.
        
    Returns:
        dict with tenant_id and user info if valid, None otherwise.
    """
    if not api_key or not api_key.strip():
        return None
    
    try:
        # Query APIToken table
        objs = APITokenService.query(token=api_key)
        if not objs:
            logging.warning(f"No APIToken found for key={api_key[:10]}...")
            return None
        
        token_obj = objs[0]
        tenant_id = token_obj.tenant_id
        
        # Verify tenant exists and is valid
        users = UserService.query(id=tenant_id, status=StatusEnum.VALID.value)
        if not users:
            logging.warning(f"No valid user found for tenant_id={tenant_id}")
            return None
        
        user = users[0]
        if not user.access_token or not user.access_token.strip():
            logging.warning(f"User {user.email} has empty access_token")
            return None
        
        return {
            "tenant_id": tenant_id,
            "user": user,
        }
    except Exception as e:
        logging.exception(f"authenticate_by_api_key error: {e}")
        return None
```

**Step 4: Modify _load_user to support API Key from query params**

```python
# Modify api/apps/__init__.py around line 138-195
# After the existing API token check (line 192), add:

    # Try agent-teams API key from query parameters
    try:
        api_key = request.args.get("api_key")
        if api_key:
            from api.utils.agent_teams_auth import authenticate_by_api_key
            auth_result = authenticate_by_api_key(api_key)
            if auth_result:
                g.user = auth_result["user"]
                return auth_result["user"]
    except Exception as e_api_key:
        logging.warning(f"load_user from api_key got exception {e_api_key}")

    return _load_user_from_session()
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest test/agent_teams/test_auth.py -v
```

Expected: Tests should pass or show import errors that we'll fix in Task 2.

**Step 6: Commit**

```bash
git add api/utils/agent_teams_auth.py test/agent_teams/test_auth.py api/apps/__init__.py
git commit -m "feat: add agent-teams API Key authentication middleware"
```

---

## Task 2: 页面跳转端点

**Files:**
- Create: `api/apps/restful_apis/agent_teams_api.py`
- Modify: `api/apps/__init__.py:43` (从 DISABLED_APIS 中移除 agent_teams_api 如果它在里面)

**Context:** 创建 `/knowledge` 端点，接收 api_key 参数，验证后自动登录并重定向到知识库管理页。

**Step 1: Write the failing test**

```python
# test/agent_teams/test_redirect.py
import pytest
from quart.testing import QuartClient


class TestAgentTeamsRedirect:
    @pytest.mark.asyncio
    async def test_redirect_without_api_key(self, client: QuartClient):
        response = await client.get('/api/v1/knowledge')
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_redirect_with_invalid_api_key(self, client: QuartClient):
        response = await client.get('/api/v1/knowledge?api_key=invalid')
        assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest test/agent_teams/test_redirect.py -v
```

Expected: FAIL with 404 (route not found)

**Step 3: Create the redirect endpoint**

```python
# api/apps/restful_apis/agent_teams_api.py
import logging
from quart import Blueprint, request, redirect

from api.apps import login_user, current_user
from api.utils.agent_teams_auth import authenticate_by_api_key
from api.utils.api_utils import get_json_result
from common.constants import RetCode

manager = Blueprint("agent_teams", __name__)


@manager.route("/knowledge", methods=["GET"])
async def knowledge_redirect():
    """Redirect agent-teams users to RAGFlow knowledge base management page.
    
    Query Parameters:
        api_key: The API key for authentication
        redirect: Target path after login (default: /knowledge/datasets)
    """
    api_key = request.args.get("api_key")
    redirect_path = request.args.get("redirect", "/knowledge/datasets")
    
    if not api_key:
        return get_json_result(
            data=False,
            message="Missing API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return get_json_result(
            data=False,
            message="Invalid API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    user = auth_result["user"]
    
    # Log the user in
    login_user(user)
    logging.info(f"Agent-teams user logged in: tenant_id={auth_result['tenant_id']}")
    
    # Redirect to the knowledge base page
    return redirect(redirect_path)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest test/agent_teams/test_redirect.py -v
```

Expected: Tests should pass.

**Step 5: Commit**

```bash
git add api/apps/restful_apis/agent_teams_api.py test/agent_teams/test_redirect.py
git commit -m "feat: add agent-teams knowledge redirect endpoint"
```

---

## Task 3: MCP Server 端点 - 工具列表

**Files:**
- Modify: `api/apps/restful_apis/agent_teams_api.py`

**Context:** 在 agent_teams_api.py 中添加 MCP Server 端点，实现 `tools/list` 和 `tools/call`。

**Step 1: Write the failing test**

```python
# test/agent_teams/test_mcp.py
import pytest
from quart.testing import QuartClient


class TestMCPServer:
    @pytest.mark.asyncio
    async def test_mcp_tools_list_without_auth(self, client: QuartClient):
        response = await client.post('/api/v1/mcp/v1/tools/list')
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_mcp_tools_list_with_auth(self, client: QuartClient):
        response = await client.post(
            '/api/v1/mcp/v1/tools/list',
            headers={"Authorization": "Bearer test_api_key"}
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "tools" in data
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest test/agent_teams/test_mcp.py -v
```

Expected: FAIL with 404 (route not found)

**Step 3: Implement MCP Server endpoints**

```python
# Add to api/apps/restful_apis/agent_teams_api.py

from quart import request, jsonify
from api.utils.api_utils import validate_request


# MCP Tool definitions
MCP_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "在知识库中检索与查询相关的内容，返回匹配的文本片段",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询文本，应包含关键词和同义词"
                },
                "dataset_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要检索的知识库ID列表，为空时检索所有知识库"
                },
                "top_n": {
                    "type": "integer",
                    "default": 8,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "返回结果数量"
                },
                "similarity_threshold": {
                    "type": "number",
                    "default": 0.2,
                    "minimum": 0,
                    "maximum": 1,
                    "description": "相似度阈值"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_knowledge_bases",
        "description": "列出当前租户下的所有知识库，用于选择检索范围",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


@manager.route("/mcp/v1/tools/list", methods=["POST"])
async def mcp_tools_list():
    """List available MCP tools for agent-teams integration."""
    # Authenticate via Authorization header
    auth_header = request.headers.get("Authorization", "")
    api_key = None
    if auth_header.lower().startswith("bearer "):
        api_key = auth_header[7:].strip()
    
    if not api_key:
        return get_json_result(
            data=False,
            message="Missing API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return get_json_result(
            data=False,
            message="Invalid API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    return jsonify({
        "jsonrpc": "2.0",
        "result": {
            "tools": MCP_TOOLS
        },
        "id": 1
    })
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest test/agent_teams/test_mcp.py::TestMCPServer::test_mcp_tools_list_with_auth -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add api/apps/restful_apis/agent_teams_api.py test/agent_teams/test_mcp.py
git commit -m "feat: add MCP tools/list endpoint for agent-teams"
```

---

## Task 4: MCP Server 端点 - 工具调用 (search_knowledge_base)

**Files:**
- Modify: `api/apps/restful_apis/agent_teams_api.py`
- Modify: `api/apps/restful_apis/agent_teams_api.py` (reuse retrieval logic)

**Context:** 实现 `tools/call` 端点，调用现有的检索服务。复用 `api/apps/sdk/dify_retrieval.py` 的检索逻辑。

**Step 1: Write the failing test**

```python
# Add to test/agent_teams/test_mcp.py
class TestMCPSearch:
    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, client: QuartClient):
        response = await client.post(
            '/api/v1/mcp/v1/tools/call',
            headers={"Authorization": "Bearer test_api_key"},
            json={
                "tool": "search_knowledge_base",
                "arguments": {
                    "query": "test query",
                    "top_n": 5
                }
            }
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "result" in data
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest test/agent_teams/test_mcp.py::TestMCPSearch -v
```

Expected: FAIL with 404 or function not defined

**Step 3: Implement tools/call endpoint with search logic**

```python
# Add to api/apps/restful_apis/agent_teams_api.py

import asyncio
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name, get_tenant_default_model_by_type
from common.constants import LLMType
from common import settings
from rag.prompts.generator import kb_prompt
import re


@manager.route("/mcp/v1/tools/call", methods=["POST"])
@validate_request("tool", "arguments")
async def mcp_tools_call():
    """Call an MCP tool for agent-teams integration."""
    # Authenticate via Authorization header
    auth_header = request.headers.get("Authorization", "")
    api_key = None
    if auth_header.lower().startswith("bearer "):
        api_key = auth_header[7:].strip()
    
    if not api_key:
        return get_json_result(
            data=False,
            message="Missing API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    auth_result = authenticate_by_api_key(api_key)
    if not auth_result:
        return get_json_result(
            data=False,
            message="Invalid API Key",
            code=RetCode.UNAUTHORIZED
        ), 401
    
    tenant_id = auth_result["tenant_id"]
    req = await request.get_json()
    tool_name = req.get("tool")
    arguments = req.get("arguments", {})
    
    if tool_name == "search_knowledge_base":
        return await _handle_search_knowledge_base(tenant_id, arguments)
    elif tool_name == "list_knowledge_bases":
        return await _handle_list_knowledge_bases(tenant_id)
    else:
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": f"Tool '{tool_name}' not found"
            },
            "id": 1
        }), 404


async def _handle_search_knowledge_base(tenant_id: str, arguments: dict):
    """Handle search_knowledge_base tool call."""
    query = arguments.get("query", "")
    dataset_ids = arguments.get("dataset_ids", [])
    top_n = arguments.get("top_n", 8)
    similarity_threshold = arguments.get("similarity_threshold", 0.2)
    
    if not query:
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Missing required parameter: query"
            },
            "id": 1
        }), 400
    
    try:
        # Get knowledge bases
        if dataset_ids:
            kbs = KnowledgebaseService.get_by_ids(dataset_ids)
            kbs = [kb for kb in kbs if kb.tenant_id == tenant_id]
        else:
            kbs = KnowledgebaseService.query(tenant_id=tenant_id)
            kbs = list(kbs)
        
        if not kbs:
            return jsonify({
                "jsonrpc": "2.0",
                "result": {
                    "chunks": [],
                    "total": 0,
                    "doc_aggs": []
                },
                "id": 1
            })
        
        kb_ids = [kb.id for kb in kbs]
        
        # Get embedding model
        embd_nms = list(set([kb.embd_id for kb in kbs]))
        embd_mdl = None
        if embd_nms:
            embd_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.EMBEDDING, embd_nms[0])
            embd_mdl = LLMBundle(tenant_id, embd_model_config)
        
        # Perform retrieval
        query = re.sub(r"^user[:\s]*", "", query, flags=re.IGNORECASE)
        kbinfos = await settings.retriever.retrieval(
            query,
            embd_mdl,
            [tenant_id],
            kb_ids,
            1,
            top_n,
            similarity_threshold,
            1 - 0.5,  # keywords_similarity_weight = 0.5
            aggs=True,
            rank_feature=None,
        )
        
        # Format results
        chunks = []
        for ck in kbinfos.get("chunks", []):
            if "vector" in ck:
                del ck["vector"]
            if "content_ltks" in ck:
                del ck["content_ltks"]
            chunks.append({
                "content": ck.get("content_with_weight", ck.get("content", "")),
                "score": ck.get("similarity", 0),
                "document_name": ck.get("docnm_kwd", ""),
                "dataset_id": ck.get("kb_id", ""),
                "chunk_id": ck.get("chunk_id", "")
            })
        
        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "chunks": chunks,
                "total": len(chunks),
                "doc_aggs": kbinfos.get("doc_aggs", [])
            },
            "id": 1
        })
    except Exception as e:
        logging.exception(f"search_knowledge_base error: {e}")
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": f"Search error: {str(e)}"
            },
            "id": 1
        }), 500


async def _handle_list_knowledge_bases(tenant_id: str):
    """Handle list_knowledge_bases tool call."""
    try:
        kbs = KnowledgebaseService.query(tenant_id=tenant_id)
        datasets = []
        for kb in kbs:
            datasets.append({
                "id": kb.id,
                "name": kb.name,
                "document_count": getattr(kb, "document_count", 0),
                "chunk_count": getattr(kb, "chunk_count", 0),
                "create_time": kb.create_time.isoformat() if kb.create_time else None
            })
        
        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "datasets": datasets
            },
            "id": 1
        })
    except Exception as e:
        logging.exception(f"list_knowledge_bases error: {e}")
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": f"List error: {str(e)}"
            },
            "id": 1
        }), 500
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest test/agent_teams/test_mcp.py::TestMCPSearch -v
```

Expected: Tests should pass or show connection errors to dependent services.

**Step 5: Commit**

```bash
git add api/apps/restful_apis/agent_teams_api.py test/agent_teams/test_mcp.py
git commit -m "feat: add MCP tools/call endpoint for knowledge base search"
```

---

## Task 5: 前端页面适配 - 支持 api_key 参数

**Files:**
- Modify: `web/src/pages/knowledge/index.tsx` (or equivalent)

**Context:** 前端页面需要识别 URL 中的 api_key 参数，自动触发认证流程。

**Step 1: Find the knowledge base page entry point**

```bash
grep -r "knowledge/datasets" web/src/ --include="*.tsx" --include="*.ts"
```

**Step 2: Add api_key handling to the page component**

```typescript
// In the knowledge base page component (likely web/src/pages/knowledge/index.tsx)
// Add useEffect to check for api_key in URL

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export default function KnowledgePage() {
  const [searchParams] = useSearchParams();
  
  useEffect(() => {
    const apiKey = searchParams.get('api_key');
    if (apiKey) {
      // The backend should have already authenticated via the middleware
      // Just need to ensure the frontend auth state is updated
      console.log('Authenticated via agent-teams API Key');
    }
  }, [searchParams]);
  
  // ... rest of the component
}
```

**Step 3: Test the frontend changes**

```bash
cd web
npm run build
```

Expected: Build should succeed without errors.

**Step 4: Commit**

```bash
git add web/src/pages/knowledge/index.tsx
git commit -m "feat: support api_key parameter in knowledge base page"
```

---

## Task 6: 集成测试

**Files:**
- Create: `test/agent_teams/test_integration.py`

**Context:** 端到端测试验证整个流程：认证 → 跳转 → 检索。

**Step 1: Write integration tests**

```python
# test/agent_teams/test_integration.py
import pytest
from quart.testing import QuartClient


class TestAgentTeamsIntegration:
    """End-to-end tests for agent-teams integration."""
    
    @pytest.mark.asyncio
    async def test_full_flow(self, client: QuartClient):
        """Test the complete flow: redirect -> list KBs -> search."""
        # Step 1: Redirect with API key
        response = await client.get(
            '/api/v1/knowledge?api_key=test_api_key',
            follow_redirects=False
        )
        assert response.status_code in [302, 307]
        
        # Step 2: List knowledge bases via MCP
        response = await client.post(
            '/api/v1/mcp/v1/tools/call',
            headers={"Authorization": "Bearer test_api_key"},
            json={
                "tool": "list_knowledge_bases",
                "arguments": {}
            }
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "result" in data
        
        # Step 3: Search knowledge base
        response = await client.post(
            '/api/v1/mcp/v1/tools/call',
            headers={"Authorization": "Bearer test_api_key"},
            json={
                "tool": "search_knowledge_base",
                "arguments": {
                    "query": "test",
                    "top_n": 3
                }
            }
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "result" in data
        assert "chunks" in data["result"]
```

**Step 2: Run integration tests**

```bash
uv run pytest test/agent_teams/test_integration.py -v
```

Expected: Tests may show DB connection issues if services aren't running, but should show correct route handling.

**Step 3: Commit**

```bash
git add test/agent_teams/test_integration.py
git commit -m "test: add integration tests for agent-teams integration"
```

---

## Task 7: 文档与配置

**Files:**
- Modify: `docs/plans/2026-05-15-agent-teams-ragflow-integration-design.md` (add implementation notes)
- Create: `docs/agent_teams_integration.md`

**Context:** 创建用户文档，说明如何配置和使用 agent-teams 集成。

**Step 1: Create integration documentation**

```markdown
# Agent-Teams 集成指南

## 概述

本文档说明如何将 agent-teams 与 RAGFlow 集成，实现知识库管理和检索功能的外包。

## 配置步骤

### 1. RAGFlow 侧配置

1. 为每个客户创建 API Key：
   ```bash
   # 在 RAGFlow 管理后台创建 API Token
   # 或使用 API: POST /api/v1/tenants/{tenant_id}/tokens
   ```

2. 确保客户有对应的知识库：
   ```bash
   # 创建知识库
   POST /api/v1/datasets
   ```

### 2. agent-teams 侧配置

在 agent-teams 配置文件中添加：

```yaml
ragflow:
  base_url: "https://ragflow.example.com"
  api_keys:
    customer_a: "sk_abc123"
    customer_b: "sk_def456"
```

### 3. 页面跳转

生成跳转 URL：
```
https://ragflow.example.com/api/v1/knowledge?api_key=sk_abc123&redirect=/knowledge/datasets
```

### 4. MCP 工具调用

LLM 可通过 MCP 协议调用以下工具：

- `search_knowledge_base`: 在知识库中检索内容
- `list_knowledge_bases`: 列出所有知识库

## API 参考

### 认证方式

所有 API 请求需要在 Header 中携带 API Key：
```
Authorization: Bearer <api_key>
```

### 错误码

| 状态码 | 说明 |
|--------|------|
| 401 | API Key 缺失或无效 |
| 403 | Tenant 已禁用 |
| 404 | 知识库不存在 |
| 500 | 服务器内部错误 |
```

**Step 2: Commit**

```bash
git add docs/agent_teams_integration.md
git commit -m "docs: add agent-teams integration guide"
```

---

## Task 8: 代码检查与格式化

**Files:**
- All modified files

**Context:** 运行 lint 和格式化工具确保代码质量。

**Step 1: Run linting**

```bash
cd /root/workspace/ragflow
ruff check api/apps/restful_apis/agent_teams_api.py api/utils/agent_teams_auth.py test/agent_teams/
```

Expected: No critical errors.

**Step 2: Run formatting**

```bash
ruff format api/apps/restful_apis/agent_teams_api.py api/utils/agent_teams_auth.py test/agent_teams/
```

**Step 3: Commit formatting changes**

```bash
git add -A
git commit -m "style: format code with ruff"
```

---

## Summary

This implementation plan covers:

1. **Task 1**: API Key authentication middleware (`api/utils/agent_teams_auth.py`)
2. **Task 2**: Knowledge redirect endpoint (`api/apps/restful_apis/agent_teams_api.py`)
3. **Task 3**: MCP tools/list endpoint
4. **Task 4**: MCP tools/call endpoint with search logic
5. **Task 5**: Frontend adaptation for api_key parameter
6. **Task 6**: Integration tests
7. **Task 7**: Documentation
8. **Task 8**: Code quality checks

**Next Steps:**
- Implement each task in order
- Run tests after each task
- Commit frequently
- Review with the team before deploying to production

**Notes:**
- The `_load_user` function in `api/apps/__init__.py` may need adjustment based on the actual authentication flow
- Frontend changes depend on the exact React component structure
- Make sure to handle edge cases like empty knowledge bases, mixed embedding models, etc.

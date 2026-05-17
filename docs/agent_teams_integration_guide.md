# RAGFlow 对接文档（for agent-teams）

> 本文档面向 agent-teams 开发人员，说明如何在 agent-teams 项目中对接 RAGFlow 的文件上传和知识库检索能力。

---

## 1. 概述

agent-teams 通过以下方式与 RAGFlow 集成：

| 功能 | 方式 | 说明 |
|------|------|------|
| **页面跳转** | URL 重定向 | 用户点击按钮，跳转到 RAGFlow 管理知识库 |
| **知识库检索** | MCP 协议 | LLM 通过 MCP 工具调用检索知识库内容 |

### 架构图

```
agent-teams                              RAGFlow
    │                                       │
    ├── 页面跳转 ──────────────────────────▶│  GET /api/v1/knowledge?api_key=xxx
    │   (浏览器跳转)                         │      ↓
    │                                       │  自动登录 + 重定向到知识库页
    │                                       │
    ├── MCP 工具调用 ──────────────────────▶│  POST /api/v1/mcp/v1/tools/call
    │   (LLM 后端调用)                       │      ↓
    │                                       │  检索知识库并返回结果
```

---

## 2. 前置条件

### 2.1 RAGFlow 侧

1. RAGFlow 服务已部署并可访问
2. 为每个客户（tenant）创建 **API Token**
   - 登录 RAGFlow Web UI
   - 点击右上角头像 → **API**
   - 点击 **Create a new API key**
   - 记录生成的 key（格式：`ragflow-sk-xxxx`）

### 2.2 agent-teams 侧

1. 在 agent-teams 配置中记录每个客户对应的 RAGFlow API Key
2. 配置 RAGFlow Base URL（如：`https://ragflow.example.com`）

---

## 3. 认证方式

所有请求使用 **API Key** 认证：

### 3.1 页面跳转（Query Parameter）

```
GET /api/v1/knowledge?api_key=ragflow-sk-xxxx
```

### 3.2 MCP 调用（Authorization Header）

```http
Authorization: Bearer ragflow-sk-xxxx
```

---

## 4. API 详细说明

### 4.1 页面跳转

让用户免登录进入 RAGFlow 知识库管理页面。

**请求**:

```http
GET /api/v1/knowledge?api_key={api_key}&redirect={redirect_path}
```

**参数**:

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `api_key` | string | 是 | - | RAGFlow API Token |
| `redirect` | string | 否 | `/knowledge/datasets` | 登录后跳转的路径 |

**响应**:

- **成功**: HTTP 302 重定向到指定页面
- **失败**: HTTP 401 + JSON 错误

```json
{
  "code": 401,
  "message": "Invalid api_key",
  "data": false
}
```

**示例**:

```python
import urllib.parse

base_url = "https://ragflow.example.com"
api_key = "ragflow-sk-xxxx"

# 生成跳转 URL
params = {
    "api_key": api_key,
    "redirect": "/knowledge/datasets"
}
url = f"{base_url}/api/v1/knowledge?{urllib.parse.urlencode(params)}"

# 用户点击此 URL 后，将自动登录并跳转到知识库列表页
print(url)
# 输出: https://ragflow.example.com/api/v1/knowledge?api_key=ragflow-sk-xxxx&redirect=%2Fknowledge%2Fdatasets
```

---

### 4.2 MCP 工具列表

获取可用的 MCP 工具列表。

**请求**:

```http
POST /api/v1/mcp/v1/tools/list
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1
}
```

**响应**:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "search_knowledge_base",
        "description": "在知识库中检索与查询相关的内容，返回匹配的文本片段",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "检索查询文本"
            },
            "dataset_ids": {
              "type": "array",
              "items": {"type": "string"},
              "description": "知识库ID列表，为空时检索所有知识库"
            },
            "top_n": {
              "type": "integer",
              "default": 8,
              "description": "返回结果数量"
            }
          },
          "required": ["query"]
        }
      },
      {
        "name": "list_knowledge_bases",
        "description": "列出当前租户下的所有知识库",
        "parameters": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    ]
  }
}
```

---

### 4.3 MCP 工具调用 - 检索知识库

在知识库中搜索与查询相关的内容。

**请求**:

```http
POST /api/v1/mcp/v1/tools/call
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 2,
  "params": {
    "name": "search_knowledge_base",
    "arguments": {
      "query": "如何配置 SSL 证书",
      "dataset_ids": ["kb_123"],
      "top_n": 5
    }
  }
}
```

**参数说明**:

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `query` | string | 是 | - | 检索查询文本 |
| `dataset_ids` | array[string] | 否 | [] | 知识库ID列表，为空时检索所有知识库 |
| `top_n` | integer | 否 | 8 | 返回结果数量，范围 1-100 |

**响应（成功）**:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "## 检索结果\\n\\n### 文档：服务器配置指南.pdf\\n**相似度**: 0.95\\n\\nSSL 证书配置步骤：\\n1. 生成 CSR 文件...\\n\\n---\\n\\n### 文档：运维手册.docx\\n**相似度**: 0.87\\n\\n在生产环境中配置 SSL..."
      }
    ]
  }
}
```

**响应（失败示例）**:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Missing required parameter: query"
  }
}
```

---

### 4.4 MCP 工具调用 - 列出知识库

获取当前租户下的所有知识库列表。

**请求**:

```http
POST /api/v1/mcp/v1/tools/call
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 3,
  "params": {
    "name": "list_knowledge_bases",
    "arguments": {}
  }
}
```

**响应**:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "## 知识库列表\\n\\n| ID | 名称 | 文档数 | 切片数 |\\n|---|---|---|---|\\n| kb_123 | 产品文档 | 15 | 1024 |\\n| kb_124 | 技术规范 | 8 | 512 |"
      }
    ]
  }
}
```

---

## 5. 与 LLM 集成示例

agent-teams 的 LLM 可以通过 MCP 协议调用 RAGFlow 的检索能力。

### 5.1 Python 示例

```python
import requests
import json

class RAGFlowMCPClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    def search_knowledge_base(self, query: str, dataset_ids: list = None, top_n: int = 8) -> dict:
        """在知识库中检索内容"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {
                "name": "search_knowledge_base",
                "arguments": {
                    "query": query,
                    "top_n": top_n
                }
            }
        }
        if dataset_ids:
            payload["params"]["arguments"]["dataset_ids"] = dataset_ids
        
        response = requests.post(
            f"{self.base_url}/api/v1/mcp/v1/tools/call",
            headers=self.headers,
            json=payload
        )
        return response.json()
    
    def list_knowledge_bases(self) -> dict:
        """列出所有知识库"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {
                "name": "list_knowledge_bases",
                "arguments": {}
            }
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/mcp/v1/tools/call",
            headers=self.headers,
            json=payload
        )
        return response.json()
    
    def generate_redirect_url(self, redirect_path: str = "/knowledge/datasets") -> str:
        """生成页面跳转 URL"""
        import urllib.parse
        params = {
            "api_key": self.api_key,
            "redirect": redirect_path,
        }
        query = urllib.parse.urlencode(params)
        return f"{self.base_url}/api/v1/knowledge?{query}"


# 使用示例
client = RAGFlowMCPClient(
    base_url="https://ragflow.example.com",
    api_key="ragflow-sk-xxxx"
)

# 检索知识库
result = client.search_knowledge_base(
    query="如何配置 SSL 证书",
    top_n=5
)
print(json.dumps(result, indent=2, ensure_ascii=False))

# 列出知识库
kbs = client.list_knowledge_bases()
print(json.dumps(kbs, indent=2, ensure_ascii=False))

# 生成跳转 URL
url = client.generate_redirect_url()
print(f"跳转 URL: {url}")
```

### 5.2 JavaScript/TypeScript 示例

```typescript
class RAGFlowMCPClient {
  private baseUrl: string;
  private apiKey: string;
  
  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }
  
  async searchKnowledgeBase(
    query: string, 
    datasetIds?: string[], 
    topN: number = 8
  ): Promise<any> {
    const payload = {
      jsonrpc: "2.0",
      id: 1,
      params: {
        name: "search_knowledge_base",
        arguments: {
          query,
          top_n: topN,
          ...(datasetIds && { dataset_ids: datasetIds })
        }
      }
    };
    
    const response = await fetch(`${this.baseUrl}/api/v1/mcp/v1/tools/call`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    return response.json();
  }
  
  async listKnowledgeBases(): Promise<any> {
    const payload = {
      jsonrpc: "2.0",
      id: 1,
      params: {
        name: "list_knowledge_bases",
        arguments: {}
      }
    };
    
    const response = await fetch(`${this.baseUrl}/api/v1/mcp/v1/tools/call`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    return response.json();
  }
  
  generateRedirectUrl(redirectPath: string = '/knowledge/datasets'): string {
    const params = new URLSearchParams({
      api_key: this.apiKey,
      redirect: redirectPath,
    });
    return `${this.baseUrl}/api/v1/knowledge?${params.toString()}`;
  }
}

// 使用示例
const client = new RAGFlowMCPClient(
  'https://ragflow.example.com',
  'ragflow-sk-xxxx'
);

// 检索知识库
client.searchKnowledgeBase('如何配置 SSL 证书', undefined, 5)
  .then(result => console.log(result));

// 列出知识库
client.listKnowledgeBases()
  .then(result => console.log(result));

// 生成跳转 URL
const url = client.generateRedirectUrl();
console.log(`跳转 URL: ${url}`);
```

---

## 6. 错误码说明

### 6.1 页面跳转错误

| HTTP 状态码 | 说明 |
|------------|------|
| 401 | API Key 缺失或无效 |

### 6.2 MCP 错误码

MCP 端点返回 JSON-RPC 2.0 格式的错误：

| JSON-RPC Code | HTTP 状态码 | 说明 |
|--------------|------------|------|
| -32001 | 401 | 认证失败（API Key 缺失或无效） |
| -32600 | 400 | 无效请求（JSON-RPC 格式错误） |
| -32601 | 200 | 工具不存在 |
| -32602 | 200 | 参数无效（缺少必填参数或类型错误） |
| -32000 | 200 | 内部错误（检索服务异常） |

**常见错误场景**:

1. **API Key 无效**:
```json
{
  "jsonrpc": "2.0",
  "error": {"code": -32001, "message": "Unauthorized"},
  "id": 1
}
```

2. **缺少必填参数**:
```json
{
  "jsonrpc": "2.0",
  "error": {"code": -32602, "message": "Missing required parameter: query"},
  "id": 1
}
```

3. **JSON-RPC 版本错误**:
```json
{
  "jsonrpc": "2.0",
  "error": {"code": -32600, "message": "Invalid Request"},
  "id": null
}
```

---

## 7. 数据隔离说明

- 每个客户在 RAGFlow 中对应一个 **tenant**
- API Key 绑定到特定 tenant
- 所有检索操作自动按 tenant 隔离
- agent-teams 只需管理好 **客户 ↔ API Key** 的映射关系

---

## 8. 最佳实践

### 8.1 API Key 管理

- 在 agent-teams 中加密存储 API Key
- 支持 API Key 轮换（定期更新）
- 为每个客户使用独立的 API Key

### 8.2 错误处理

- 始终检查 HTTP 状态码和 JSON-RPC error code
- 对 401 错误提示用户重新配置 API Key
- 对 -32000 内部错误记录日志并重试

### 8.3 性能优化

- `top_n` 建议设置为 5-10，最大不超过 100
- 如需指定知识库，使用 `dataset_ids` 减少检索范围
- 缓存知识库列表，避免频繁调用 `list_knowledge_bases`

### 8.4 用户体验

- 页面跳转使用 `target="_blank"` 在新标签页打开 RAGFlow
- LLM 检索结果建议显示来源文档名称和相似度分数
- 提供"管理知识库"按钮，跳转到 RAGFlow 上传文档

---

## 9. 更新记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-15 | v1.0 | 初始版本，支持页面跳转和 MCP 检索 |

---

## 10. 附录

### 10.1 完整的 OpenAPI 风格描述

```yaml
openapi: 3.0.0
info:
  title: RAGFlow Agent-Teams Integration API
  version: 1.0.0

paths:
  /api/v1/knowledge:
    get:
      summary: 页面跳转（自动登录）
      parameters:
        - name: api_key
          in: query
          required: true
          schema:
            type: string
        - name: redirect
          in: query
          schema:
            type: string
            default: /knowledge/datasets
      responses:
        '302':
          description: 重定向到目标页面
        '401':
          description: 认证失败

  /api/v1/mcp/v1/tools/list:
    post:
      summary: 列出 MCP 工具
      security:
        - BearerAuth: []
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                jsonrpc:
                  type: string
                  enum: ["2.0"]
                id:
                  type: [integer, string, null]
      responses:
        '200':
          description: 工具列表

  /api/v1/mcp/v1/tools/call:
    post:
      summary: 调用 MCP 工具
      security:
        - BearerAuth: []
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                jsonrpc:
                  type: string
                  enum: ["2.0"]
                id:
                  type: [integer, string, null]
                params:
                  type: object
                  properties:
                    name:
                      type: string
                    arguments:
                      type: object
      responses:
        '200':
          description: 工具执行结果

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```

### 10.2 联系支持

- RAGFlow 文档: https://ragflow.io/docs
- 问题反馈: https://github.com/infiniflow/ragflow/issues

# Agent-Teams 与 RAGFlow 集成设计文档

**日期**: 2026-05-15  
**主题**: agent-teams 集成 RAGFlow 文件上传与知识库检索能力  
**状态**: 已审批

---

## 1. 概述

本文档描述 agent-teams（独立项目）与 RAGFlow 的集成方案，将文件上传和管理功能剥离给 RAGFlow，同时暴露知识库检索能力给 agent-teams 的 LLM 使用。

### 1.1 背景

- **agent-teams**: 独立的多智能体协作项目，需要文件管理和知识库检索能力
- **RAGFlow**: 开源 RAG 引擎，已具备完整的文件上传、知识库管理和检索能力
- **目标**: 通过 REST API 和 MCP 协议，让 agent-teams 复用 RAGFlow 的能力，避免重复建设

### 1.2 核心需求

1. **页面跳转**: agent-teams 用户可一键跳转到 RAGFlow 管理知识库
2. **自动认证**: 无需 SSO，通过 API Key 自动识别租户
3. **知识库检索**: 通过 MCP 协议暴露检索工具给 agent-teams 的 LLM
4. **数据隔离**: 每个客户（tenant）在 RAGFlow 中有独立的知识库空间

---

## 2. 架构设计

### 2.1 整体架构

```
agent-teams                          RAGFlow
    │                                    │
    ├─► 页面跳转 ──────────────────────►│ /knowledge?api_key=xxx
    │   (自动识别 tenant)                │   (根据 api_key 加载知识库)
    │                                    │
    ├─► MCP 调用 ──────────────────────►│ /mcp/v1/tools/call
    │   Authorization: Bearer <key>      │   (验证 api_key，按 tenant 隔离)
    │                                    │
    └─► 知识库列表查询 ─────────────────►│ /mcp/v1/tools/list
```

### 2.2 核心组件

#### 2.2.1 API Key 认证中间件

- 拦截所有请求，从 URL 参数或请求头提取 `api_key`
- 验证 API Key 对应的 tenant 是否存在且有效
- 将 tenant_id 注入到请求上下文中
- 复用 RAGFlow 现有的 API Key 机制

#### 2.2.2 页面跳转端点 (`/knowledge`)

- 接收 `api_key` 查询参数
- 验证 API Key，获取 tenant_id
- 设置 session（有效期 24 小时）
- 重定向到知识库管理页面

#### 2.2.3 MCP Server (`/mcp/v1/`)

- 基于 MCP 协议实现工具暴露
- 支持 `tools/list` 和 `tools/call` 端点
- 每个请求自动携带 tenant 上下文
- 复用 RAGFlow 现有的 `Retrieval` 工具逻辑

#### 2.2.4 知识库检索服务

- 复用现有 `Retrieval` 组件
- 按 tenant_id 过滤知识库访问权限
- 支持多知识库联合检索

### 2.3 Tenant 映射关系

```
agent-teams          RAGFlow
   客户A  ────────►  Tenant A (api_key_a)
   客户B  ────────►  Tenant B (api_key_b)
   客户C  ────────►  Tenant C (api_key_c)
```

- agent-teams 为每个客户预配置 RAGFlow API Key
- API Key 在 RAGFlow 中绑定到特定 tenant
- 所有操作通过 API Key 自动路由到对应 tenant

---

## 3. API 设计

### 3.1 页面跳转

```http
GET /knowledge?api_key=<api_key>&redirect=/knowledge/datasets
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| api_key | string | 是 | agent-teams 客户的 API Key |
| redirect | string | 否 | 登录后跳转页面，默认 `/knowledge/datasets` |

**响应**:

- 成功: 302 重定向到目标页面，设置 session cookie
- 失败: 重定向到错误页面

### 3.2 MCP Server 端点

```http
POST /mcp/v1/tools/list
Authorization: Bearer <api_key>
```

**响应**:

```json
{
  "tools": [
    {
      "name": "search_knowledge_base",
      "description": "在知识库中检索与查询相关的内容",
      "parameters": { ... }
    },
    {
      "name": "list_knowledge_bases",
      "description": "列出当前租户下的所有知识库",
      "parameters": { ... }
    }
  ]
}
```

```http
POST /mcp/v1/tools/call
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "tool": "search_knowledge_base",
  "arguments": {
    "query": "如何配置 SSL 证书",
    "top_n": 5
  }
}
```

### 3.3 工具定义

#### 3.3.1 search_knowledge_base

```json
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
}
```

**返回示例**:

```json
{
  "chunks": [
    {
      "content": "SSL 证书配置步骤：1. 生成 CSR 文件...",
      "score": 0.95,
      "document_name": "服务器配置指南.pdf",
      "dataset_id": "kb_123",
      "chunk_id": "chunk_456"
    }
  ],
  "total": 10,
  "doc_aggs": [
    {
      "doc_name": "服务器配置指南.pdf",
      "doc_id": "doc_789",
      "count": 3
    }
  ]
}
```

#### 3.3.2 list_knowledge_bases

```json
{
  "name": "list_knowledge_bases",
  "description": "列出当前租户下的所有知识库，用于选择检索范围",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

**返回示例**:

```json
{
  "datasets": [
    {
      "id": "kb_123",
      "name": "产品文档",
      "document_count": 15,
      "chunk_count": 1024,
      "create_time": "2026-01-15T10:00:00Z"
    },
    {
      "id": "kb_124",
      "name": "技术规范",
      "document_count": 8,
      "chunk_count": 512,
      "create_time": "2026-02-20T14:30:00Z"
    }
  ]
}
```

---

## 4. 数据流设计

### 4.1 场景一：页面跳转流程

```
1. agent-teams 用户点击"知识库管理"按钮
   │
   ▼
2. agent-teams 生成跳转 URL
   https://ragflow.example.com/knowledge?api_key=sk_abc123
   │
   ▼
3. 浏览器打开 RAGFlow 跳转端点
   │
   ▼
4. RAGFlow 验证 api_key
   - 查询 api_key 对应的 tenant
   - 检查 tenant 状态和权限
   │
   ▼
5. 设置 session
   - 生成 session token
   - 绑定 tenant_id
   - 设置 httpOnly secure cookie
   │
   ▼
6. 重定向到知识库列表页
   │
   ▼
7. 用户在 RAGFlow 中管理知识库
   - 创建/删除知识库
   - 上传/删除文档
   - 查看解析状态和检索测试
```

### 4.2 场景二：MCP 检索流程

```
1. agent-teams LLM 收到用户查询
   例如："如何配置 SSL 证书？"
   │
   ▼
2. LLM 分析查询，决定调用 search_knowledge_base
   │
   ▼
3. agent-teams 发送 MCP 请求
   POST /mcp/v1/tools/call
   Authorization: Bearer sk_abc123
   {
     "tool": "search_knowledge_base",
     "arguments": {
       "query": "SSL 证书配置",
       "top_n": 5
     }
   }
   │
   ▼
4. RAGFlow MCP Server 处理请求
   a. 从 Authorization header 提取 api_key
   b. 验证 api_key，获取 tenant_id
   c. 调用 Retrieval 服务
   d. 按 tenant_id 过滤知识库范围
   e. 执行向量检索 + 重排序
   │
   ▼
5. 返回检索结果给 LLM
   {
     "chunks": [...],
     "total": 10
   }
   │
   ▼
6. LLM 基于检索结果生成回答
   "根据知识库中的《服务器配置指南》，配置 SSL 证书的步骤如下：..."
```

### 4.3 场景三：知识库列表同步

```
1. agent-teams 初始化或定期同步
   │
   ▼
2. 调用 list_knowledge_bases
   │
   ▼
3. RAGFlow 返回该 tenant 下所有知识库
   │
   ▼
4. agent-teams 缓存知识库列表
   - 用于下拉选择框
   - 用于自动补全
   - 用于权限校验
```

---

## 5. 错误处理

### 5.1 API Key 相关错误

| 场景 | HTTP 状态码 | 错误响应 |
|------|-------------|----------|
| API Key 缺失 | 401 | `{"error": "Missing API Key"}` |
| API Key 无效 | 401 | `{"error": "Invalid API Key"}` |
| API Key 已过期 | 401 | `{"error": "API Key expired"}` |
| Tenant 已禁用 | 403 | `{"error": "Tenant disabled"}` |

### 5.2 检索相关错误

| 场景 | HTTP 状态码 | 错误响应 |
|------|-------------|----------|
| 知识库不存在 | 404 | `{"error": "Dataset not found"}` |
| 知识库为空 | 200 | `{"chunks": [], "total": 0}` |
| 检索超时 | 504 | `{"error": "Search timeout"}` |
| Embedding 模型不匹配 | 400 | `{"error": "Mixed embedding models"}` |
| 参数无效 | 400 | `{"error": "Invalid parameters"}` |

### 5.3 页面跳转错误

| 场景 | 处理方式 |
|------|----------|
| API Key 无效 | 重定向到错误页面，显示"认证失败，请联系管理员" |
| Tenant 无知识库 | 正常跳转，显示空状态，引导创建知识库 |
| Session 过期 | 重定向到登录页面（agent-teams 重新生成跳转 URL） |

### 5.4 MCP 协议错误

遵循 MCP 规范，错误响应格式：

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  },
  "id": 1
}
```

常见错误码：

| 错误码 | 含义 |
|--------|------|
| -32700 | Parse error |
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32000 | Server error |

---

## 6. 安全设计

### 6.1 认证机制

- **API Key**: 使用 RAGFlow 现有的 API Key 体系
- **传输安全**: 所有请求强制 HTTPS
- **Session 管理**: 
  - Session cookie 设置 httpOnly 和 secure 标志
  - Session 有效期 24 小时
  - 支持手动登出清除 session

### 6.2 数据隔离

- **Tenant 级别**: 每个客户对应一个 RAGFlow tenant
- **知识库级别**: 知识库归属特定 tenant
- **检索范围**: MCP 检索自动过滤当前 tenant 的知识库
- **权限校验**: 所有数据库查询自动附加 tenant_id 过滤条件

### 6.3 限流与防护

- **API 限流**: 每个 API Key 限制请求频率（默认 100/min）
- **IP 白名单**: 可选配置 agent-teams 服务器 IP 白名单
- **请求大小限制**: 上传文件限制 100MB，查询文本限制 10KB

---

## 7. 测试策略

### 7.1 单元测试

| 测试项 | 说明 |
|--------|------|
| API Key 验证 | 测试有效、无效、过期 API Key 的处理 |
| Tenant 权限 | 测试 tenant 数据隔离，确保无法访问其他 tenant 数据 |
| MCP 参数校验 | 测试必填参数、类型检查、范围限制 |
| 工具调用路由 | 测试 tools/list 和 tools/call 的正确路由 |

### 7.2 集成测试

| 测试项 | 说明 |
|--------|------|
| 端到端检索 | 上传文档 → 等待索引完成 → 检索 → 验证结果 |
| 多 tenant 隔离 | 在 tenant A 上传文档，确保 tenant B 检索不到 |
| 页面跳转流程 | 生成跳转 URL → 访问 → 验证自动登录 → 管理知识库 |
| MCP 协议兼容 | 使用标准 MCP 客户端测试工具列表和调用 |

### 7.3 性能测试

| 测试项 | 目标 |
|--------|------|
| 并发检索 | 100 并发请求，P99 延迟 < 2s |
| 大知识库检索 | 10k+ 文档的知识库，检索延迟 < 3s |
| 页面加载 | 跳转后首屏加载 < 2s |

---

## 8. 部署与配置

### 8.1 RAGFlow 侧配置

```yaml
# 新增配置项
agent_teams:
  enabled: true
  api_key_header: "Authorization"
  api_key_prefix: "Bearer "
  session_ttl: 86400  # 24 hours
  max_upload_size: 104857600  # 100MB
  rate_limit: 100  # requests per minute
```

### 8.2 agent-teams 侧配置

```yaml
# agent-teams 配置示例
ragflow:
  base_url: "https://ragflow.example.com"
  api_keys:
    customer_a: "sk_abc123"
    customer_b: "sk_def456"
  default_redirect: "/knowledge/datasets"
```

---

## 9. 方案对比与决策

### 9.1 方案对比

| 维度 | 方案一: MCP Server | 方案二: REST API 代理 | 方案三: 混合模式 |
|------|-------------------|---------------------|----------------|
| 复杂度 | 中等 | 低 | 高 |
| 标准化 | 高（MCP 协议） | 中（自定义 API） | 中 |
| LLM 兼容性 | 原生支持 | 需 Function Calling | 原生支持 |
| 维护成本 | 低 | 中 | 高 |
| 扩展性 | 高 | 中 | 高 |
| 实现工作量 | 中等 | 低 | 高 |

### 9.2 决策

**选择方案一：MCP Server 模式**

理由：
1. RAGFlow 已有 `MCPToolCallSession` 和 `ToolCallSession` 基础实现
2. MCP 是 LLM 工具调用的行业标准协议
3. 一次实现，多处受益（其他系统也可通过 MCP 接入）
4. 无需修改 agent-teams 架构，只需配置 API Key 和 MCP 端点

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| MCP 协议变更 | 中 | 关注 MCP 规范更新，预留版本兼容层 |
| 大文件上传超时 | 中 | 支持分片上传，增加进度反馈 |
| 检索性能瓶颈 | 高 | 监控检索延迟，必要时增加 Embedding 缓存 |
| API Key 泄露 | 高 | 支持 API Key 轮换，增加访问日志审计 |
| 多租户数据泄露 | 高 | 严格的 tenant_id 过滤，集成测试覆盖 |

---

## 11. 附录

### 11.1 术语表

| 术语 | 说明 |
|------|------|
| MCP | Model Context Protocol，模型上下文协议，用于 LLM 工具调用的标准协议 |
| Tenant | RAGFlow 中的租户，对应一个独立的工作空间 |
| Dataset | 知识库，包含一组文档和索引 |
| Chunk | 文档切片，检索的最小单位 |
| Embedding | 文本向量，用于语义检索 |

### 11.2 参考文档

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [RAGFlow API 文档](https://ragflow.io/docs/api)
- [RAGFlow 架构文档](https://ragflow.io/docs/architecture)

---

**审批人**:  
**审批日期**: 2026-05-15

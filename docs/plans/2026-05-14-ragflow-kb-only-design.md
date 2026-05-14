# RAGFlow Knowledge Base Only - 裁剪与集成设计文档

**日期**: 2026-05-14
**方案**: 方案1 - 浅层裁剪（前端隐藏 + 后端禁用 API）
**目标**: 将 RAGFlow 裁剪为纯知识库引擎，与 Agent-Teams 系统打通

---

## 1. 概述

### 1.1 背景

RAGFlow 是一个功能完整的 RAG 平台，包含：
- 知识库管理（Dataset/Document/Chunk）
- 文档解析（DeepDoc）
- 向量检索（Elasticsearch）
- 聊天对话（Chat）
- Agent 工作流（Agent Canvas）
- 记忆管理（Memory）
- 代码执行沙箱（Sandbox）

### 1.2 需求

用户只需要 RAGFlow 的**知识库核心能力**：
- 知识库创建与管理
- 文档上传与解析
- 分块管理
- 向量检索

**不需要**的能力：
- 聊天对话（Chat）
- Agent 工作流（Agent）
- 记忆管理（Memory）
- 代码执行沙箱（Sandbox）

### 1.3 集成目标

将裁剪后的 RAGFlow 作为**知识库服务**，通过 REST API 和 MCP 协议与 **Agent-Teams**（TypeScript/Node.js 项目）打通。

---

## 2. 裁剪设计

### 2.1 前端 UI 裁剪

#### 修改文件: `web/src/layouts/components/global-navbar.tsx`

**移除的菜单项：**
- Chat（聊天）
- Agent（智能体）
- Memory（记忆）

**保留的菜单项：**
- Home（首页）
- Knowledge Base（知识库）
- Files（文件管理）
- Search（搜索测试，可选）

#### 修改文件: `web/src/routes.tsx`

**移除的路由：**
```typescript
// 从 Routes enum 中移除：
Agent = '/agent'
AgentTemplates = '/agent-templates'
Agents = '/agents'
Explore = '/explore'
AgentExplore = `${Routes.Agent}/:id/explore`
Memories = '/memories'
Memory = '/memory'
MemoryMessage = '/memory-message'
MemorySetting = '/memory-setting'
AgentList = '/agent-list'
Chats = '/chats'
Chat = '/chat'
Skills = '/files/skills'
// ... 所有 Agent/Chat/Memory 相关子路由
```

**保留的路由：**
```typescript
Root = '/'
Login = '/login-next'
Home = '/home'
Datasets = '/datasets'
DatasetBase = '/dataset'
Files = '/files'
Dataset = `${Routes.DatasetBase}/${Routes.Files}`
Searches = '/searches'           // 可选保留
Search = '/search'
SearchShare = '/search/share'
Chunk = '/chunk'
ChunkResult = `${Chunk}${Chunk}`
Parsed = '/parsed'
ParsedResult = `${Chunk}${Parsed}`
Result = '/result'
ResultView = `${Chunk}${Result}`
KnowledgeGraph = '/knowledge-graph'
UserSetting = '/user-setting'
DataSetOverview = '/logs'
DataSetSetting = '/configuration'
Admin = '/admin'
```

### 2.2 后端 API 裁剪

#### 修改文件: `api/apps/__init__.py`

在 `search_pages_path()` 函数中增加过滤逻辑：

```python
# 裁剪配置
DISABLED_APIS = {
    'chat_api',      # 聊天对话
    'agent_api',     # Agent 工作流
    'memory_api',    # 记忆管理
    'openai_api',    # OpenAI 兼容 API
    'mcp_api',       # MCP Server（将自建）
    'plugin_api',    # 插件系统
}

def search_pages_path(page_path):
    app_path_list = [
        path for path in page_path.glob("*_app.py")
        if not path.name.startswith(".")
    ]
    # 过滤掉禁用的 API
    app_path_list = [
        path for path in app_path_list
        if path.stem.removesuffix("_app") not in DISABLED_APIS
    ]
    # ... SDK 和 restful_apis 同理过滤
    return app_path_list
```

#### API 保留 vs 禁用对照表

| 状态 | API 模块 | 说明 |
|------|---------|------|
| ✅ **保留** | `dataset_api.py` | 知识库 CRUD |
| ✅ **保留** | `document_api.py` | 文档上传/管理 |
| ✅ **保留** | `chunk_api.py` | 分块管理 |
| ✅ **保留** | `file_api.py` | 文件管理 |
| ✅ **保留** | `search_api.py` | 搜索/检索 |
| ✅ **保留** | `user_api.py` | 用户认证 |
| ✅ **保留** | `tenant_api.py` | 租户管理 |
| ✅ **保留** | `system_api.py` | 系统配置 |
| ✅ **保留** | `stats_api.py` | 统计信息 |
| ✅ **保留** | `connector_api.py` | 数据源连接 |
| ✅ **保留** | `langfuse_api.py` | 监控追踪 |
| ❌ **禁用** | `chat_api.py` | 聊天对话 |
| ❌ **禁用** | `agent_api.py` | Agent 工作流 |
| ❌ **禁用** | `memory_api.py` | 记忆管理 |
| ❌ **禁用** | `openai_api.py` | OpenAI 兼容 API |
| ❌ **禁用** | `mcp_api.py` | MCP Server（将自建） |
| ❌ **禁用** | `plugin_api.py` | 插件系统 |

### 2.3 保留的代码文件

浅层裁剪**不删除**任何代码文件，只是不注册它们。保留的文件包括：
- `agent/` - Agent 引擎代码
- `memory/` - 记忆管理代码
- `api/apps/restful_apis/chat_api.py`
- `api/apps/restful_apis/agent_api.py`
- `api/apps/restful_apis/memory_api.py`

**原因：**
- 便于后续同步上游更新（git merge）
- 降低裁剪风险
- 保留扩展可能性

---

## 3. Agent-Teams 集成设计

### 3.1 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent-Teams 系统 (TypeScript/Node.js)     │
│  ┌─────────┐ ┌─────────┐ ┌───────────────────────────────┐ │
│  │ Planner │ │ Executor│ │     RAGFlow Client (TS)       │ │
│  └────┬────┘ └────┬────┘ └──────────────┬──────────────┘ │
│       └───────────┴─────────────────────┘                │
│                   HTTP REST API / MCP                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────┐
│              RAGFlow (裁剪后 - 纯知识库引擎)                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Dataset │ │Document │ │ Chunk   │ │   Retrieval     │  │
│  │  API    │ │  API    │ │  API    │ │     API         │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘  │
│                                                            │
│  底层：MySQL + Elasticsearch + Redis + MinIO                │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 集成方式

#### 方式 1: REST API 直接调用（基础）

Agent-Teams 后端直接调用 RAGFlow HTTP API。

**TypeScript 客户端 SDK:**

```typescript
// ragflow-client.ts
class RAGFlowKBClient {
  async retrieve(
    datasetId: string,
    query: string,
    topK: number = 5,
    similarityThreshold: number = 0.2
  ): Promise<RetrievalResult[]>

  async createDataset(
    name: string,
    description: string = ''
  ): Promise<string>

  async uploadDocument(
    datasetId: string,
    file: File,
    metadata?: Record<string, any>
  ): Promise<string>

  async listDatasets(): Promise<Dataset[]>
}
```

#### 方式 2: MCP 协议（推荐）

通过 MCP Server 标准化工具调用，Agent 可自主发现和使用知识库工具。

**MCP 工具列表：**
1. `search_knowledge` - 检索知识库
2. `upload_document` - 上传文档
3. `list_datasets` - 列出知识库
4. `get_document_status` - 查询文档状态

**Agent-Teams MCP 配置:**

```json
{
  "mcpServers": {
    "ragflow-kb": {
      "url": "http://ragflow-host:9382/sse",
      "apiKey": "ragflow-api-key"
    }
  }
}
```

### 3.3 端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| RAGFlow REST API | 9380 | 核心 API |
| RAGFlow MCP Server | 9382 | MCP 协议接口 |
| RAGFlow Admin | 9381 | 管理后台（可选） |
| Web UI (Dev) | 8080 | 开发模式前端 |
| MySQL | 3306 | 元数据存储 |
| Elasticsearch | 1200 | 向量数据库 |
| Redis | 6379 | 缓存/队列 |
| MinIO | 9000/9001 | 对象存储 |

---

## 4. 实施步骤

### Phase 1: 前端裁剪
1. 修改 `web/src/layouts/components/global-navbar.tsx` - 移除 Chat/Agent/Memory 菜单
2. 修改 `web/src/routes.tsx` - 移除对应路由
3. 重启 Vite dev server 验证

### Phase 2: 后端裁剪
1. 修改 `api/apps/__init__.py` - 添加 DISABLED_APIS 过滤
2. 重启 RAGFlow API server 验证
3. 测试保留 API 正常工作，禁用 API 返回 404

### Phase 3: Agent-Teams SDK
1. 创建 TypeScript SDK (`ragflow-client.ts`)
2. 实现核心方法：retrieve, upload, createDataset, listDatasets
3. 在 Agent-Teams 中集成 SDK

### Phase 4: MCP Server（可选）
1. 启动 RAGFlow 内置 MCP Server（如果支持）
2. 或自建独立 MCP Server
3. 在 Agent-Teams 中配置 MCP Client

---

## 5. 验证清单

### 前端验证
- [x] 导航栏只显示 Home/Knowledge Base/Files/Search
- [x] 直接访问 /chat 返回 404
- [x] 直接访问 /agent 返回 404
- [x] 直接访问 /memory 返回 404

### 后端验证
- [x] `GET /api/v1/datasets` 正常返回
- [x] `POST /api/v1/datasets` 可创建知识库
- [x] `POST /api/dify/retrieval` 可检索
- [x] `GET /api/v1/chats` 返回 404
- [x] `GET /api/v1/agents` 返回 404

### 集成验证
- [x] Agent-Teams 可调用 `retrieve()` 获取结果
- [x] Agent-Teams 可调用 `uploadDocument()` 上传文件
- [x] MCP `search_knowledge` 工具可用

---

## 6. 风险与回滚

### 风险
- **风险1**: 误删被其他模块依赖的代码
  - **缓解**: 浅层裁剪只禁用注册，不删除文件
- **风险2**: 前端路由移除后，某些内部跳转报错
  - **缓解**: 保留必要的子路由（如 chunk/result 等）

### 回滚
如需恢复完整功能：
1. 还原 `global-navbar.tsx` 中的 menuItems
2. 还原 `routes.tsx` 中的路由定义
3. 移除 `api/apps/__init__.py` 中的 DISABLED_APIS 过滤

---

## 6. TypeScript SDK 实现

### 6.1 概述

TypeScript SDK 已在 `docker/integration/ragflow-client.ts` 实现，为 Agent-Teams 系统提供与 RAGFlow 知识库交互的客户端。

### 6.2 核心类

#### `RAGFlowKBClient`

知识库操作客户端，封装 RAGFlow REST API：

```typescript
class RAGFlowKBClient {
  constructor(baseURL: string, apiKey: string)
  
  async retrieve(
    datasetId: string,
    query: string,
    topK?: number,
    similarityThreshold?: number
  ): Promise<RetrievalResult[]>
  
  async createDataset(name: string, description?: string): Promise<string>
  async uploadDocument(datasetId: string, file: File, metadata?: object): Promise<string>
  async listDatasets(): Promise<Dataset[]>
}
```

#### `RAGFlowTool`

MCP 工具封装，暴露为 Agent 可调用的工具：

```typescript
class RAGFlowTool {
  constructor(client: RAGFlowKBClient)
  
  async searchKnowledge(params: SearchParams): Promise<ToolResult>
  async uploadDocument(params: UploadParams): Promise<ToolResult>
  async listDatasets(): Promise<ToolResult>
}
```

### 6.3 技术特性

- **原生 fetch API**：无需额外 HTTP 客户端依赖
- **跨平台支持**：兼容 Node.js 18+ 和浏览器环境
- **类型安全**：完整的 TypeScript 类型定义
- **错误处理**：统一异常捕获和格式化

### 6.4 实现状态

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 1 | ✅ 完成 | 前端 UI 裁剪 |
| Task 2 | ✅ 完成 | 后端 API 裁剪 |
| Task 3 | ✅ 完成 | TypeScript SDK 实现 |
| Task 4 | ✅ 完成 | SDK 集成测试 |

---

## 7. 附录

### 7.1 保留的 Web UI 页面

| 页面 | 路径 | 说明 |
|------|------|------|
| Home | `/` | 知识库首页 |
| Datasets | `/datasets` | 知识库列表 |
| Dataset Detail | `/dataset/:id` | 知识库详情 |
| Files | `/files` | 文件管理 |
| Search | `/search` | 检索测试 |
| Chunk | `/chunk` | 分块管理 |
| Admin | `/admin` | 管理后台 |

### 7.2 核心 API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/datasets` | 列出知识库 |
| POST | `/api/v1/datasets` | 创建知识库 |
| GET | `/api/v1/datasets/:id/documents` | 列出文档 |
| POST | `/api/v1/datasets/:id/documents` | 上传文档 |
| POST | `/api/v1/datasets/:id/chunks` | 触发解析 |
| POST | `/api/dify/retrieval` | 检索知识 |
| GET | `/api/v1/user` | 用户信息 |
| POST | `/api/v1/user/login` | 用户登录 |

### 7.3 相关文件

- 客户端 SDK: `docker/integration/ragflow_client.py`（Python 参考）
- 迁移指南: `docker/integration/MIGRATION_GUIDE.md`
- 前端路由: `web/src/routes.tsx`
- 前端导航: `web/src/layouts/components/global-navbar.tsx`
- 后端注册: `api/apps/__init__.py`

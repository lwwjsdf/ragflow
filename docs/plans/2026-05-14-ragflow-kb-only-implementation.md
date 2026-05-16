# RAGFlow Knowledge Base Only - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 RAGFlow 裁剪为纯知识库引擎（隐藏 Chat/Agent/Memory 入口），提供 TypeScript SDK 和 MCP 协议供 Agent-Teams 集成。

**Architecture:** 浅层裁剪方案 - 前端隐藏菜单+路由，后端禁用 API Blueprint 注册。代码文件保留，通过配置控制功能开关。Agent-Teams 通过 REST API 或 MCP 协议调用 RAGFlow 知识库服务。

**Tech Stack:** TypeScript/React (前端), Python/Quart (后端), Elasticsearch (向量数据库), MCP (模型上下文协议)

---

## Task 1: 前端导航栏裁剪

**Files:**
- Modify: `web/src/layouts/components/global-navbar.tsx:20-40`

**Step 1: 修改导航栏菜单项**

编辑 `web/src/layouts/components/global-navbar.tsx`，移除 Chat/Agent/Memory 菜单：

```typescript
// 修改前：
const menuItems = [
  { path: Routes.Root, name: 'header.Root', icon: LucideHouse },
  { path: Routes.Datasets, name: 'header.dataset' },
  { path: Routes.Chats, name: 'header.chat', 'data-testid': 'nav-chat' },
  { path: Routes.Searches, name: 'header.search', 'data-testid': 'nav-search' },
  { path: Routes.Agents, name: 'header.flow', 'data-testid': 'nav-agent' },
  { path: Routes.Memories, name: 'header.memories' },
  { path: Routes.Files, name: 'header.fileManager' },
];

// 修改后：
const menuItems = [
  { path: Routes.Root, name: 'header.Root', icon: LucideHouse },
  { path: Routes.Datasets, name: 'header.dataset' },
  { path: Routes.Searches, name: 'header.search', 'data-testid': 'nav-search' },
  { path: Routes.Files, name: 'header.fileManager' },
];
```

**Step 2: 验证前端编译**

```bash
cd /root/workspace/ragflow/web
npm run build 2>&1 | tail -20
```

Expected: Build succeeds without errors related to missing routes.

**Step 3: Commit**

```bash
cd /root/workspace/ragflow
git add web/src/layouts/components/global-navbar.tsx
git commit -m "feat(kb-only): remove Chat/Agent/Memory from navigation bar"
```

---

## Task 2: 前端路由表裁剪

**Files:**
- Modify: `web/src/routes.tsx:12-77`

**Step 1: 从 Routes enum 中移除不需要的路由**

```typescript
// 在 web/src/routes.tsx 中，注释或删除以下路由：
// Agent = '/agent',
// AgentTemplates = '/agent-templates',
// Agents = '/agents',
// Explore = '/explore',
// AgentExplore = `${Routes.Agent}/:id/explore`,
// Memories = '/memories',
// Memory = '/memory',
// MemoryMessage = '/memory-message',
// MemorySetting = '/memory-setting',
// AgentList = '/agent-list',
// Chats = '/chats',
// Chat = '/chat',
// Skills = '/files/skills',
```

**Step 2: 从路由配置中移除对应的 lazy import 和 route definition**

搜索文件中的 `Agent`, `Chat`, `Memory` 相关路由配置并移除。

**Step 3: 验证编译**

```bash
cd /root/workspace/ragflow/web
npm run build 2>&1 | grep -i "error" | head -10
```

Expected: No errors related to missing Agent/Chat/Memory routes.

**Step 4: Commit**

```bash
cd /root/workspace/ragflow
git add web/src/routes.tsx
git commit -m "feat(kb-only): remove Chat/Agent/Memory routes from frontend"
```

---

## Task 3: 后端 API Blueprint 禁用

**Files:**
- Modify: `api/apps/__init__.py` (末尾附近)

**Step 1: 在 `search_pages_path` 函数中添加过滤逻辑**

找到 `api/apps/__init__.py` 中的 `search_pages_path` 函数（约 line 300+）：

```python
# 在函数开头添加：
DISABLED_APIS = {
    'chat_api',
    'agent_api', 
    'memory_api',
    'openai_api',
    'mcp_api',
    'plugin_api',
}

def search_pages_path(page_path):
    app_path_list = [
        path for path in page_path.glob("*_app.py") 
        if not path.name.startswith(".")
    ]
    
    # 过滤掉禁用的 API 模块
    app_path_list = [
        path for path in app_path_list
        if path.stem not in DISABLED_APIS
    ]
    
    api_path_list = [
        path for path in page_path.glob("*sdk/*.py") 
        if not path.name.startswith(".")
    ]
    # SDK 同理过滤
    api_path_list = [
        path for path in api_path_list
        if path.stem not in DISABLED_APIS
    ]
    
    app_path_list.extend(api_path_list)
    
    restful_api_path_list = [
        path for path in page_path.glob("*restful_apis/*.py")
        if not path.name.startswith(".")
    ]
    # RESTful APIs 同理过滤
    restful_api_path_list = [
        path for path in restful_api_path_list
        if path.stem not in DISABLED_APIS
    ]
    
    app_path_list.extend(restful_api_path_list)
    return app_path_list
```

**Step 2: 重启 RAGFlow API server 验证**

```bash
# 停止现有服务
pkill -f "ragflow_server.py"

# 重新启动
export PYTHONPATH=/root/workspace/ragflow
cd /root/workspace/ragflow
nohup .venv/bin/python3 api/ragflow_server.py > logs/ragflow.log 2>&1 &

# 等待启动
sleep 10
```

**Step 3: 验证 API 禁用生效**

```bash
# 保留的 API 应该正常工作（返回 401 表示路由存在，只是未认证）
curl -s http://localhost:9380/api/v1/datasets | grep -o '"code":[0-9]*'
# Expected: "code":401

# 禁用的 API 应该返回 404
curl -s http://localhost:9380/api/v1/chats | grep -o '"code":[0-9]*'
# Expected: "code":404

curl -s http://localhost:9380/api/v1/agents | grep -o '"code":[0-9]*'
# Expected: "code":404

curl -s http://localhost:9380/api/v1/memories | grep -o '"code":[0-9]*'
# Expected: "code":404
```

**Step 4: Commit**

```bash
cd /root/workspace/ragflow
git add api/apps/__init__.py
git commit -m "feat(kb-only): disable Chat/Agent/Memory/OpenAI/MCP/Plugin APIs"
```

---

## Task 4: 创建 TypeScript SDK

**Files:**
- Create: `docker/integration/ragflow-client.ts`

**Step 1: 编写 TypeScript SDK**

```typescript
// docker/integration/ragflow-client.ts

export interface RAGFlowConfig {
  baseUrl: string;
  apiKey: string;
}

export interface RetrievalResult {
  content: string;
  document_name: string;
  score: number;
  dataset_id?: string;
  document_id?: string;
  chunk_id?: string;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  document_count: number;
  chunk_count: number;
  create_time: string;
  update_time: string;
}

export class RAGFlowKBClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(config: RAGFlowConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.headers = {
      'Authorization': `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json'
    };
  }

  // 检索知识（核心方法）
  async retrieve(
    datasetId: string,
    query: string,
    topK: number = 5,
    similarityThreshold: number = 0.2
  ): Promise<RetrievalResult[]> {
    const response = await fetch(`${this.baseUrl}/api/dify/retrieval`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        knowledge_id: datasetId,
        query,
        retrieval_setting: {
          top_k: topK,
          score_threshold: similarityThreshold
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Retrieval failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    if (data.retcode !== 0) {
      throw new Error(`Retrieval failed: ${data.retmsg}`);
    }

    return data.data?.records || [];
  }

  // 创建知识库
  async createDataset(
    name: string,
    description: string = '',
    embeddingModel: string = 'BAAI/bge-m3'
  ): Promise<string> {
    const response = await fetch(`${this.baseUrl}/api/v1/datasets`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        name,
        description,
        embedding_model: embeddingModel,
        chunk_method: 'naive',
        parser_config: {
          chunk_token_num: 128,
          delimiter: '\\n!?;。；！？',
          layout_recognize: true
        }
      })
    });

    const data = await response.json();
    return data.data?.id;
  }

  // 列出知识库
  async listDatasets(page: number = 1, pageSize: number = 30): Promise<Dataset[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/datasets?page=${page}&page_size=${pageSize}`,
      { headers: this.headers }
    );

    const data = await response.json();
    return data.data?.docs || [];
  }

  // 上传文档
  async uploadDocument(
    datasetId: string,
    file: File,
    metadata?: Record<string, any>
  ): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('meta_data', JSON.stringify(metadata));
    }

    const response = await fetch(
      `${this.baseUrl}/api/v1/datasets/${datasetId}/documents`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: formData
      }
    );

    const data = await response.json();
    return data.data?.id;
  }

  // 启动文档解析
  async startParsing(datasetId: string, documentIds: string[]): Promise<boolean> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/datasets/${datasetId}/chunks`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({ document_ids: documentIds })
      }
    );

    return response.ok;
  }
}

// 工具类 - 供 Agent 框架使用
export class RAGFlowTool {
  constructor(private client: RAGFlowKBClient) {}

  // Agent 工具：搜索知识库
  async searchKnowledge(query: string, datasetName?: string): Promise<string> {
    let datasetId: string | undefined;

    if (datasetName) {
      const datasets = await this.client.listDatasets(1, 100);
      const ds = datasets.find(d => d.name === datasetName);
      if (ds) datasetId = ds.id;
    }

    if (!datasetId) {
      const datasets = await this.client.listDatasets(1, 1);
      if (datasets.length === 0) return '未找到知识库';
      datasetId = datasets[0].id;
    }

    const records = await this.client.retrieve(datasetId, query, 5, 0.2);

    if (records.length === 0) {
      return '未找到相关内容';
    }

    return records.map((r, i) =>
      `[来源 ${i + 1}] ${r.document_name} (相关度: ${r.score.toFixed(2)})\n${r.content.substring(0, 500)}...`
    ).join('\n\n');
  }

  // Agent 工具：添加文档
  async addDocument(
    file: File,
    datasetName: string,
    metadata?: Record<string, any>
  ): Promise<string> {
    const datasets = await this.client.listDatasets(1, 100);
    let datasetId = datasets.find(d => d.name === datasetName)?.id;

    if (!datasetId) {
      datasetId = await this.client.createDataset(datasetName);
    }

    const docId = await this.client.uploadDocument(datasetId, file, metadata);
    await this.client.startParsing(datasetId, [docId]);

    return `文档已上传并开始解析，文档ID: ${docId}`;
  }
}
```

**Step 2: Commit SDK**

```bash
cd /root/workspace/ragflow
git add docker/integration/ragflow-client.ts
git commit -m "feat(integration): add TypeScript SDK for Agent-Teams"
```

---

## Task 5: 更新设计文档为最终版本

**Files:**
- Modify: `docs/plans/2026-05-14-ragflow-kb-only-design.md`

**Step 1: 在文档末尾添加 TypeScript SDK 章节**

已在设计文档中包含，确保以下章节完整：
- Section 3.2 方式1: REST API 直接调用
- 附录 7.4 TypeScript SDK 示例

**Step 2: Commit 最终设计文档**

```bash
cd /root/workspace/ragflow
git add docs/plans/2026-05-14-ragflow-kb-only-design.md
git commit -m "docs: finalize RAGFlow KB-only design document"
```

---

## Task 6: 验证端到端流程

**Step 1: 测试前端访问**

```bash
# 浏览器访问
open http://localhost:8080
# 确认导航栏只有：Home / Knowledge Base / Files / Search
```

**Step 2: 测试 API 禁用**

```bash
# 禁用 API 返回 404
curl -s http://localhost:9380/api/v1/chats | python3 -m json.tool
# Expected: {"code": 404, "message": "Not Found: /api/v1/chats"}

# 保留 API 正常工作
curl -s http://localhost:9380/api/v1/datasets | python3 -m json.tool
# Expected: {"code": 401, "message": "<Unauthorized '401: Unauthorized'>"}
```

**Step 3: 测试 TypeScript SDK**

在 Agent-Teams 项目中：

```typescript
import { RAGFlowKBClient } from './ragflow-client';

const client = new RAGFlowKBClient({
  baseUrl: 'http://ragflow-host:9380',
  apiKey: 'your-api-key'
});

async function test() {
  const datasets = await client.listDatasets();
  console.log('知识库列表:', datasets);
}

test();
```

---

## 实施顺序

1. **Task 1**: 前端导航栏裁剪
2. **Task 2**: 前端路由表裁剪
3. **Task 3**: 后端 API Blueprint 禁用
4. **Task 4**: 创建 TypeScript SDK
5. **Task 5**: 更新设计文档
6. **Task 6**: 验证端到端流程

**预计总时间**: 2-3 小时

---

## 回滚方案

如需恢复完整功能：

```bash
# 1. 还原导航栏
git checkout web/src/layouts/components/global-navbar.tsx

# 2. 还原路由表
git checkout web/src/routes.tsx

# 3. 还原后端 API 注册（移除 DISABLED_APIS 过滤）
# 手动编辑 api/apps/__init__.py，移除过滤逻辑

# 4. 重启服务
pkill -f "ragflow_server.py"
export PYTHONPATH=/root/workspace/ragflow
nohup .venv/bin/python3 api/ragflow_server.py > logs/ragflow.log 2>&1 &
```

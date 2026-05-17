# Agent Teams Integration Guide

This document describes how to integrate RAGFlow with agent-teams, enabling seamless knowledge base access through page redirects and MCP tool calls.

## Overview

The agent-teams integration provides two primary capabilities:

1. **Page Redirect**: Generate authenticated URLs that allow users to jump directly into RAGFlow's knowledge base interface.
2. **MCP Tools**: Expose RAGFlow knowledge bases as Model Context Protocol (MCP) tools, enabling AI agents to search and list knowledge bases programmatically.

## Configuration Steps

### RAGFlow Side: Create API Token

1. Log in to the RAGFlow web UI.
2. Click your avatar in the top right corner and navigate to **API**.
3. Click **Create a new API key** to generate a token.
4. Copy and securely store the generated key (e.g., `ragflow-sk-xxxx`).

For detailed instructions, see [Acquire RAGFlow API key](../develop/acquire_ragflow_api_key.md).

### Agent Teams Side: Configure API Key Mapping

1. In the agent-teams admin console, navigate to **Integrations > RAGFlow**.
2. Paste the RAGFlow API key into the **RAGFlow API Key** field.
3. Set the **RAGFlow Base URL** to your RAGFlow instance (e.g., `https://your-ragflow-domain.com`).
4. Save the configuration. Agent-teams will use this key to authenticate all requests to RAGFlow.

## API Reference

### Page Redirect URL Format

Generate a URL to redirect users directly to a RAGFlow knowledge base page.

**Endpoint**: `GET /agent_teams/knowledge`

**Query Parameters**:

| Parameter | Type   | Required | Description                                      |
|-----------|--------|----------|--------------------------------------------------|
| `api_key` | string | Yes      | RAGFlow API token                                |
| `redirect`| string | No       | Target path after login (default: `/knowledge/datasets`) |

**Example URL**:
```
https://your-ragflow-domain.com/agent_teams/knowledge?api_key=ragflow-sk-xxxx&redirect=/knowledge/datasets
```

**Behavior**:
- Validates the `api_key` against RAGFlow's API token store.
- Logs the user in and sets the session.
- Redirects to the specified path (or default).

### MCP Endpoint Description

Agent-teams exposes two MCP tools for interacting with RAGFlow knowledge bases.

**Endpoint**: `POST /agent_teams/mcp/v1/tools/list`

Lists all available MCP tools.

**Request Body** (JSON-RPC 2.0):
```json
{
  "jsonrpc": "2.0",
  "id": 1
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "search_knowledge_base",
        "description": "Search knowledge bases for relevant content",
        "parameters": {
          "type": "object",
          "properties": {
            "query": { "type": "string" },
            "dataset_ids": { "type": "array", "items": { "type": "string" } },
            "top_n": { "type": "integer", "default": 8 }
          },
          "required": ["query"]
        }
      },
      {
        "name": "list_knowledge_bases",
        "description": "List all knowledge bases for the current tenant",
        "parameters": { "type": "object", "properties": {} }
      }
    ]
  }
}
```

**Endpoint**: `POST /agent_teams/mcp/v1/tools/call`

Calls a specific MCP tool.

**Request Body** (JSON-RPC 2.0):
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "params": {
    "name": "search_knowledge_base",
    "arguments": {
      "query": "SSL configuration",
      "dataset_ids": ["kb_123"],
      "top_n": 5
    }
  }
}
```

### Authentication Method

All MCP endpoints require Bearer token authentication.

**Header**:
```
Authorization: Bearer <ragflow_api_key>
```

The redirect endpoint uses query parameter authentication (`?api_key=<key>`).

## Example Code

### Generate Redirect URL

```python
import urllib.parse

BASE_URL = "https://your-ragflow-domain.com"
API_KEY = "ragflow-sk-xxxx"

def generate_redirect_url(redirect_path="/knowledge/datasets"):
    params = {
        "api_key": API_KEY,
        "redirect": redirect_path,
    }
    query = urllib.parse.urlencode(params)
    return f"{BASE_URL}/agent_teams/knowledge?{query}"

# Example usage
url = generate_redirect_url("/knowledge/datasets")
print(url)
```

### Call MCP Tools

```python
import requests

BASE_URL = "https://your-ragflow-domain.com"
API_KEY = "ragflow-sk-xxxx"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# 1. List available tools
list_payload = {
    "jsonrpc": "2.0",
    "id": 1,
}
response = requests.post(f"{BASE_URL}/agent_teams/mcp/v1/tools/list", json=list_payload, headers=headers)
print(response.json())

# 2. Search knowledge base
call_payload = {
    "jsonrpc": "2.0",
    "id": 2,
    "params": {
        "name": "search_knowledge_base",
        "arguments": {
            "query": "SSL configuration",
            "dataset_ids": ["kb_123"],
            "top_n": 5,
        },
    },
}
response = requests.post(f"{BASE_URL}/agent_teams/mcp/v1/tools/call", json=call_payload, headers=headers)
print(response.json())

# 3. List knowledge bases
call_payload = {
    "jsonrpc": "2.0",
    "id": 3,
    "params": {
        "name": "list_knowledge_bases",
        "arguments": {},
    },
}
response = requests.post(f"{BASE_URL}/agent_teams/mcp/v1/tools/call", json=call_payload, headers=headers)
print(response.json())
```

## Error Code Reference

### Redirect Endpoint Errors

| HTTP Status | Code | Description                        |
|-------------|------|------------------------------------|
| 401         | 401  | Missing or invalid `api_key`       |

### MCP Endpoint Errors

MCP endpoints return JSON-RPC 2.0 error objects.

| JSON-RPC Code | HTTP Status | Description                        |
|---------------|-------------|------------------------------------|
| -32001        | 401         | Unauthorized (missing/invalid key) |
| -32600        | 400         | Invalid Request (bad JSON-RPC)     |
| -32601        | 200         | Method not found (unknown tool)    |
| -32602        | 200         | Invalid params (bad arguments)     |
| -32000        | 200         | Internal error (server failure)    |

**Common Error Scenarios**:

- **Missing Authorization header**: Returns `-32001` (401).
- **Invalid API key**: Returns `-32001` (401).
- **Wrong JSON-RPC version**: Returns `-32600` (400).
- **Unknown tool name**: Returns `-32601` (200).
- **Missing required `query` parameter**: Returns `-32602` (200).
- **Invalid `dataset_ids` (not tenant-owned)**: Returns `-32602` (200).
- **Retriever failure**: Returns `-32000` (200).

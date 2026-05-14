/**
 * RAGFlow TypeScript SDK for Agent-Teams
 *
 * A lightweight client for integrating RAGFlow's knowledge base capabilities
 * into TypeScript/Node.js agent frameworks.
 */

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface RAGFlowConfig {
  /** Base URL of the RAGFlow API server (e.g., http://localhost:9380) */
  baseUrl: string;
  /** API key for authentication */
  apiKey: string;
}

export interface RetrievalResult {
  /** Unique identifier of the retrieved chunk */
  id: string;
  /** The text content of the retrieved chunk */
  content: string;
  /** Document name the chunk belongs to */
  documentName: string;
  /** Similarity score (0-1) */
  score: number;
  /** Document ID the chunk belongs to */
  documentId: string;
  /** Chunk metadata */
  metadata?: Record<string, unknown>;
}

export interface Dataset {
  /** Unique identifier of the dataset */
  id: string;
  /** Name of the dataset */
  name: string;
  /** Description of the dataset */
  description?: string;
  /** Embedding model used */
  embeddingModel?: string;
  /** Number of documents in the dataset */
  documentCount?: number;
  /** Creation timestamp */
  createdAt?: string;
}

interface RAGFlowApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

interface RAGFlowRetrievalData {
  chunks: Array<{
    chunk_id: string;
    content_with_weight: string;
    doc_id: string;
    doc_name: string;
    similarity?: number;
    [key: string]: unknown;
  }>;
}

interface RAGFlowDatasetData {
  id: string;
  name: string;
  description?: string;
  embedding_model?: string;
  document_count?: number;
  create_time?: string;
  [key: string]: unknown;
}

interface RAGFlowDocumentData {
  id: string;
  name: string;
  [key: string]: unknown;
}

// ============================================================================
// RAGFlowKBClient - Core API Client
// ============================================================================

export class RAGFlowKBClient {
  private baseUrl: string;
  private apiKey: string;

  /**
   * Create a new RAGFlow knowledge base client
   * @param config - Configuration object containing baseUrl and apiKey
   */
  constructor(config: RAGFlowConfig) {
    if (!config.baseUrl) {
      throw new Error('RAGFlowKBClient: baseUrl is required');
    }
    if (!config.apiKey) {
      throw new Error('RAGFlowKBClient: apiKey is required');
    }

    // Remove trailing slash from baseUrl
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.apiKey = config.apiKey;
  }

  /**
   * Make an authenticated request to the RAGFlow API
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = new Headers(options.headers || {});

    // Add authorization header
    headers.set('Authorization', `Bearer ${this.apiKey}`);

    // Add Content-Type for JSON requests if not already set and not FormData
    if (
      !(options.body instanceof FormData) &&
      !headers.has('Content-Type') &&
      options.method !== 'GET'
    ) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(
        `RAGFlow API error (${response.status}): ${errorBody || response.statusText}`
      );
    }

    // Some endpoints may return empty body
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return response.json() as Promise<T>;
    }

    return null as T;
  }

  /**
   * Retrieve knowledge from a dataset
   * @param datasetId - The dataset ID to search
   * @param query - The search query
   * @param topK - Number of results to return (default: 5)
   * @param similarityThreshold - Minimum similarity threshold (default: 0.5)
   * @returns Array of retrieval results
   */
  async retrieve(
    datasetId: string,
    query: string,
    topK: number = 5,
    similarityThreshold: number = 0.5
  ): Promise<RetrievalResult[]> {
    if (!datasetId) {
      throw new Error('retrieve: datasetId is required');
    }
    if (!query) {
      throw new Error('retrieve: query is required');
    }

    const response = await this.request<RAGFlowApiResponse<RAGFlowRetrievalData>>(
      '/api/dify/retrieval',
      {
        method: 'POST',
        body: JSON.stringify({
          dataset_id: datasetId,
          question: query,
          top_k: topK,
          similarity_threshold: similarityThreshold,
        }),
      }
    );

    if (response.code !== 0) {
      throw new Error(`RAGFlow retrieval error: ${response.message}`);
    }

    return (response.data?.chunks || []).map((chunk) => ({
      id: chunk.chunk_id,
      content: chunk.content_with_weight,
      documentName: chunk.doc_name,
      score: chunk.similarity || 0,
      documentId: chunk.doc_id,
      metadata: Object.fromEntries(
        Object.entries(chunk).filter(
          ([key]) =>
            ![
              'chunk_id',
              'content_with_weight',
              'doc_id',
              'doc_name',
              'similarity',
            ].includes(key)
        )
      ),
    }));
  }

  /**
   * Create a new dataset
   * @param name - Name of the dataset
   * @param description - Optional description
   * @param embeddingModel - Optional embedding model name
   * @returns The created dataset
   */
  async createDataset(
    name: string,
    description?: string,
    embeddingModel?: string
  ): Promise<Dataset> {
    if (!name) {
      throw new Error('createDataset: name is required');
    }

    const response = await this.request<RAGFlowApiResponse<RAGFlowDatasetData>>(
      '/api/v1/datasets',
      {
        method: 'POST',
        body: JSON.stringify({
          name,
          description: description || '',
          embedding_model: embeddingModel || '',
        }),
      }
    );

    if (response.code !== 0) {
      throw new Error(`RAGFlow create dataset error: ${response.message}`);
    }

    return this.mapDataset(response.data);
  }

  /**
   * List all datasets
   * @param page - Page number (default: 1)
   * @param pageSize - Items per page (default: 30)
   * @returns Array of datasets
   */
  async listDatasets(
    page: number = 1,
    pageSize: number = 30
  ): Promise<Dataset[]> {
    const response = await this.request<
      RAGFlowApiResponse<{ datasets: RAGFlowDatasetData[] }>
    >(`/api/v1/datasets?page=${page}&page_size=${pageSize}`, {
      method: 'GET',
    });

    if (response.code !== 0) {
      throw new Error(`RAGFlow list datasets error: ${response.message}`);
    }

    return (response.data?.datasets || []).map((d) => this.mapDataset(d));
  }

  /**
   * Upload a document to a dataset
   * @param datasetId - The dataset ID
   * @param file - The file to upload (Blob, File, or Buffer)
   * @param metadata - Optional metadata
   * @returns The uploaded document info
   */
  async uploadDocument(
    datasetId: string,
    file: Blob | File | Buffer,
    metadata?: Record<string, unknown>
  ): Promise<{ id: string; name: string; status: string }> {
    if (!datasetId) {
      throw new Error('uploadDocument: datasetId is required');
    }
    if (!file) {
      throw new Error('uploadDocument: file is required');
    }

    const formData = new FormData();

    // Handle different file types
    if (typeof Blob !== 'undefined' && file instanceof Blob) {
      formData.append('file', file);
    } else if (Buffer.isBuffer(file)) {
      // Node.js Buffer
      const blob = new Blob([file]);
      formData.append('file', blob, 'document');
    } else {
      throw new Error('uploadDocument: file must be a Blob, File, or Buffer');
    }

    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await this.request<
      RAGFlowApiResponse<{ documents: RAGFlowDocumentData[] }>
    >(`/api/v1/datasets/${datasetId}/documents`, {
      method: 'POST',
      body: formData,
    });

    if (response.code !== 0) {
      throw new Error(`RAGFlow upload document error: ${response.message}`);
    }

    const doc = response.data?.documents?.[0];
    if (!doc) {
      throw new Error('RAGFlow upload document error: no document returned');
    }

    return {
      id: doc.id,
      name: doc.name,
      status: 'uploaded',
    };
  }

  /**
   * Start parsing documents in a dataset
   * @param datasetId - The dataset ID
   * @param documentIds - Array of document IDs to parse
   * @returns Parsing status
   */
  async startParsing(
    datasetId: string,
    documentIds: string[]
  ): Promise<{ status: string; message: string }> {
    if (!datasetId) {
      throw new Error('startParsing: datasetId is required');
    }
    if (!documentIds || documentIds.length === 0) {
      throw new Error('startParsing: documentIds is required');
    }

    const response = await this.request<RAGFlowApiResponse<unknown>>(
      `/api/v1/datasets/${datasetId}/chunks`,
      {
        method: 'POST',
        body: JSON.stringify({
          document_ids: documentIds,
        }),
      }
    );

    if (response.code !== 0) {
      throw new Error(`RAGFlow start parsing error: ${response.message}`);
    }

    return {
      status: 'started',
      message: response.message || 'Parsing started successfully',
    };
  }

  /**
   * Map RAGFlow API dataset to SDK Dataset interface
   */
  private mapDataset(data: RAGFlowDatasetData): Dataset {
    return {
      id: data.id,
      name: data.name,
      description: data.description,
      embeddingModel: data.embedding_model,
      documentCount: data.document_count,
      createdAt: data.create_time,
    };
  }
}

// ============================================================================
// RAGFlowTool - High-level tools for Agent frameworks
// ============================================================================

export class RAGFlowTool {
  private client: RAGFlowKBClient;

  /**
   * Create a new RAGFlowTool instance
   * @param client - An initialized RAGFlowKBClient
   */
  constructor(client: RAGFlowKBClient) {
    if (!client) {
      throw new Error('RAGFlowTool: client is required');
    }
    this.client = client;
  }

  /**
   * Search knowledge base and format results as text for agents
   * @param query - The search query
   * @param datasetName - Optional dataset name to search (searches all if not provided)
   * @returns Formatted search results as a string
   */
  async searchKnowledge(
    query: string,
    datasetName?: string
  ): Promise<string> {
    if (!query) {
      throw new Error('searchKnowledge: query is required');
    }

    let datasets: Dataset[];

    if (datasetName) {
      // Find the specific dataset
      const allDatasets = await this.client.listDatasets(1, 1000);
      datasets = allDatasets.filter(
        (d) => d.name.toLowerCase() === datasetName.toLowerCase()
      );
      if (datasets.length === 0) {
        throw new Error(`Dataset "${datasetName}" not found`);
      }
    } else {
      // Search all datasets
      datasets = await this.client.listDatasets(1, 1000);
    }

    if (datasets.length === 0) {
      return 'No datasets available to search.';
    }

    // Search each dataset and aggregate results
    const allResults: Array<{ dataset: string; results: RetrievalResult[] }> =
      [];

    for (const dataset of datasets) {
      try {
        const results = await this.client.retrieve(dataset.id, query, 5, 0.5);
        if (results.length > 0) {
          allResults.push({ dataset: dataset.name, results });
        }
      } catch (error) {
        // Skip datasets that fail to retrieve
        console.warn(
          `Warning: Failed to search dataset "${dataset.name}":`,
          error instanceof Error ? error.message : error
        );
      }
    }

    if (allResults.length === 0) {
      return `No relevant information found for query: "${query}"`;
    }

    // Format results as text
    let output = `Knowledge Base Search Results for: "${query}"\n`;
    output += '=' .repeat(60) + '\n\n';

    for (const { dataset, results } of allResults) {
      output += `[Dataset: ${dataset}]\n`;
      output += '-'.repeat(40) + '\n';

      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        output += `Result ${i + 1} (Score: ${(result.score * 100).toFixed(1)}%)\n`;
        output += `Source: ${result.documentName}\n`;
        output += `Content: ${result.content}\n`;
        output += '\n';
      }
    }

    return output;
  }

  /**
   * Add a document to a dataset and trigger parsing
   * @param file - The file to upload
   * @param datasetName - Name of the dataset to add to
   * @param metadata - Optional metadata
   * @returns Status message
   */
  async addDocument(
    file: Blob | File | Buffer,
    datasetName: string,
    metadata?: Record<string, unknown>
  ): Promise<string> {
    if (!file) {
      throw new Error('addDocument: file is required');
    }
    if (!datasetName) {
      throw new Error('addDocument: datasetName is required');
    }

    // Find or create the dataset
    const datasets = await this.client.listDatasets(1, 1000);
    let dataset = datasets.find(
      (d) => d.name.toLowerCase() === datasetName.toLowerCase()
    );

    if (!dataset) {
      dataset = await this.client.createDataset(datasetName);
    }

    // Upload the document
    const uploadedDoc = await this.client.uploadDocument(
      dataset.id,
      file,
      metadata
    );

    // Start parsing
    await this.client.startParsing(dataset.id, [uploadedDoc.id]);

    return `Document "${uploadedDoc.name}" uploaded to dataset "${datasetName}" and parsing started.`;
  }
}

// ============================================================================
// Default Export
// ============================================================================

export default {
  RAGFlowKBClient,
  RAGFlowTool,
};

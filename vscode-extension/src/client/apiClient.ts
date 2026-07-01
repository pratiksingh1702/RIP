export interface HealthStatus {
  status: string;
  neo4j: boolean;
  qdrant: boolean;
  mode?: string;
  capabilities?: string[];
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  async isHealthy(): Promise<boolean> {
    try {
      await this.getHealth();
      return true;
    } catch {
      return false;
    }
  }

  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>("/health");
  }

  async assertServerMode(): Promise<void> {
    const health = await this.getHealth();
    const capabilities = health.capabilities ?? [];
    if (!capabilities.includes("REST_API") || health.mode === "local") {
      throw new Error(
        "RIP HTTP features require server mode. Start Neo4j, Qdrant, and PostgreSQL with " +
          "`docker compose up -d`, then run `repo serve`. CLI features can still use local mode."
      );
    }
  }

  async traceSymbol(symbol: string): Promise<any> {
    return this.request(`/trace/${encodeURIComponent(symbol)}`);
  }

  async impactSymbol(symbol: string): Promise<any> {
    return this.request(`/impact/${encodeURIComponent(symbol)}`);
  }

  async explainSymbol(symbol: string): Promise<any> {
    return this.explain(symbol);
  }

  async explain(symbol: string, projectId: string = ""): Promise<any> {
    return this.request("/explain", {
      method: "POST",
      body: JSON.stringify({ symbol, context_level: "file", project_id: projectId }),
    });
  }

  async getArchitecture(): Promise<any> {
    return this.request("/architecture");
  }

  async getMetrics(): Promise<any> {
    return this.request("/metrics?top_risk=10");
  }

  async getIndexStatus(): Promise<any> {
    return this.request("/index/status");
  }

  async getRuntimeStatus(): Promise<any> {
    return this.request("/runtime/status");
  }

  async indexRepo(path: string): Promise<any> {
    return this.request("/index", {
      method: "POST",
      body: JSON.stringify({ repo_path: path }),
    });
  }

  async search(query: string, projectId: string = ""): Promise<any> {
    return this.request(
      `/search?q=${encodeURIComponent(query)}&top=12&project_id=${encodeURIComponent(projectId)}`
    );
  }
}

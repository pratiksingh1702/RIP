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
      await this.request("/health");
      return true;
    } catch {
      return false;
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

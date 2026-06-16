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

  async traceSymbol(symbol: string): Promise<any> {
    return this.request(`/trace/${encodeURIComponent(symbol)}`);
  }

  async impactSymbol(symbol: string): Promise<any> {
    return this.request(`/impact/${encodeURIComponent(symbol)}`);
  }

  async explainSymbol(symbol: string): Promise<any> {
    return this.request(`/explain/${encodeURIComponent(symbol)}`);
  }

  async getArchitecture(): Promise<any> {
    return this.request("/architecture");
  }

  async indexRepo(path: string): Promise<any> {
    return this.request("/index", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
  }

  async search(query: string): Promise<any> {
    return this.request("/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }
}

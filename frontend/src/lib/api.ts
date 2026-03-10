import { getTokens, setTokens, clearTokens } from "./auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

class ApiClient {
  private baseUrl: string;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const tokens = getTokens();
    if (tokens) {
      headers["Authorization"] = `Bearer ${tokens.access_token}`;
    }
    return headers;
  }

  private async refreshToken(): Promise<boolean> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
    this.refreshPromise = this._doRefresh().finally(() => {
      this.refreshPromise = null;
    });
    return this.refreshPromise;
  }

  private async _doRefresh(): Promise<boolean> {
    try {
      const tokens = getTokens();
      if (!tokens?.refresh_token) return false;

      const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      });

      if (!response.ok) {
        clearTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return false;
      }

      const data = await response.json();
      setTokens(data);
      return true;
    } catch {
      clearTokens();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      return false;
    }
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const response = await fetch(url, {
      method,
      headers: this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryResponse = await fetch(url, {
          method,
          headers: this.getHeaders(),
          body: body ? JSON.stringify(body) : undefined,
        });

        if (!retryResponse.ok) {
          throw new ApiError(retryResponse.status, await retryResponse.text());
        }
        return retryResponse.json();
      }
      throw new ApiError(401, "Unauthorized");
    }

    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PATCH", path, body);
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async postFormData<T>(path: string, formData: FormData): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {};
    const tokens = getTokens();
    if (tokens) {
      headers["Authorization"] = `Bearer ${tokens.access_token}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryHeaders: Record<string, string> = {};
        const retryTokens = getTokens();
        if (retryTokens) {
          retryHeaders["Authorization"] = `Bearer ${retryTokens.access_token}`;
        }
        const retryResponse = await fetch(url, {
          method: "POST",
          headers: retryHeaders,
          body: formData,
        });
        if (!retryResponse.ok) {
          throw new ApiError(retryResponse.status, await retryResponse.text());
        }
        return retryResponse.json();
      }
      throw new ApiError(401, "Unauthorized");
    }

    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  }
}

export const api = new ApiClient(BASE_URL);
export { ApiError };

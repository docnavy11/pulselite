import { getTokens, setTokens, clearTokens } from "./auth";
import { reconnectSocket } from "./socket";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

class ApiError extends Error {
  public detail: string;

  constructor(
    public status: number,
    message: string,
  ) {
    // Try to extract "detail" from JSON error responses for user-friendly messages
    let detail = message;
    try {
      const parsed = JSON.parse(message);
      if (parsed.detail) {
        detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      // Not JSON — use raw message
    }
    super(detail);
    this.detail = detail;
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
      reconnectSocket();
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

    let response: Response;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
      response = await fetch(url, {
        method,
        headers: this.getHeaders(),
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
    } catch (err) {
      // Network error — backend unreachable, CORS failure, DNS resolution failure, etc.
      const detail =
        `Cannot reach the backend at ${this.baseUrl}. ` +
        "Check that Docker containers are running (make up) and VITE_API_URL is correct in your .env file.";
      throw new ApiError(0, detail);
    }

    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryController = new AbortController();
        const retryTimeoutId = setTimeout(() => retryController.abort(), DEFAULT_TIMEOUT_MS);
        const retryResponse = await fetch(url, {
          method,
          headers: this.getHeaders(),
          body: body ? JSON.stringify(body) : undefined,
          signal: retryController.signal,
        });
        clearTimeout(retryTimeoutId);

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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS * 2); // 60s for file uploads
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        const retryHeaders: Record<string, string> = {};
        const retryTokens = getTokens();
        if (retryTokens) {
          retryHeaders["Authorization"] = `Bearer ${retryTokens.access_token}`;
        }
        const retryController = new AbortController();
        const retryTimeoutId = setTimeout(() => retryController.abort(), DEFAULT_TIMEOUT_MS * 2);
        const retryResponse = await fetch(url, {
          method: "POST",
          headers: retryHeaders,
          body: formData,
          signal: retryController.signal,
        });
        clearTimeout(retryTimeoutId);
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

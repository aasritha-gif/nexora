const getBaseUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) {
    return envUrl.endsWith("/api") ? envUrl : `${envUrl.replace(/\/$/, "")}/api`;
  }
  if (typeof window !== "undefined") {
    return "/api";
  }
  return "http://localhost:8000/api";
};

const API_BASE = getBaseUrl();

interface RequestOptions extends RequestInit {
  token?: string;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { token, headers = {}, ...rest } = options;

  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    ...(headers as Record<string, string>),
  };

  // Check stored auth token if client-side and not explicitly passed
  let activeToken = token;
  if (!activeToken && typeof window !== "undefined") {
    activeToken = localStorage.getItem("nexora_access_token") || undefined;
  }

  if (activeToken) {
    reqHeaders["Authorization"] = `Bearer ${activeToken}`;
  }

  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const res = await fetch(url, {
    ...rest,
    headers: reqHeaders,
  });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("nexora_access_token");
      localStorage.removeItem("nexora_user");
    }
    let errorMsg = `API request failed: ${res.status} ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson.error && errorJson.error.message) {
        errorMsg = errorJson.error.message;
      } else if (errorJson.detail) {
        errorMsg = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

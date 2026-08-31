export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError("无法连接服务器，请检查网络后重试", 0);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message = Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).join("；") : detail;
    throw new ApiError(message || "操作失败，请稍后重试", response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function photoUrl(path: string) { return path; }

export function upload<T>(path: string, body: FormData, onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", path);
    request.withCredentials = true;
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new ApiError("上传失败，请检查网络后重试", 0));
    request.onload = () => {
      const data = JSON.parse(request.responseText || "{}");
      if (request.status >= 200 && request.status < 300) resolve(data as T);
      else reject(new ApiError(data.detail || "上传失败，请重试", request.status));
    };
    request.send(body);
  });
}

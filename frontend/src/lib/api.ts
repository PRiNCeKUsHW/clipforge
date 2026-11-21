import { errorMessage } from "./errors";
import type {
  Clip,
  ClipDetail,
  ClipUpdate,
  PlatformId,
  PresignResponse,
  Project,
  PublishJob,
  SocialAccount,
  SourceType,
  User,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      // send/receive the httpOnly auth cookie
      credentials: "include",
      headers: {
        ...(init.body && !(init.body instanceof URLSearchParams) ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, `Can't reach the API at ${API_URL}. Is the backend running?`);
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(body));
  return body as T;
}

export const api = {
  me: () => request<User>("/api/users/me"),
  login: (email: string, password: string) =>
    request<void>("/api/auth/cookie/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  logout: () => request<void>("/api/auth/cookie/logout", { method: "POST" }),
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),

  listProjects: () => request<Project[]>("/api/projects"),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (body: {
    source_type: SourceType;
    source_url?: string;
    storage_key?: string;
    title?: string;
    instruction?: string;
    layout?: string;
    caption_style?: string;
    clip_length?: string;
    target_clips?: number | null;
  }) => request<Project>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  retryProject: (id: string) => request<Project>(`/api/projects/${id}/retry`, { method: "POST" }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  listClips: (projectId: string) => request<Clip[]>(`/api/projects/${projectId}/clips`),
  downloadClip: (clipId: string) => request<{ url: string; filename: string }>(`/api/clips/${clipId}/download`),
  /** Plain link: the browser downloads the streamed zip with the auth cookie. */
  zipUrl: (projectId: string) => `${API_URL}/api/projects/${projectId}/download.zip`,

  getClip: (clipId: string) => request<ClipDetail>(`/api/clips/${clipId}`),
  updateClip: (clipId: string, body: ClipUpdate) =>
    request<ClipDetail>(`/api/clips/${clipId}`, { method: "PATCH", body: JSON.stringify(body) }),
  renderClip: (clipId: string) => request<ClipDetail>(`/api/clips/${clipId}/render`, { method: "POST" }),
  publishClip: (
    clipId: string,
    body: { social_account_id: string; title: string; description: string; privacy_status: string },
  ) => request<PublishJob>(`/api/clips/${clipId}/publish`, { method: "POST", body: JSON.stringify(body) }),
  listPublishJobs: (clipId: string) => request<PublishJob[]>(`/api/clips/${clipId}/publish-jobs`),

  providers: () => request<Record<PlatformId, boolean>>("/api/oauth/providers"),
  listAccounts: () => request<SocialAccount[]>("/api/accounts"),
  disconnectAccount: (id: string) => request<void>(`/api/accounts/${id}`, { method: "DELETE" }),
  /** Plain link: starts the OAuth redirect dance (top-level navigation carries the auth cookie). */
  connectUrl: (platform: PlatformId) => `${API_URL}/api/oauth/${platform}/start`,

  presignUpload: (file: File) =>
    request<PresignResponse>("/api/uploads/presign", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, content_type: file.type || "video/mp4", size: file.size }),
    }),

  eventsUrl: (projectId: string) => `${API_URL}/api/projects/${projectId}/events`,
};

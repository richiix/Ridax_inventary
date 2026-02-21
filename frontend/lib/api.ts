"use client";

import { resolveApiBaseUrl } from "@/lib/config";
import { getToken } from "@/lib/session";

const RETRYABLE_STATUS = new Set([502, 503, 504, 522, 524]);

type RetryOptions = {
  attempts?: number;
  baseDelayMs?: number;
  timeoutMs?: number;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(
  input: RequestInfo | URL,
  init: RequestInit,
  retry: RetryOptions = {},
): Promise<Response> {
  const attempts = retry.attempts ?? 4;
  const baseDelayMs = retry.baseDelayMs ?? 250;
  const timeoutMs = retry.timeoutMs ?? 10000;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(input, {
        ...init,
        signal: controller.signal,
      });
      if (!RETRYABLE_STATUS.has(response.status) || attempt === attempts) {
        return response;
      }
    } catch (error) {
      if (attempt === attempts) {
        throw new Error("No se pudo conectar con el servidor. Intenta nuevamente en unos segundos.");
      }
    } finally {
      clearTimeout(timeoutId);
    }
    const waitMs = Math.min(baseDelayMs * attempt, 3000);
    await sleep(waitMs);
  }

  throw new Error("No se pudo completar la solicitud");
}

function buildApiUrl(path: string): string {
  return `${resolveApiBaseUrl()}${path}`;
}

async function parseResponse(response: Response): Promise<any> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload.detail || "Error inesperado";
    throw new Error(message);
  }
  return response.json();
}

function buildHeaders(token?: string, contentType = "application/json"): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": contentType,
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function apiGet(path: string): Promise<any> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function apiPost(path: string, body: unknown): Promise<any> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiPostPublicForm(path: string, body: Record<string, string>, retry?: RetryOptions): Promise<any> {
  const formData = new URLSearchParams();
  for (const [key, value] of Object.entries(body)) {
    formData.set(key, value);
  }

  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "POST",
    body: formData.toString(),
    headers: {
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    },
  }, retry);

  return parseResponse(response);
}

export async function apiPut(path: string, body: unknown): Promise<any> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "PUT",
    headers: buildHeaders(token),
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiPatch(path: string, body: unknown = {}): Promise<any> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "PATCH",
    headers: buildHeaders(token),
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiDelete(path: string): Promise<any> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "DELETE",
    headers: buildHeaders(token),
  });
  return parseResponse(response);
}

export async function apiDownload(path: string): Promise<Blob> {
  const token = getToken();
  const response = await fetchWithRetry(buildApiUrl(path), {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "No se pudo descargar archivo");
  }
  return response.blob();
}

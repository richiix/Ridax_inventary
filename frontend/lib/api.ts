"use client";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

async function parseResponse(response: Response): Promise<any> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload.detail || "Error inesperado";
    throw new Error(message);
  }
  return response.json();
}

export async function apiGet(path: string): Promise<any> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function apiPost(path: string, body: unknown): Promise<any> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiPut(path: string, body: unknown): Promise<any> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiPatch(path: string, body: unknown = {}): Promise<any> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

export async function apiDelete(path: string): Promise<any> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  return parseResponse(response);
}

export async function apiDownload(path: string): Promise<Blob> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "No se pudo descargar archivo");
  }
  return response.blob();
}

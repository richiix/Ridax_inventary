const envApiBase = process.env.NEXT_PUBLIC_API_URL;

export function resolveApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "app.repuestosm13.com" || host.endsWith(".ridax-inventary.pages.dev")) {
      return "/api";
    }
  }

  return envApiBase ?? "http://localhost:8000/api/v1";
}

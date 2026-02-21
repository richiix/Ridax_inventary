const RETRYABLE_STATUS = new Set([502, 503, 504, 522, 524]);
const ORIGIN_API_BASE = "https://api.repuestosm13.com/api/v1";
const FETCH_TIMEOUT_MS = 10000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildCorsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "authorization,content-type",
    "Access-Control-Max-Age": "600",
    Vary: "Origin",
  };
}

export async function onRequest(context) {
  const { request, params } = context;
  const requestUrl = new URL(request.url);
  const pathParam = params.path;
  const path = Array.isArray(pathParam) ? pathParam.join("/") : pathParam || "";

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: buildCorsHeaders(request.headers.get("Origin")),
    });
  }

  const targetUrl = new URL(`${ORIGIN_API_BASE}/${path}`);
  targetUrl.search = requestUrl.search;

  const headers = new Headers(request.headers);
  headers.delete("host");

  const bodyBuffer = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const attempts = 6;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers,
        body: bodyBuffer,
        redirect: "follow",
        signal: controller.signal,
      });

      if (!RETRYABLE_STATUS.has(response.status) || attempt === attempts) {
        const outHeaders = new Headers(response.headers);
        const cors = buildCorsHeaders(request.headers.get("Origin"));
        Object.entries(cors).forEach(([key, value]) => outHeaders.set(key, value));
        return new Response(response.body, {
          status: response.status,
          headers: outHeaders,
        });
      }
    } catch (error) {
      if (attempt === attempts) {
        break;
      }
    } finally {
      clearTimeout(timeoutId);
    }

    await sleep(Math.min(500 * attempt, 2500));
  }

  return new Response(
    JSON.stringify({ detail: "Gateway temporalmente inestable" }),
    {
      status: 503,
      headers: {
        "Content-Type": "application/json",
        ...buildCorsHeaders(request.headers.get("Origin")),
      },
    },
  );
}

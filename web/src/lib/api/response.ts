/**
 * response.ts — Helpers for building JSON responses with CORS + rate-limit headers.
 */

import type { RateLimitResult } from "./rate-limit";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

/** Build common headers including CORS and rate-limit info. */
function buildHeaders(rl: RateLimitResult): HeadersInit {
  return {
    ...CORS_HEADERS,
    "Content-Type": "application/json",
    "Cache-Control": "no-store, must-revalidate",
    "X-RateLimit-Limit": String(100),
    "X-RateLimit-Remaining": String(rl.remaining),
    "X-RateLimit-Reset": String(Math.floor(rl.reset.getTime() / 1000)),
  };
}

/** Successful JSON response with CORS + rate-limit headers. */
export function ok(data: unknown, rl: RateLimitResult, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: buildHeaders(rl),
  });
}

/** 429 Too Many Requests response. */
export function rateLimitExceeded(rl: RateLimitResult): Response {
  return new Response(
    JSON.stringify({
      error: "rate_limit_exceeded",
      retry_after_seconds: rl.retryAfterSeconds,
    }),
    {
      status: 429,
      headers: {
        ...CORS_HEADERS,
        "Content-Type": "application/json",
        "X-RateLimit-Limit": String(100),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": String(Math.floor(rl.reset.getTime() / 1000)),
        "Retry-After": String(rl.retryAfterSeconds),
      },
    }
  );
}

/** 404 Not Found response. */
export function notFound(message = "Not found"): Response {
  return new Response(JSON.stringify({ error: message }), {
    status: 404,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

/** 400 Bad Request response. */
export function badRequest(message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status: 400,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

/** 500 Internal Server Error response. */
export function serverError(message = "Internal server error"): Response {
  return new Response(JSON.stringify({ error: message }), {
    status: 500,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

/** 503 Service Unavailable (e.g., DB unreachable). */
export function serviceUnavailable(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 503,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

/** Handle OPTIONS preflight requests. */
export function optionsResponse(): Response {
  return new Response(null, {
    status: 204,
    headers: CORS_HEADERS,
  });
}

/**
 * rate-limit.ts — In-memory sliding-window rate limiter.
 *
 * 100 requests per day per IP (default). Timestamps are stored in a Map<ip, number[]>.
 * A hourly purge removes stale entries to keep memory bounded.
 */

const WINDOW_MS = 24 * 60 * 60 * 1000; // 24 hours
const MAX_REQUESTS = 100;

// Map<ip, sorted array of request timestamps (ms)>
const store = new Map<string, number[]>();

// Purge entries older than WINDOW_MS every hour
setInterval(() => {
  const cutoff = Date.now() - WINDOW_MS;
  for (const [ip, timestamps] of store.entries()) {
    const fresh = timestamps.filter((t) => t > cutoff);
    if (fresh.length === 0) {
      store.delete(ip);
    } else {
      store.set(ip, fresh);
    }
  }
}, 60 * 60 * 1000);

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  reset: Date;
  retryAfterSeconds: number;
}

export function checkRateLimit(ip: string): RateLimitResult {
  const now = Date.now();
  const cutoff = now - WINDOW_MS;

  // Normalize IP (strip IPv6 prefix if needed)
  const normalizedIp = ip.replace(/^::ffff:/, "");

  const timestamps = (store.get(normalizedIp) || []).filter((t) => t > cutoff);

  const oldestInWindow = timestamps[0] ?? now;
  const reset = new Date(oldestInWindow + WINDOW_MS);

  if (timestamps.length >= MAX_REQUESTS) {
    const retryAfterSeconds = Math.ceil((reset.getTime() - now) / 1000);
    return {
      allowed: false,
      remaining: 0,
      reset,
      retryAfterSeconds,
    };
  }

  timestamps.push(now);
  store.set(normalizedIp, timestamps);

  return {
    allowed: true,
    remaining: MAX_REQUESTS - timestamps.length,
    reset,
    retryAfterSeconds: 0,
  };
}

/** Extracts client IP from Next.js request headers. Falls back to "unknown". */
export function getClientIp(request: Request): string {
  const headers = request.headers;
  return (
    headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    headers.get("x-real-ip") ||
    "unknown"
  );
}

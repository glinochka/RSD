type Bucket = { hits: number[] };

const buckets = new Map<string, Bucket>();

export function checkRateLimit(params: {
  key: string;
  maxRequests: number;
  windowSeconds: number;
}): { allowed: boolean; retryAfterSeconds: number } {
  const { key, maxRequests, windowSeconds } = params;
  const now = Date.now();
  const windowMs = windowSeconds * 1000;
  const windowStart = now - windowMs;

  let bucket = buckets.get(key);
  if (!bucket) {
    bucket = { hits: [] };
    buckets.set(key, bucket);
  }

  bucket.hits = bucket.hits.filter((ts) => ts > windowStart);

  if (bucket.hits.length >= maxRequests) {
    const oldest = bucket.hits[0] ?? now;
    const retryAfterSeconds = Math.max(1, Math.ceil((oldest + windowMs - now) / 1000));
    return { allowed: false, retryAfterSeconds };
  }

  bucket.hits.push(now);
  return { allowed: true, retryAfterSeconds: 0 };
}

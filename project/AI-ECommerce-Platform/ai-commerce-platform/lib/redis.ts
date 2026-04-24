import Redis from 'ioredis';

// Redis client for caching and session management
// Used for: product caching, session storage, rate limiting, recommendation cache

const getRedisUrl = () => {
  // Support both redis:// and rediss:// for TLS connections
  return process.env.REDIS_URL || 'redis://localhost:6379';
};

declare global {
  // eslint-disable-next-line no-var
  var redis: Redis | undefined;
}

// Create Redis client instance
function createRedisClient() {
  const client = new Redis(getRedisUrl(), {
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000);
      return delay;
    },
    lazyConnect: true,
  });

  client.on('error', (err) => {
    console.error('Redis connection error:', err.message);
  });

  client.on('connect', () => {
    console.log('Redis connected successfully');
  });

  return client;
}

// Use singleton pattern for development hot reloading
export const redis = globalThis.redis ?? createRedisClient();

if (process.env.NODE_ENV !== 'production') {
  globalThis.redis = redis;
}

// Cache utilities
export const cacheKeys = {
  product: (id: string) => `product:${id}`,
  products: (page: number, limit: number) => `products:${page}:${limit}`,
  category: (id: string) => `category:${id}`,
  categoryProducts: (id: string, page: number) => `category:${id}:products:${page}`,
  recommendation: (userId: string, type: string) => `recommendation:${userId}:${type}`,
  trending: () => 'trending:products',
  search: (query: string) => `search:${query}`,
};

export const cacheTTL = {
  short: 60 * 5,        // 5 minutes
  medium: 60 * 30,      // 30 minutes
  long: 60 * 60 * 24,   // 24 hours
  week: 60 * 60 * 24 * 7, // 1 week
};

export default redis;

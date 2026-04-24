import Redis from 'ioredis';

// Redis client singleton
const globalForRedis = globalThis as unknown as {
  redis: Redis | undefined;
};

/**
 * Redis client for caching and session management
 */
export const redis =
  globalForRedis.redis ??
  new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
    maxRetriesPerRequest: 3,
    lazyConnect: true,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000);
      return delay;
    },
  });

if (process.env.NODE_ENV !== 'production') globalForRedis.redis = redis;

/**
 * Cache utility functions
 */
export const cache = {
  /**
   * Get cached data
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      const data = await redis.get(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Cache get error:', error);
      return null;
    }
  },

  /**
   * Set cached data with expiration
   */
  async set(key: string, data: unknown, ttlSeconds: number = 3600): Promise<boolean> {
    try {
      await redis.set(key, JSON.stringify(data), 'EX', ttlSeconds);
      return true;
    } catch (error) {
      console.error('Cache set error:', error);
      return false;
    }
  },

  /**
   * Delete cached data
   */
  async del(key: string): Promise<boolean> {
    try {
      await redis.del(key);
      return true;
    } catch (error) {
      console.error('Cache delete error:', error);
      return false;
    }
  },

  /**
   * Delete cached data by pattern
   */
  async delByPattern(pattern: string): Promise<number> {
    try {
      const keys = await redis.keys(pattern);
      if (keys.length > 0) {
        return await redis.del(...keys);
      }
      return 0;
    } catch (error) {
      console.error('Cache delete by pattern error:', error);
      return 0;
    }
  },
};

export default redis;

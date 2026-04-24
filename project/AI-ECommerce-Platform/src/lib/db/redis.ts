/**
 * Redis Client for Caching and Session Management
 * 
 * This module provides a Redis client for:
 * - Session storage
 * - API response caching
 * - Rate limiting
 * - Real-time features
 */

import Redis from 'ioredis'

// Define global type for redis client
declare global {
  // eslint-disable-next-line no-var
  var redis: Redis | undefined
}

/**
 * Creates a new Redis client instance
 */
function createRedisClient(): Redis {
  const client = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000)
      return delay
    },
    lazyConnect: true,
  })

  client.on('error', (err) => {
    console.error('Redis connection error:', err)
  })

  client.on('connect', () => {
    console.log('Redis connected successfully')
  })

  return client
}

// Export a singleton instance
export const redis = globalThis.redis ?? createRedisClient()

// In development, cache the client to prevent reconnecting
if (process.env.NODE_ENV !== 'production') {
  globalThis.redis = redis
}

/**
 * Cache utility functions
 */
export const cache = {
  /**
   * Get a value from cache
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      const value = await redis.get(key)
      if (!value) return null
      return JSON.parse(value) as T
    } catch (error) {
      console.error('Cache get error:', error)
      return null
    }
  },

  /**
   * Set a value in cache with optional TTL
   */
  async set(key: string, value: unknown, ttlSeconds?: number): Promise<boolean> {
    try {
      const serialized = JSON.stringify(value)
      if (ttlSeconds) {
        await redis.setex(key, ttlSeconds, serialized)
      } else {
        await redis.set(key, serialized)
      }
      return true
    } catch (error) {
      console.error('Cache set error:', error)
      return false
    }
  },

  /**
   * Delete a value from cache
   */
  async del(key: string): Promise<boolean> {
    try {
      await redis.del(key)
      return true
    } catch (error) {
      console.error('Cache delete error:', error)
      return false
    }
  },

  /**
   * Check if a key exists
   */
  async exists(key: string): Promise<boolean> {
    try {
      const result = await redis.exists(key)
      return result === 1
    } catch (error) {
      console.error('Cache exists error:', error)
      return false
    }
  },

  /**
   * Increment a counter (useful for rate limiting)
   */
  async incr(key: string, ttlSeconds?: number): Promise<number> {
    try {
      const result = await redis.incr(key)
      if (ttlSeconds && result === 1) {
        await redis.expire(key, ttlSeconds)
      }
      return result
    } catch (error) {
      console.error('Cache incr error:', error)
      return 0
    }
  },
}

/**
 * Rate limiter utility
 */
export const rateLimit = {
  /**
   * Check if request is within rate limit
   * @param identifier - Unique identifier (IP, user ID, etc.)
   * @param limit - Max requests allowed
   * @param windowSeconds - Time window in seconds
   */
  async check(identifier: string, limit: number, windowSeconds: number): Promise<{
    success: boolean
    remaining: number
    reset: number
  }> {
    const key = `ratelimit:${identifier}`
    const current = await redis.incr(key)
    
    if (current === 1) {
      await redis.expire(key, windowSeconds)
    }

    const ttl = await redis.ttl(key)
    const reset = Math.floor(Date.now() / 1000) + (ttl > 0 ? ttl : windowSeconds)
    const remaining = Math.max(0, limit - current)

    return {
      success: current <= limit,
      remaining,
      reset,
    }
  },
}

export default redis

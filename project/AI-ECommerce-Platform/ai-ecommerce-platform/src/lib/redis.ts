/**
 * Redis 缓存客户端
 * 用于会话存储、缓存、实时数据等
 */

import Redis from 'ioredis';

const globalForRedis = globalThis as unknown as {
  redis: Redis | undefined;
};

// 创建 Redis 客户端实例
export const redis =
  globalForRedis.redis ??
  new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000);
      return delay;
    },
    lazyConnect: true,
  });

// 在开发环境中将实例挂载到全局
if (process.env.NODE_ENV !== 'production') {
  globalForRedis.redis = redis;
}

/**
 * 缓存工具函数
 */
export const cache = {
  /**
   * 设置缓存
   */
  async set(key: string, value: string, ttlSeconds?: number): Promise<void> {
    if (ttlSeconds) {
      await redis.setex(key, ttlSeconds, value);
    } else {
      await redis.set(key, value);
    }
  },

  /**
   * 获取缓存
   */
  async get(key: string): Promise<string | null> {
    return redis.get(key);
  },

  /**
   * 删除缓存
   */
  async del(key: string): Promise<void> {
    await redis.del(key);
  },

  /**
   * 检查键是否存在
   */
  async exists(key: string): Promise<boolean> {
    const result = await redis.exists(key);
    return result === 1;
  },

  /**
   * 设置缓存并返回旧值
   */
  async getset(key: string, value: string): Promise<string | null> {
    return redis.getset(key, value);
  },

  /**
   * 批量删除缓存
   */
  async delMany(keys: string[]): Promise<void> {
    if (keys.length > 0) {
      await redis.del(...keys);
    }
  },

  /**
   * 自增计数器
   */
  async incr(key: string): Promise<number> {
    return redis.incr(key);
  },

  /**
   * 设置带过期时间的键（TTL）
   */
  async expire(key: string, ttlSeconds: number): Promise<void> {
    await redis.expire(key, ttlSeconds);
  },

  /**
   * 获取键的剩余过期时间
   */
  async ttl(key: string): Promise<number> {
    return redis.ttl(key);
  },

  /**
   * 发布消息到频道
   */
  async publish(channel: string, message: string): Promise<number> {
    return redis.publish(channel, message);
  },

  /**
   * 订阅消息（返回订阅迭代器）
   */
  subscribe(channel: string): Redis.RedisSubscription {
    const subscriber = redis.duplicate();
    subscriber.subscribe(channel);
    return subscriber;
  },
};

export default redis;

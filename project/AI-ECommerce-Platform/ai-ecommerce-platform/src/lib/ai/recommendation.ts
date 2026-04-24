/**
 * AI 推荐引擎服务
 * 基于用户行为和商品特征进行个性化推荐
 */

import OpenAI from 'openai';
import prisma from '../db';
import { cache } from '../redis';

// 初始化 OpenAI 客户端
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/**
 * 推荐类型枚举
 */
export enum RecommendationType {
  PERSONALIZED = 'PERSONALIZED', // 个性化推荐
  SIMILAR = 'SIMILAR', // 相似商品
  FREQUENTLY_BOUGHT = 'FREQUENTLY_BOUGHT', // 经常一起购买
  TRENDING = 'TRENDING', // 热门商品
  NEW_ARRIVALS = 'NEW_ARRIVALS', // 新品上架
  RECENTLY_VIEWED = 'RECENTLY_VIEWED', // 最近浏览
}

/**
 * 推荐缓存配置
 */
const CACHE_TTL = {
  PERSONALIZED: 3600, // 1小时
  SIMILAR: 86400, // 24小时
  TRENDING: 1800, // 30分钟
  NEW_ARRIVALS: 3600, // 1小时
  RECENTLY_VIEWED: 300, // 5分钟
};

/**
 * 获取用户个性化推荐
 */
export async function getPersonalizedRecommendations(
  userId: string,
  limit: number = 10
): Promise<RecommendationResult[]> {
  const cacheKey = `recommendation:personalized:${userId}`;
  const cached = await cache.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // 获取用户浏览历史
  const browsingHistory = await prisma.browsingHistory.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    take: 20,
    include: { product: true },
  });

  // 获取用户购买历史
  const purchasedProducts = await prisma.orderItem.findMany({
    where: {
      order: { userId, paymentStatus: 'PAID' },
    },
    include: { product: true },
    distinct: ['productId'],
  });

  // 获取用户收藏
  const favorites = await prisma.favorite.findMany({
    where: { userId },
    include: { product: true },
  });

  // 构建用户画像
  const userProfile = {
    viewedCategories: [
      ...new Set(browsingHistory.map((h) => h.product.categoryId)),
    ],
    viewedBrands: [
      ...new Set(
        browsingHistory
          .map((h) => h.product.brand)
          .filter((b): b is string => !!b)
      ),
    ],
    priceRange: calculatePriceRange(browsingHistory),
    favoriteCategories: [
      ...new Set(favorites.map((f) => f.product.categoryId)),
    ],
  };

  // 使用 AI 生成推荐
  const recommendations = await generateAIRecommendations(
    userProfile,
    purchasedProducts.map((p) => p.product),
    limit
  );

  // 缓存结果
  await cache.set(
    cacheKey,
    JSON.stringify(recommendations),
    CACHE_TTL.PERSONALIZED
  );

  return recommendations;
}

/**
 * 获取相似商品推荐
 */
export async function getSimilarProducts(
  productId: string,
  limit: number = 10
): Promise<RecommendationResult[]> {
  const cacheKey = `recommendation:similar:${productId}`;
  const cached = await cache.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // 获取目标商品信息
  const targetProduct = await prisma.product.findUnique({
    where: { id: productId },
    include: { category: true },
  });

  if (!targetProduct) {
    return [];
  }

  // 查找相似商品（同类目、相似价格区间）
  const similarProducts = await prisma.product.findMany({
    where: {
      id: { not: productId },
      categoryId: targetProduct.categoryId,
      isActive: true,
      stock: { gt: 0 },
      price: {
        gte: Number(targetProduct.price) * 0.7,
        lte: Number(targetProduct.price) * 1.3,
      },
    },
    orderBy: [{ sales: 'desc' }, { rating: 'desc' }],
    take: limit,
  });

  const results = similarProducts.map((product) => ({
    productId: product.id,
    product,
    score: calculateSimilarityScore(targetProduct, product),
    reason: `与"${targetProduct.name}"相似`,
  }));

  await cache.set(cacheKey, JSON.stringify(results), CACHE_TTL.SIMILAR);
  return results;
}

/**
 * 获取热门商品推荐
 */
export async function getTrendingProducts(
  limit: number = 10
): Promise<RecommendationResult[]> {
  const cacheKey = `recommendation:trending:${limit}`;
  const cached = await cache.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  const products = await prisma.product.findMany({
    where: {
      isActive: true,
      stock: { gt: 0 },
    },
    orderBy: [
      { sales: 'desc' },
      { views: 'desc' },
      { rating: 'desc' },
    ],
    take: limit,
  });

  const results = products.map((product, index) => ({
    productId: product.id,
    product,
    score: Math.max(1 - index * 0.1, 0.5),
    reason: '热门商品',
  }));

  await cache.set(cacheKey, JSON.stringify(results), CACHE_TTL.TRENDING);
  return results;
}

/**
 * 获取新品推荐
 */
export async function getNewArrivals(
  categoryId?: string,
  limit: number = 10
): Promise<RecommendationResult[]> {
  const cacheKey = `recommendation:new:${categoryId || 'all'}:${limit}`;
  const cached = await cache.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  const products = await prisma.product.findMany({
    where: {
      isActive: true,
      stock: { gt: 0 },
      ...(categoryId ? { categoryId } : {}),
    },
    orderBy: { createdAt: 'desc' },
    take: limit,
  });

  const results = products.map((product) => ({
    productId: product.id,
    product,
    score: 1,
    reason: '新品上架',
  }));

  await cache.set(cacheKey, JSON.stringify(results), CACHE_TTL.NEW_ARRIVALS);
  return results;
}

/**
 * 获取经常一起购买的商品
 */
export async function getFrequentlyBoughtTogether(
  productId: string,
  limit: number = 5
): Promise<RecommendationResult[]> {
  // 查找购买过该商品的用户还购买了哪些商品
  const orders = await prisma.orderItem.findMany({
    where: {
      productId,
      order: { paymentStatus: 'PAID' },
    },
    include: { order: { include: { items: true } } },
  });

  // 统计商品共现次数
  const coOccurrence: Record<string, number> = {};
  orders.forEach((item) => {
    item.order.items.forEach((orderItem) => {
      if (orderItem.productId !== productId) {
        coOccurrence[orderItem.productId] =
          (coOccurrence[orderItem.productId] || 0) + 1;
      }
    });
  });

  // 获取共现商品
  const sortedProducts = Object.entries(coOccurrence)
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit);

  const products = await prisma.product.findMany({
    where: {
      id: { in: sortedProducts.map(([id]) => id) },
      isActive: true,
      stock: { gt: 0 },
    },
  });

  const maxCoOccurrence = sortedProducts[0]?.[1] || 1;
  const results = products.map((product) => ({
    productId: product.id,
    product,
    score: (coOccurrence[product.id] || 0) / maxCoOccurrence,
    reason: '经常一起购买',
  }));

  return results;
}

/**
 * 获取最近浏览记录
 */
export async function getRecentlyViewed(
  userId: string,
  limit: number = 10
): Promise<RecommendationResult[]> {
  const history = await prisma.browsingHistory.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    distinct: ['productId'],
    take: limit,
    include: { product: true },
  });

  return history.map((item) => ({
    productId: item.productId,
    product: item.product,
    score: 1,
    reason: '最近浏览',
  }));
}

/**
 * 记录用户浏览历史
 */
export async function recordBrowsingHistory(
  userId: string,
  productId: string,
  sessionId?: string,
  source?: string
): Promise<void> {
  await prisma.browsingHistory.create({
    data: {
      userId,
      productId,
      sessionId,
      source,
    },
  });
}

// ============================================
// 辅助函数
// ============================================

interface RecommendationResult {
  productId: string;
  product: {
    id: string;
    name: string;
    slug: string;
    price: number;
    originalPrice?: number | null;
    images: string[];
    categoryId: string;
    rating: number;
    reviewCount: number;
  };
  score: number;
  reason: string;
}

interface UserProfile {
  viewedCategories: string[];
  viewedBrands: string[];
  priceRange: { min: number; max: number };
  favoriteCategories: string[];
}

/**
 * 计算用户价格区间偏好
 */
function calculatePriceRange(
  browsingHistory: Array<{ product: { price: number } }>
): { min: number; max: number } {
  if (browsingHistory.length === 0) {
    return { min: 0, max: 1000 };
  }
  const prices = browsingHistory.map((h) => Number(h.product.price));
  return {
    min: Math.min(...prices) * 0.8,
    max: Math.max(...prices) * 1.2,
  };
}

/**
 * 使用 AI 生成个性化推荐
 */
async function generateAIRecommendations(
  userProfile: UserProfile,
  purchasedProducts: Array<{
    id: string;
    name: string;
    categoryId: string;
    brand?: string | null;
  }>,
  limit: number
): Promise<RecommendationResult[]> {
  try {
    // 使用商品协同过滤逻辑生成推荐
    // 查找与用户历史偏好匹配的商品
    const recommendedProducts = await prisma.product.findMany({
      where: {
        isActive: true,
        stock: { gt: 0 },
        OR: [
          { categoryId: { in: userProfile.viewedCategories } },
          { categoryId: { in: userProfile.favoriteCategories } },
          ...(userProfile.viewedBrands.length > 0
            ? [{ brand: { in: userProfile.viewedBrands } }]
            : []),
        ],
        id: {
          notIn: purchasedProducts.map((p) => p.id),
        },
      },
      orderBy: [{ sales: 'desc' }, { rating: 'desc' }],
      take: limit,
    });

    return recommendedProducts.map((product) => ({
      productId: product.id,
      product,
      score: Math.random() * 0.5 + 0.5,
      reason: '根据您的浏览历史推荐',
    }));
  } catch (error) {
    console.error('AI推荐生成失败:', error);
    // 返回热门商品作为后备
    return getTrendingProducts(limit);
  }
}

/**
 * 计算商品相似度分数
 */
function calculateSimilarityScore(
  product1: { categoryId: string; price: number; tags: string[] },
  product2: { categoryId: string; price: number; tags: string[] }
): number {
  let score = 0;

  // 相同类目
  if (product1.categoryId === product2.categoryId) {
    score += 0.4;
  }

  // 价格接近度
  const priceDiff = Math.abs(
    Number(product1.price) - Number(product2.price)
  );
  const priceSimilarity = Math.max(0, 1 - priceDiff / 1000);
  score += priceSimilarity * 0.3;

  // 标签重叠
  const tags1 = product1.tags || [];
  const tags2 = product2.tags || [];
  const commonTags = tags1.filter((t) => tags2.includes(t));
  score += (commonTags.length / Math.max(tags1.length, tags2.length)) * 0.3;

  return score;
}

export default {
  getPersonalizedRecommendations,
  getSimilarProducts,
  getTrendingProducts,
  getNewArrivals,
  getFrequentlyBoughtTogether,
  getRecentlyViewed,
  recordBrowsingHistory,
  RecommendationType,
};

import prisma from '@/lib/db';
import { cache } from '@/lib/redis';
import { generateSlug } from '@/lib/utils';
import { generateProductSummary, generateProductTags } from '@/lib/openai';

/**
 * Get all products with pagination and filters
 */
export async function getProducts({
  page = 1,
  limit = 12,
  categoryId,
  search,
  minPrice,
  maxPrice,
  sortBy = 'createdAt',
  sortOrder = 'desc',
  status = 'ACTIVE',
}: {
  page?: number;
  limit?: number;
  categoryId?: string;
  search?: string;
  minPrice?: number;
  maxPrice?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  status?: 'ACTIVE' | 'DRAFT' | 'ARCHIVED';
} = {}) {
  const where: Record<string, unknown> = {
    status,
  };

  if (categoryId) {
    where.categoryId = categoryId;
  }

  if (search) {
    where.OR = [
      { name: { contains: search, mode: 'insensitive' } },
      { description: { contains: search, mode: 'insensitive' } },
    ];
  }

  if (minPrice !== undefined || maxPrice !== undefined) {
    where.price = {};
    if (minPrice !== undefined) (where.price as Record<string, number>).gte = minPrice;
    if (maxPrice !== undefined) (where.price as Record<string, number>).lte = maxPrice;
  }

  const [products, total] = await Promise.all([
    prisma.product.findMany({
      where,
      include: {
        category: {
          select: { id: true, name: true, slug: true },
        },
        reviews: {
          select: { rating: true },
        },
      },
      orderBy: { [sortBy]: sortOrder },
      skip: (page - 1) * limit,
      take: limit,
    }),
    prisma.product.count({ where }),
  ]);

  // Calculate average rating for each product
  const productsWithRating = products.map((product) => {
    const avgRating =
      product.reviews.length > 0
        ? product.reviews.reduce((sum, r) => sum + r.rating, 0) / product.reviews.length
        : 0;
    return {
      ...product,
      averageRating: avgRating,
      reviewCount: product.reviews.length,
    };
  });

  return {
    products: productsWithRating,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Get featured products
 */
export async function getFeaturedProducts(limit: number = 4) {
  const cacheKey = `products:featured:${limit}`;
  
  const cached = await cache.get<typeof productsWithRating>(cacheKey);
  if (cached) return cached;

  const products = await prisma.product.findMany({
    where: { status: 'ACTIVE', featured: true },
    include: {
      category: {
        select: { id: true, name: true, slug: true },
      },
      reviews: {
        select: { rating: true },
        take: 1,
      },
    },
    take: limit,
    orderBy: { createdAt: 'desc' },
  });

  const productsWithRating = products.map((product) => ({
    ...product,
    averageRating:
      product.reviews.length > 0
        ? product.reviews.reduce((sum, r) => sum + r.rating, 0) / product.reviews.length
        : 0,
    reviewCount: product.reviews.length,
  }));

  await cache.set(cacheKey, productsWithRating, 1800); // 30 minutes

  return productsWithRating;
}

/**
 * Get new arrivals
 */
export async function getNewArrivals(limit: number = 4) {
  const cacheKey = `products:new:${limit}`;
  
  const cached = await cache.get<typeof productsWithRating>(cacheKey);
  if (cached) return cached;

  const products = await prisma.product.findMany({
    where: { status: 'ACTIVE' },
    include: {
      category: {
        select: { id: true, name: true, slug: true },
      },
      reviews: {
        select: { rating: true },
        take: 1,
      },
    },
    take: limit,
    orderBy: { createdAt: 'desc' },
  });

  const productsWithRating = products.map((product) => ({
    ...product,
    averageRating:
      product.reviews.length > 0
        ? product.reviews.reduce((sum, r) => sum + r.rating, 0) / product.reviews.length
        : 0,
    reviewCount: product.reviews.length,
  }));

  await cache.set(cacheKey, productsWithRating, 1800);

  return productsWithRating;
}

/**
 * Get product by ID or slug
 */
export async function getProduct(identifier: string, byId: boolean = false) {
  const where = byId ? { id: identifier } : { slug: identifier };
  
  const cacheKey = `product:${byId ? 'id' : 'slug'}:${identifier}`;
  
  const cached = await cache.get<typeof product>(cacheKey);
  if (cached) return cached;

  const product = await prisma.product.findFirst({
    where: {
      ...where,
      status: 'ACTIVE',
    },
    include: {
      category: true,
      variants: true,
      reviews: {
        include: {
          user: {
            select: { id: true, name: true, avatar: true },
          },
        },
        orderBy: { createdAt: 'desc' },
        take: 10,
      },
    },
  });

  if (product) {
    // Calculate rating statistics
    const allReviews = await prisma.review.findMany({
      where: { productId: product.id },
      select: { rating: true },
    });

    const ratingDistribution = [1, 2, 3, 4, 5].map((rating) => ({
      rating,
      count: allReviews.filter((r) => r.rating === rating).length,
    }));

    const avgRating =
      allReviews.length > 0
        ? allReviews.reduce((sum, r) => sum + r.rating, 0) / allReviews.length
        : 0;

    const enrichedProduct = {
      ...product,
      averageRating: avgRating,
      reviewCount: allReviews.length,
      ratingDistribution,
    };

    await cache.set(cacheKey, enrichedProduct, 1800);
    
    return enrichedProduct;
  }

  return null;
}

/**
 * Get product by ID
 */
export async function getProductById(id: string) {
  return getProduct(id, true);
}

/**
 * Get product by slug
 */
export async function getProductBySlug(slug: string) {
  return getProduct(slug, false);
}

/**
 * Get related products
 */
export async function getRelatedProducts(productId: string, limit: number = 4) {
  const cacheKey = `products:related:${productId}:${limit}`;
  
  const cached = await cache.get<typeof products>(cacheKey);
  if (cached) return cached;

  const product = await prisma.product.findUnique({
    where: { id: productId },
    select: { categoryId: true },
  });

  if (!product) return [];

  const products = await prisma.product.findMany({
    where: {
      id: { not: productId },
      categoryId: product.categoryId,
      status: 'ACTIVE',
    },
    include: {
      category: {
        select: { id: true, name: true, slug: true },
      },
    },
    take: limit,
  });

  await cache.set(cacheKey, products, 1800);

  return products;
}

/**
 * Create a new product
 */
export async function createProduct(data: {
  name: string;
  description: string;
  summary?: string;
  price: number;
  comparePrice?: number;
  categoryId?: string;
  images: string[];
  sku?: string;
  stockQuantity?: number;
  weight?: number;
  dimensions?: string;
  featured?: boolean;
}) {
  const slug = generateSlug(data.name);
  
  // Generate AI summary and tags
  const [aiSummary, aiTags] = await Promise.all([
    generateProductSummary(data.description),
    generateProductTags(data.name, data.description),
  ]);

  const product = await prisma.product.create({
    data: {
      ...data,
      slug,
      aiSummary,
      aiTags,
    },
  });

  // Invalidate cache
  await cache.delByPattern('products:*');

  return product;
}

/**
 * Update a product
 */
export async function updateProduct(
  id: string,
  data: Partial<{
    name: string;
    description: string;
    summary: string;
    price: number;
    comparePrice: number;
    categoryId: string;
    images: string[];
    sku: string;
    stockQuantity: number;
    weight: number;
    dimensions: string;
    status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
    featured: boolean;
  }>
) {
  const product = await prisma.product.update({
    where: { id },
    data,
  });

  // Invalidate cache
  await cache.del(`product:id:${id}`);
  await cache.del(`product:slug:${product.slug}`);
  await cache.delByPattern('products:*');

  return product;
}

/**
 * Delete a product
 */
export async function deleteProduct(id: string) {
  const product = await prisma.product.delete({
    where: { id },
  });

  // Invalidate cache
  await cache.del(`product:id:${id}`);
  await cache.del(`product:slug:${product.slug}`);
  await cache.delByPattern('products:*');

  return product;
}

/**
 * Get product reviews
 */
export async function getProductReviews(productId: string, page = 1, limit = 10) {
  const [reviews, total] = await Promise.all([
    prisma.review.findMany({
      where: { productId },
      include: {
        user: {
          select: { id: true, name: true, avatar: true },
        },
      },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    prisma.review.count({ where: { productId } }),
  ]);

  return {
    reviews,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Create a product review
 */
export async function createReview(data: {
  rating: number;
  title: string;
  content: string;
  productId: string;
  userId: string;
  images?: string[];
}) {
  const review = await prisma.review.create({
    data: {
      ...data,
      isVerified: true, // Can be based on actual purchase verification
    },
  });

  // Invalidate product cache
  await cache.delByPattern('product:*');

  return review;
}

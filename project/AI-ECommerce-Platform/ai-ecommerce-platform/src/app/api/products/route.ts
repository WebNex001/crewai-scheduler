/**
 * 商品管理 API 路由
 * GET: 获取商品列表
 * POST: 创建商品（仅管理员）
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/db';
import { productListQuerySchema, productCreateSchema } from '@/lib/validators/auth';
import { slugify } from '@/lib/utils';

// ============================================
// GET /api/products - 获取商品列表
// ============================================
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    
    // 验证查询参数
    const query = productListQuerySchema.parse({
      page: searchParams.get('page') || 1,
      limit: searchParams.get('limit') || 20,
      category: searchParams.get('category'),
      search: searchParams.get('search'),
      minPrice: searchParams.get('minPrice'),
      maxPrice: searchParams.get('maxPrice'),
      brand: searchParams.get('brand'),
      tags: searchParams.get('tags'),
      sort: searchParams.get('sort') || 'newest',
      isFeatured: searchParams.get('isFeatured'),
    });

    // 构建查询条件
    const where: Record<string, unknown> = {
      isActive: true,
    };

    // 分类筛选
    if (query.category) {
      where.categoryId = query.category;
    }

    // 搜索筛选
    if (query.search) {
      where.OR = [
        { name: { contains: query.search, mode: 'insensitive' } },
        { description: { contains: query.search, mode: 'insensitive' } },
        { brand: { contains: query.search, mode: 'insensitive' } },
      ];
    }

    // 价格区间筛选
    if (query.minPrice !== undefined || query.maxPrice !== undefined) {
      where.price = {};
      if (query.minPrice !== undefined) {
        (where.price as Record<string, number>).gte = query.minPrice;
      }
      if (query.maxPrice !== undefined) {
        (where.price as Record<string, number>).lte = query.maxPrice;
      }
    }

    // 品牌筛选
    if (query.brand) {
      where.brand = query.brand;
    }

    // 标签筛选
    if (query.tags) {
      const tags = query.tags.split(',');
      where.tags = { hasSome: tags };
    }

    // 热门精选
    if (query.isFeatured) {
      where.isFeatured = true;
    }

    // 排序
    let orderBy: Record<string, string> = {};
    switch (query.sort) {
      case 'price-asc':
        orderBy = { price: 'asc' };
        break;
      case 'price-desc':
        orderBy = { price: 'desc' };
        break;
      case 'sales':
        orderBy = { sales: 'desc' };
        break;
      case 'rating':
        orderBy = { rating: 'desc' };
        break;
      case 'newest':
      default:
        orderBy = { createdAt: 'desc' };
    }

    // 查询数据
    const [products, total] = await Promise.all([
      prisma.product.findMany({
        where,
        include: {
          category: {
            select: { id: true, name: true, slug: true },
          },
        },
        orderBy,
        skip: (query.page - 1) * query.limit,
        take: query.limit,
      }),
      prisma.product.count({ where }),
    ]);

    return NextResponse.json({
      success: true,
      data: products,
      pagination: {
        total,
        page: query.page,
        pageSize: query.limit,
        totalPages: Math.ceil(total / query.limit),
        hasNextPage: query.page < Math.ceil(total / query.limit),
        hasPrevPage: query.page > 1,
      },
    });
  } catch (error) {
    console.error('获取商品列表失败:', error);
    return NextResponse.json(
      { success: false, error: '获取商品列表失败' },
      { status: 500 }
    );
  }
}

// ============================================
// POST /api/products - 创建商品
// ============================================
export async function POST(request: NextRequest) {
  try {
    // 验证用户登录和权限
    const session = await getServerSession(authOptions);
    if (!session || session.user.role !== 'ADMIN') {
      return NextResponse.json(
        { success: false, error: '无权限访问' },
        { status: 403 }
      );
    }

    // 解析和验证请求体
    const body = await request.json();
    const validatedData = productCreateSchema.parse(body);

    // 生成唯一 slug
    let slug = slugify(validatedData.name);
    const existingProduct = await prisma.product.findUnique({
      where: { slug },
    });
    if (existingProduct) {
      slug = `${slug}-${Date.now()}`;
    }

    // 创建商品
    const product = await prisma.product.create({
      data: {
        ...validatedData,
        slug,
      },
    });

    return NextResponse.json({
      success: true,
      data: product,
      message: '商品创建成功',
    });
  } catch (error) {
    console.error('创建商品失败:', error);
    return NextResponse.json(
      { success: false, error: '创建商品失败' },
      { status: 500 }
    );
  }
}

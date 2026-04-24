/**
 * 商品详情 API 路由
 * GET: 获取商品详情
 * PUT: 更新商品（仅管理员）
 * DELETE: 删除商品（仅管理员）
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/db';
import { productCreateSchema } from '@/lib/validators/auth';
import { recordBrowsingHistory } from '@/lib/ai/recommendation';

// ============================================
// GET /api/products/[id] - 获取商品详情
// ============================================
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;

    // 获取商品信息
    const product = await prisma.product.findUnique({
      where: { id },
      include: {
        category: {
          include: {
            parent: {
              select: { id: true, name: true, slug: true },
            },
            children: {
              select: { id: true, name: true, slug: true },
            },
          },
        },
        attributes: {
          orderBy: { sortOrder: 'asc' },
        },
        specifications: true,
        reviews: {
          where: { status: 'APPROVED' },
          include: {
            user: {
              select: { id: true, name: true, image: true },
            },
          },
          orderBy: { createdAt: 'desc' },
          take: 10,
        },
      },
    });

    if (!product) {
      return NextResponse.json(
        { success: false, error: '商品不存在' },
        { status: 404 }
      );
    }

    // 增加浏览量
    await prisma.product.update({
      where: { id },
      data: { views: { increment: 1 } },
    });

    // 记录浏览历史（如果用户已登录）
    const session = await getServerSession(authOptions);
    if (session?.user?.id) {
      await recordBrowsingHistory(session.user.id, id, undefined, 'direct');
    }

    return NextResponse.json({
      success: true,
      data: product,
    });
  } catch (error) {
    console.error('获取商品详情失败:', error);
    return NextResponse.json(
      { success: false, error: '获取商品详情失败' },
      { status: 500 }
    );
  }
}

// ============================================
// PUT /api/products/[id] - 更新商品
// ============================================
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // 验证用户登录和权限
    const session = await getServerSession(authOptions);
    if (!session || session.user.role !== 'ADMIN') {
      return NextResponse.json(
        { success: false, error: '无权限访问' },
        { status: 403 }
      );
    }

    const { id } = params;

    // 检查商品是否存在
    const existingProduct = await prisma.product.findUnique({
      where: { id },
    });

    if (!existingProduct) {
      return NextResponse.json(
        { success: false, error: '商品不存在' },
        { status: 404 }
      );
    }

    // 解析和验证请求体
    const body = await request.json();
    const validatedData = productCreateSchema.partial().parse(body);

    // 更新商品
    const product = await prisma.product.update({
      where: { id },
      data: validatedData,
    });

    return NextResponse.json({
      success: true,
      data: product,
      message: '商品更新成功',
    });
  } catch (error) {
    console.error('更新商品失败:', error);
    return NextResponse.json(
      { success: false, error: '更新商品失败' },
      { status: 500 }
    );
  }
}

// ============================================
// DELETE /api/products/[id] - 删除商品
// ============================================
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // 验证用户登录和权限
    const session = await getServerSession(authOptions);
    if (!session || session.user.role !== 'ADMIN') {
      return NextResponse.json(
        { success: false, error: '无权限访问' },
        { status: 403 }
      );
    }

    const { id } = params;

    // 检查商品是否存在
    const existingProduct = await prisma.product.findUnique({
      where: { id },
    });

    if (!existingProduct) {
      return NextResponse.json(
        { success: false, error: '商品不存在' },
        { status: 404 }
      );
    }

    // 软删除：设置为不活跃
    await prisma.product.update({
      where: { id },
      data: { isActive: false },
    });

    return NextResponse.json({
      success: true,
      message: '商品已删除',
    });
  } catch (error) {
    console.error('删除商品失败:', error);
    return NextResponse.json(
      { success: false, error: '删除商品失败' },
      { status: 500 }
    );
  }
}

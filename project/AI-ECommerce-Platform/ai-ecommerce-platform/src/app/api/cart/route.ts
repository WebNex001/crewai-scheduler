/**
 * 购物车 API 路由
 * GET: 获取购物车
 * POST: 添加商品到购物车
 * DELETE: 清空购物车
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/db';
import { addToCartSchema } from '@/lib/validators/auth';

// ============================================
// GET /api/cart - 获取购物车
// ============================================
export async function GET() {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json(
        { success: false, error: '请先登录' },
        { status: 401 }
      );
    }

    // 获取或创建购物车
    let cart = await prisma.cart.findUnique({
      where: { userId: session.user.id },
      include: {
        items: {
          include: {
            product: {
              include: {
                category: {
                  select: { id: true, name: true, slug: true },
                },
              },
            },
          },
        },
      },
    });

    // 如果购物车不存在，创建一个新的
    if (!cart) {
      cart = await prisma.cart.create({
        data: { userId: session.user.id },
        include: {
          items: {
            include: {
              product: true,
            },
          },
        },
      });
    }

    // 计算购物车统计
    const totalItems = cart.items.reduce((sum, item) => sum + item.quantity, 0);
    const subtotal = cart.items.reduce(
      (sum, item) => sum + Number(item.product.price) * item.quantity,
      0
    );

    return NextResponse.json({
      success: true,
      data: {
        ...cart,
        totalItems,
        subtotal,
      },
    });
  } catch (error) {
    console.error('获取购物车失败:', error);
    return NextResponse.json(
      { success: false, error: '获取购物车失败' },
      { status: 500 }
    );
  }
}

// ============================================
// POST /api/cart - 添加商品到购物车
// ============================================
export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json(
        { success: false, error: '请先登录' },
        { status: 401 }
      );
    }

    // 验证请求体
    const body = await request.json();
    const { productId, quantity } = addToCartSchema.parse(body);

    // 检查商品是否存在
    const product = await prisma.product.findUnique({
      where: { id: productId, isActive: true },
    });

    if (!product) {
      return NextResponse.json(
        { success: false, error: '商品不存在或已下架' },
        { status: 404 }
      );
    }

    // 检查库存
    if (product.stock < quantity) {
      return NextResponse.json(
        { success: false, error: '库存不足' },
        { status: 400 }
      );
    }

    // 获取或创建购物车
    let cart = await prisma.cart.findUnique({
      where: { userId: session.user.id },
    });

    if (!cart) {
      cart = await prisma.cart.create({
        data: { userId: session.user.id },
      });
    }

    // 检查购物车中是否已有该商品
    const existingItem = await prisma.cartItem.findUnique({
      where: {
        cartId_productId: {
          cartId: cart.id,
          productId,
        },
      },
    });

    if (existingItem) {
      // 更新数量
      const newQuantity = existingItem.quantity + quantity;
      if (newQuantity > product.stock) {
        return NextResponse.json(
          { success: false, error: '库存不足' },
          { status: 400 }
        );
      }

      await prisma.cartItem.update({
        where: { id: existingItem.id },
        data: { quantity: newQuantity },
      });
    } else {
      // 添加新商品
      await prisma.cartItem.create({
        data: {
          cartId: cart.id,
          productId,
          quantity,
        },
      });
    }

    // 返回更新后的购物车
    const updatedCart = await prisma.cart.findUnique({
      where: { userId: session.user.id },
      include: {
        items: {
          include: {
            product: true,
          },
        },
      },
    });

    const totalItems = updatedCart?.items.reduce(
      (sum, item) => sum + item.quantity,
      0
    ) || 0;
    const subtotal =
      updatedCart?.items.reduce(
        (sum, item) => sum + Number(item.product.price) * item.quantity,
        0
      ) || 0;

    return NextResponse.json({
      success: true,
      data: {
        ...updatedCart,
        totalItems,
        subtotal,
      },
      message: '已添加到购物车',
    });
  } catch (error) {
    console.error('添加到购物车失败:', error);
    return NextResponse.json(
      { success: false, error: '添加到购物车失败' },
      { status: 500 }
    );
  }
}

// ============================================
// DELETE /api/cart - 清空购物车
// ============================================
export async function DELETE(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json(
        { success: false, error: '请先登录' },
        { status: 401 }
      );
    }

    const { searchParams } = new URL(request.url);
    const itemId = searchParams.get('itemId');

    if (itemId) {
      // 删除单个商品
      await prisma.cartItem.delete({
        where: { id: itemId },
      });
    } else {
      // 清空整个购物车
      const cart = await prisma.cart.findUnique({
        where: { userId: session.user.id },
      });
      if (cart) {
        await prisma.cartItem.deleteMany({
          where: { cartId: cart.id },
        });
      }
    }

    return NextResponse.json({
      success: true,
      message: itemId ? '已从购物车移除' : '购物车已清空',
    });
  } catch (error) {
    console.error('删除购物车商品失败:', error);
    return NextResponse.json(
      { success: false, error: '删除失败' },
      { status: 500 }
    );
  }
}

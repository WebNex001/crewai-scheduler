/**
 * 订单管理 API 路由
 * GET: 获取订单列表
 * POST: 创建订单
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/db';
import { createOrderSchema, orderListQuerySchema } from '@/lib/validators/auth';
import { generateOrderNumber, calculateDiscountPercentage } from '@/lib/utils';
import { createPaymentIntent, buildLineItems } from '@/lib/stripe';

// ============================================
// GET /api/orders - 获取订单列表
// ============================================
export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json(
        { success: false, error: '请先登录' },
        { status: 401 }
      );
    }

    const { searchParams } = new URL(request.url);
    
    // 验证查询参数
    const query = orderListQuerySchema.parse({
      page: searchParams.get('page') || 1,
      limit: searchParams.get('limit') || 10,
      status: searchParams.get('status'),
    });

    // 构建查询条件
    const where: Record<string, unknown> = {
      userId: session.user.id,
    };

    // 管理员可以查看所有订单
    if (session.user.role === 'ADMIN' || session.user.role === 'MANAGER') {
      delete where.userId;
    }

    // 订单状态筛选
    if (query.status) {
      where.status = query.status;
    }

    // 查询订单
    const [orders, total] = await Promise.all([
      prisma.order.findMany({
        where,
        include: {
          items: {
            include: {
              product: {
                select: {
                  id: true,
                  name: true,
                  slug: true,
                  images: true,
                },
              },
            },
          },
        },
        orderBy: { createdAt: 'desc' },
        skip: (query.page - 1) * query.limit,
        take: query.limit,
      }),
      prisma.order.count({ where }),
    ]);

    return NextResponse.json({
      success: true,
      data: orders,
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
    console.error('获取订单列表失败:', error);
    return NextResponse.json(
      { success: false, error: '获取订单列表失败' },
      { status: 500 }
    );
  }
}

// ============================================
// POST /api/orders - 创建订单
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
    const { addressId, paymentMethod, couponCode, note } = createOrderSchema.parse(body);

    // 获取购物车
    const cart = await prisma.cart.findUnique({
      where: { userId: session.user.id },
      include: {
        items: {
          include: { product: true },
        },
      },
    });

    if (!cart || cart.items.length === 0) {
      return NextResponse.json(
        { success: false, error: '购物车为空' },
        { status: 400 }
      );
    }

    // 验证库存
    for (const item of cart.items) {
      if (item.product.stock < item.quantity) {
        return NextResponse.json(
          {
            success: false,
            error: `商品"${item.product.name}"库存不足`,
          },
          { status: 400 }
        );
      }
    }

    // 获取地址
    const address = await prisma.address.findFirst({
      where: { id: addressId, userId: session.user.id },
    });

    if (!address) {
      return NextResponse.json(
        { success: false, error: '收货地址不存在' },
        { status: 400 }
      );
    }

    // 计算订单金额
    let subtotal = 0;
    const orderItems = cart.items.map((item) => {
      const itemSubtotal = Number(item.product.price) * item.quantity;
      subtotal += itemSubtotal;
      return {
        productId: item.productId,
        productName: item.product.name,
        productImage: item.product.images[0],
        price: item.product.price,
        quantity: item.quantity,
        subtotal: itemSubtotal,
      };
    });

    // 计算运费（满99免运费）
    let shippingFee = subtotal >= 99 ? 0 : 10;

    // 应用优惠券
    let discount = 0;
    if (couponCode) {
      const coupon = await prisma.coupon.findUnique({
        where: { code: couponCode },
      });

      if (
        coupon &&
        coupon.isActive &&
        new Date() >= coupon.startsAt &&
        new Date() <= coupon.expiresAt &&
        coupon.usageCount < (coupon.usageLimit || Infinity)
      ) {
        // 检查最低消费
        if (!coupon.minAmount || subtotal >= Number(coupon.minAmount)) {
          if (coupon.type === 'FIXED') {
            discount = Number(coupon.value);
          } else if (coupon.type === 'PERCENTAGE') {
            discount = (subtotal * Number(coupon.value)) / 100;
            // 最高折扣限制
            if (coupon.maxDiscount && discount > Number(coupon.maxDiscount)) {
              discount = Number(coupon.maxDiscount);
            }
          } else if (coupon.type === 'SHIPPING') {
            shippingFee = 0;
          }

          // 更新优惠券使用次数
          await prisma.coupon.update({
            where: { id: coupon.id },
            data: { usageCount: { increment: 1 } },
          });
        }
      }
    }

    // 计算总金额
    const total = Math.max(0, subtotal + shippingFee - discount);

    // 生成订单号
    const orderNumber = generateOrderNumber();

    // 创建订单
    const order = await prisma.order.create({
      data: {
        orderNumber,
        userId: session.user.id,
        subtotal,
        shippingFee,
        discount,
        total,
        recipient: address.recipient,
        phone: address.phone,
        shippingAddress: `${address.province}${address.city}${address.district}${address.detail}`,
        note,
        paymentMethod,
        items: {
          create: orderItems,
        },
      },
      include: {
        items: true,
      },
    });

    // 减少库存
    for (const item of cart.items) {
      await prisma.product.update({
        where: { id: item.productId },
        data: {
          stock: { decrement: item.quantity },
          sales: { increment: item.quantity },
        },
      });
    }

    // 清空购物车
    await prisma.cartItem.deleteMany({
      where: { cartId: cart.id },
    });

    // 如果是 Stripe 支付，创建支付意图
    let paymentIntent = null;
    if (paymentMethod === 'stripe') {
      const lineItems = orderItems.map((item) => ({
        name: item.productName,
        amount: Number(item.price),
        quantity: item.quantity,
        images: cart.items.find((i) => i.productId === item.productId)?.product.images,
      }));

      paymentIntent = await createPaymentIntent(
        total,
        'cny',
        {
          orderId: order.id,
          orderNumber,
        }
      );
    }

    return NextResponse.json({
      success: true,
      data: {
        order,
        clientSecret: paymentIntent?.client_secret,
      },
      message: '订单创建成功',
    });
  } catch (error) {
    console.error('创建订单失败:', error);
    return NextResponse.json(
      { success: false, error: '创建订单失败' },
      { status: 500 }
    );
  }
}

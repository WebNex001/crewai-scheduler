'use server';

import { redirect } from 'next/navigation';
import { z } from 'zod';
import prisma from '@/lib/db';
import { cache } from '@/lib/redis';
import { getCurrentUser } from '@/lib/auth';
import { generateOrderNumber } from '@/lib/utils';
import { createCheckoutSession, createPaymentIntent, verifyWebhookSignature } from '@/lib/stripe';
import { checkoutSchema, couponSchema } from '@/lib/validations';

/**
 * Create checkout session
 */
export async function createCheckout(formData: FormData) {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      redirect('/auth/login');
    }

    const data = {
      addressId: formData.get('addressId') as string,
      paymentMethod: formData.get('paymentMethod') as 'stripe' | 'cod',
      couponCode: formData.get('couponCode') as string | undefined,
      customerNote: formData.get('customerNote') as string | undefined,
    };

    // Validate input
    checkoutSchema.parse(data);

    // Get user's cart
    const cart = await prisma.cart.findUnique({
      where: { userId: user.id },
      include: {
        items: {
          include: {
            product: true,
            variant: true,
          },
        },
      },
    });

    if (!cart || cart.items.length === 0) {
      return { error: 'Cart is empty' };
    }

    // Verify address belongs to user
    const address = await prisma.address.findFirst({
      where: {
        id: data.addressId,
        userId: user.id,
      },
    });

    if (!address) {
      return { error: 'Invalid shipping address' };
    }

    // Calculate totals
    let subtotal = 0;
    const orderItems = [];

    for (const item of cart.items) {
      const price = item.variant?.price 
        ? parseFloat(item.variant.price.toString())
        : parseFloat(item.product.price.toString());
      const total = price * item.quantity;
      subtotal += total;

      orderItems.push({
        productId: item.productId,
        variantId: item.variantId,
        productName: item.product.name,
        productImage: item.product.images[0] || null,
        variantName: item.variant?.name || null,
        sku: item.variant?.sku || item.product.sku || null,
        price,
        quantity: item.quantity,
        total,
      });
    }

    // Apply coupon if provided
    let discount = 0;
    if (data.couponCode) {
      const couponValidation = couponSchema.parse({ code: data.couponCode });
      
      const coupon = await prisma.coupon.findUnique({
        where: { code: couponValidation.code },
      });

      if (coupon && coupon.isActive) {
        const now = new Date();
        if (now >= coupon.startsAt && now <= coupon.expiresAt) {
          const minAmount = coupon.minOrderAmount 
            ? parseFloat(coupon.minOrderAmount.toString()) 
            : 0;
          
          if (subtotal >= minAmount) {
            if (coupon.type === 'PERCENTAGE') {
              discount = subtotal * (parseFloat(coupon.value.toString()) / 100);
            } else if (coupon.type === 'FIXED') {
              discount = parseFloat(coupon.value.toString());
            }
            
            // Update coupon usage
            await prisma.coupon.update({
              where: { id: coupon.id },
              data: { usedCount: { increment: 1 } },
            });
          }
        }
      }
    }

    // Calculate shipping (free over $50)
    const shippingCost = subtotal >= 50 ? 0 : 5.99;
    
    // Calculate tax (8%)
    const tax = (subtotal - discount) * 0.08;
    
    // Calculate total
    const total = subtotal - discount + shippingCost + tax;

    // Create order
    const orderNumber = generateOrderNumber();
    
    const order = await prisma.order.create({
      data: {
        orderNumber,
        userId: user.id,
        status: 'PENDING',
        subtotal,
        tax,
        shippingCost,
        discount,
        total,
        shippingAddressId: address.id,
        shippingMethod: 'standard',
        customerNote: data.customerNote,
        paymentMethod: data.paymentMethod,
        items: {
          create: orderItems,
        },
      },
      include: {
        items: true,
      },
    });

    // Update inventory
    for (const item of cart.items) {
      await prisma.product.update({
        where: { id: item.productId },
        data: {
          stockQuantity: {
            decrement: item.quantity,
          },
        },
      });
    }

    // Clear cart
    await prisma.cartItem.deleteMany({
      where: { cartId: cart.id },
    });

    // Create Stripe checkout session for card payments
    if (data.paymentMethod === 'stripe') {
      const baseUrl = process.env.APP_URL || 'http://localhost:3000';
      
      const session = await createCheckoutSession({
        orderId: order.id,
        orderNumber: order.orderNumber,
        items: orderItems.map((item) => ({
          name: item.productName,
          description: item.variantName || undefined,
          amount: parseFloat(item.total.toString()),
          quantity: item.quantity,
          image: item.productImage || undefined,
        })),
        customerEmail: user.email,
        successUrl: `${baseUrl}/orders/${order.id}/success`,
        cancelUrl: `${baseUrl}/cart`,
        metadata: { orderId: order.id },
      });

      if (session.url) {
        redirect(session.url);
      }
    }

    // For COD, redirect to order success page
    redirect(`/orders/${order.id}/success`);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { error: error.errors[0].message };
    }
    console.error('Checkout error:', error);
    return { error: 'Failed to process checkout' };
  }
}

/**
 * Get user's orders
 */
export async function getOrders(page = 1, limit = 10) {
  const user = await getCurrentUser();
  
  if (!user) {
    return { orders: [], total: 0 };
  }

  const [orders, total] = await Promise.all([
    prisma.order.findMany({
      where: { userId: user.id },
      include: {
        items: {
          include: {
            product: {
              select: { images: true },
            },
          },
        },
      },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    prisma.order.count({ where: { userId: user.id } }),
  ]);

  return {
    orders,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Get order by ID
 */
export async function getOrder(orderId: string) {
  const user = await getCurrentUser();
  
  if (!user) {
    return null;
  }

  const order = await prisma.order.findFirst({
    where: {
      id: orderId,
      userId: user.id,
    },
    include: {
      items: {
        include: {
          product: {
            select: { images: true, slug: true },
          },
          variant: true,
        },
      },
      address: true,
    },
  });

  return order;
}

/**
 * Handle Stripe webhook
 */
export async function handleStripeWebhook(payload: string, signature: string) {
  try {
    const event = verifyWebhookSignature(payload, signature);

    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object;
        const orderId = session.metadata?.orderId;

        if (orderId) {
          await prisma.order.update({
            where: { id: orderId },
            data: {
              paymentStatus: 'PAID',
              stripePaymentId: session.payment_intent as string,
              paidAt: new Date(),
              status: 'CONFIRMED',
            },
          });
        }
        break;
      }

      case 'payment_intent.payment_failed': {
        const paymentIntent = event.data.object;
        
        await prisma.order.updateMany({
          where: { stripePaymentId: paymentIntent.id },
          data: {
            paymentStatus: 'FAILED',
          },
        });
        break;
      }

      case 'charge.refunded': {
        const charge = event.data.object;
        
        await prisma.order.updateMany({
          where: { stripePaymentId: charge.payment_intent as string },
          data: {
            paymentStatus: 'REFUNDED',
            status: 'REFUNDED',
          },
        });
        break;
      }
    }

    return { received: true };
  } catch (error) {
    console.error('Webhook error:', error);
    return { error: 'Webhook processing failed' };
  }
}

/**
 * Cancel order
 */
export async function cancelOrder(orderId: string) {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      return { error: 'Not authenticated' };
    }

    const order = await prisma.order.findFirst({
      where: {
        id: orderId,
        userId: user.id,
      },
    });

    if (!order) {
      return { error: 'Order not found' };
    }

    // Only allow cancellation of pending orders
    if (order.status !== 'PENDING' && order.status !== 'CONFIRMED') {
      return { error: 'Order cannot be cancelled at this stage' };
    }

    // Restore inventory
    const orderItems = await prisma.orderItem.findMany({
      where: { orderId },
    });

    for (const item of orderItems) {
      await prisma.product.update({
        where: { id: item.productId },
        data: {
          stockQuantity: {
            increment: item.quantity,
          },
        },
      });
    }

    // Update order status
    await prisma.order.update({
      where: { id: orderId },
      data: {
        status: 'CANCELLED',
        paymentStatus: 'REFUNDED',
      },
    });

    // Invalidate cache
    await cache.delByPattern(`order:${orderId}*`);

    return { success: true };
  } catch (error) {
    console.error('Cancel order error:', error);
    return { error: 'Failed to cancel order' };
  }
}

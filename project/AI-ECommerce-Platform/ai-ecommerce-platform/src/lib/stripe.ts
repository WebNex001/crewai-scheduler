/**
 * Stripe 支付集成
 * 处理支付、退款等交易操作
 */

import Stripe from 'stripe';
import { Decimal } from '@prisma/client/runtime/library';

// 初始化 Stripe 客户端
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2024-04-10',
  typescript: true,
});

/**
 * 创建支付意图
 */
export async function createPaymentIntent(
  amount: number,
  currency: string = 'cny',
  metadata?: Record<string, string>
): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.create({
    amount: Math.round(amount * 100), // 转换为分
    currency,
    automatic_payment_methods: {
      enabled: true,
    },
    metadata,
  });
}

/**
 * 确认支付意图
 */
export async function confirmPaymentIntent(
  paymentIntentId: string,
  paymentMethodId: string
): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.confirm(paymentIntentId, {
    payment_method: paymentMethodId,
  });
}

/**
 * 取消支付意图
 */
export async function cancelPaymentIntent(
  paymentIntentId: string
): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.cancel(paymentIntentId);
}

/**
 * 创建退款
 */
export async function createRefund(
  paymentIntentId: string,
  amount?: number,
  reason?: Stripe.RefundCreateParams.Reason
): Promise<Stripe.Refund> {
  const params: Stripe.RefundCreateParams = {
    payment_intent: paymentIntentId,
  };

  if (amount) {
    params.amount = Math.round(amount * 100); // 转换为分
  }

  if (reason) {
    params.reason = reason;
  }

  return stripe.refunds.create(params);
}

/**
 * 验证 Stripe Webhook 签名
 */
export function verifyWebhookSignature(
  payload: string | Buffer,
  signature: string
): Stripe.Event {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    throw new Error('Stripe webhook secret is not configured');
  }

  return stripe.webhooks.constructEvent(payload, signature, webhookSecret);
}

/**
 * 创建 Stripe Checkout 会话
 */
export async function createCheckoutSession(
  lineItems: Stripe.Checkout.SessionCreateParams.LineItem[],
  successUrl: string,
  cancelUrl: string,
  metadata?: Record<string, string>
): Promise<Stripe.Checkout.Session> {
  return stripe.checkout.sessions.create({
    mode: 'payment',
    line_items: lineItems,
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata,
    allow_promotion_codes: true,
  });
}

/**
 * 创建产品（同步到 Stripe）
 */
export async function createStripeProduct(
  name: string,
  description?: string,
  images?: string[]
): Promise<Stripe.Product> {
  return stripe.products.create({
    name,
    description,
    images,
  });
}

/**
 * 创建价格（Stripe 产品下的价格单位）
 */
export async function createStripePrice(
  productId: string,
  amount: number,
  currency: string = 'cny'
): Promise<Stripe.Price> {
  return stripe.prices.create({
    product: productId,
    unit_amount: Math.round(amount * 100),
    currency,
  });
}

/**
 * 获取支付意图详情
 */
export async function getPaymentIntent(
  paymentIntentId: string
): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.retrieve(paymentIntentId);
}

/**
 * 获取 Checkout 会话详情
 */
export async function getCheckoutSession(
  sessionId: string
): Promise<Stripe.Checkout.Session> {
  return stripe.checkout.sessions.retrieve(sessionId);
}

/**
 * 格式化金额（从分转换为元）
 */
export function formatStripeAmount(amount: number): number {
  return amount / 100;
}

/**
 * 格式化金额（从元转换为分）
 */
export function formatToStripeAmount(amount: number): number {
  return Math.round(amount * 100);
}

// ============================================
// 订单支付相关工具函数
// ============================================

/**
 * 构建 Stripe 订单行项目
 */
export function buildLineItems(
  items: Array<{
    name: string;
    amount: number;
    quantity: number;
    images?: string[];
  }>
): Stripe.Checkout.SessionCreateParams.LineItem[] {
  return items.map((item) => ({
    price_data: {
      currency: 'cny',
      product_data: {
        name: item.name,
        images: item.images,
      },
      unit_amount: formatToStripeAmount(item.amount),
    },
    quantity: item.quantity,
  }));
}

/**
 * 计算订单金额
 */
export function calculateOrderAmount(
  subtotal: number,
  shippingFee: number = 0,
  discount: number = 0
): number {
  const total = subtotal + shippingFee - discount;
  return Math.max(0, total);
}

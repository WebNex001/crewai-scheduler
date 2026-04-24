import Stripe from 'stripe';
import { loadStripe, Stripe as StripeJS } from '@stripe/stripe-js';

// Server-side Stripe instance
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2023-10-16',
  typescript: true,
});

// Client-side Stripe promise
let stripePromise: Promise<StripeJS | null> | null = null;

export const getStripe = () => {
  if (!stripePromise) {
    stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || '');
  }
  return stripePromise;
};

/**
 * Create a Stripe checkout session
 */
export async function createCheckoutSession({
  orderId,
  orderNumber,
  items,
  customerEmail,
  successUrl,
  cancelUrl,
  metadata = {},
}: {
  orderId: string;
  orderNumber: string;
  items: Array<{
    name: string;
    description?: string;
    amount: number;
    quantity: number;
    image?: string;
  }>;
  customerEmail: string;
  successUrl: string;
  cancelUrl: string;
  metadata?: Record<string, string>;
}) {
  const session = await stripe.checkout.sessions.create({
    payment_method_types: ['card'],
    mode: 'payment',
    customer_email: customerEmail,
    line_items: items.map((item) => ({
      price_data: {
        currency: 'usd',
        product_data: {
          name: item.name,
          description: item.description,
          images: item.image ? [item.image] : [],
        },
        unit_amount: Math.round(item.amount * 100), // Convert to cents
      },
      quantity: item.quantity,
    })),
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata: {
      orderId,
      orderNumber,
      ...metadata,
    },
    shipping_address_collection: {
      allowed_countries: ['US', 'CA', 'GB'],
    },
    billing_address_collection: 'required',
  });

  return session;
}

/**
 * Create a payment intent for orders
 */
export async function createPaymentIntent({
  amount,
  orderId,
  orderNumber,
  customerId,
  metadata = {},
}: {
  amount: number;
  orderId: string;
  orderNumber: string;
  customerId?: string;
  metadata?: Record<string, string>;
}) {
  const paymentIntent = await stripe.paymentIntents.create({
    amount: Math.round(amount * 100), // Convert to cents
    currency: 'usd',
    metadata: {
      orderId,
      orderNumber,
      ...metadata,
    },
    ...(customerId && { customer: customerId }),
  });

  return paymentIntent;
}

/**
 * Verify Stripe webhook signature
 */
export function verifyWebhookSignature(
  payload: string | Buffer,
  signature: string
): Stripe.Event {
  return stripe.webhooks.constructEvent(
    payload,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET || ''
  );
}

/**
 * Create refund for an order
 */
export async function createRefund({
  paymentIntentId,
  amount,
  reason,
}: {
  paymentIntentId: string;
  amount?: number;
  reason?: Stripe.RefundCreateParams.Reason;
}) {
  const refund = await stripe.refunds.create({
    payment_intent: paymentIntentId,
    ...(amount && { amount: Math.round(amount * 100) }),
    reason,
  });

  return refund;
}

/**
 * Get Stripe customer by email
 */
export async function getOrCreateCustomer(email: string, name?: string) {
  const existingCustomers = await stripe.customers.list({
    email,
    limit: 1,
  });

  if (existingCustomers.data.length > 0) {
    return existingCustomers.data[0];
  }

  return stripe.customers.create({
    email,
    name: name || undefined,
  });
}

/**
 * Format amount for Stripe (convert to cents)
 */
export function toStripeAmount(amount: number): number {
  return Math.round(amount * 100);
}

/**
 * Format amount from Stripe (convert from cents)
 */
export function fromStripeAmount(amount: number): number {
  return amount / 100;
}

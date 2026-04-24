/**
 * Stripe Payment Integration
 * 
 * This module provides Stripe payment functionality including:
 * - Creating payment intents
 * - Processing payments
 * - Handling webhooks
 * - Managing customers
 */

import Stripe from 'stripe'

// Initialize Stripe with API key
const stripeSecretKey = process.env.STRIPE_SECRET_KEY

if (!stripeSecretKey) {
  console.warn('Stripe secret key not configured')
}

export const stripe = stripeSecretKey 
  ? new Stripe(stripeSecretKey, {
      apiVersion: '2023-10-16',
      typescript: true,
    })
  : null

/**
 * Create a payment intent for an order
 * @param amount - Amount in cents
 * @param currency - Currency code (default: USD)
 * @param customerId - Stripe customer ID (optional)
 * @param metadata - Additional metadata
 * @returns Payment intent
 */
export async function createPaymentIntent(
  amount: number,
  currency: string = 'usd',
  customerId?: string,
  metadata?: Record<string, string>
): Promise<Stripe.PaymentIntent | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.paymentIntents.create({
    amount,
    currency,
    customer: customerId,
    metadata: {
      ...metadata,
    },
    automatic_payment_methods: {
      enabled: true,
    },
  })
}

/**
 * Retrieve a payment intent
 * @param paymentIntentId - Payment intent ID
 * @returns Payment intent
 */
export async function retrievePaymentIntent(
  paymentIntentId: string
): Promise<Stripe.PaymentIntent | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.paymentIntents.retrieve(paymentIntentId)
}

/**
 * Update a payment intent
 * @param paymentIntentId - Payment intent ID
 * @param data - Data to update
 * @returns Updated payment intent
 */
export async function updatePaymentIntent(
  paymentIntentId: string,
  data: {
    amount?: number
    metadata?: Record<string, string>
  }
): Promise<Stripe.PaymentIntent | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.paymentIntents.update(paymentIntentId, data)
}

/**
 * Cancel a payment intent
 * @param paymentIntentId - Payment intent ID
 * @returns Cancelled payment intent
 */
export async function cancelPaymentIntent(
  paymentIntentId: string
): Promise<Stripe.PaymentIntent | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.paymentIntents.cancel(paymentIntentId)
}

/**
 * Create or retrieve a Stripe customer
 * @param email - Customer email
 * @param name - Customer name
 * @returns Stripe customer
 */
export async function createOrGetCustomer(
  email: string,
  name?: string
): Promise<Stripe.Customer | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  // Check if customer already exists
  const existingCustomers = await stripe.customers.list({
    email,
    limit: 1,
  })

  if (existingCustomers.data.length > 0) {
    return existingCustomers.data[0]
  }

  // Create new customer
  return stripe.customers.create({
    email,
    name,
  })
}

/**
 * Create a Stripe checkout session
 * @param lineItems - Line items for checkout
 * @param customerId - Customer ID (optional)
 * @param successUrl - Success redirect URL
 * @param cancelUrl - Cancel redirect URL
 * @param metadata - Additional metadata
 * @returns Checkout session
 */
export async function createCheckoutSession(
  lineItems: Stripe.Checkout.SessionCreateParams.LineItem[],
  successUrl: string,
  cancelUrl: string,
  customerId?: string,
  metadata?: Record<string, string>
): Promise<Stripe.Checkout.Session | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.checkout.sessions.create({
    mode: 'payment',
    line_items: lineItems,
    customer: customerId,
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata,
  })
}

/**
 * Construct webhook event from payload
 * @param payload - Request body
 * @param signature - Stripe signature header
 * @returns Webhook event
 */
export function constructWebhookEvent(
  payload: string | Buffer,
  signature: string
): Stripe.Event | null {
  if (!stripe || !process.env.STRIPE_WEBHOOK_SECRET) {
    throw new Error('Stripe webhook is not configured')
  }

  return stripe.webhooks.constructEvent(
    payload,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET
  )
}

/**
 * Create a refund
 * @param paymentIntentId - Payment intent ID
 * @param amount - Amount to refund in cents (optional, refunds full amount if not provided)
 * @returns Refund
 */
export async function createRefund(
  paymentIntentId: string,
  amount?: number
): Promise<Stripe.Refund | null> {
  if (!stripe) {
    throw new Error('Stripe is not configured')
  }

  return stripe.refunds.create({
    payment_intent: paymentIntentId,
    amount,
  })
}

/**
 * Format amount for Stripe (convert from dollars to cents)
 * @param amount - Amount in dollars
 * @returns Amount in cents
 */
export function formatAmountForStripe(amount: number): number {
  return Math.round(amount * 100)
}

/**
 * Format amount from Stripe (convert from cents to dollars)
 * @param amount - Amount in cents
 * @returns Amount in dollars
 */
export function formatAmountFromStripe(amount: number): number {
  return amount / 100
}

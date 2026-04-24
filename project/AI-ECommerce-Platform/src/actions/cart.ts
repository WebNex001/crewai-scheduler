'use server';

import { redirect } from 'next/navigation';
import { z } from 'zod';
import prisma from '@/lib/db';
import { cache } from '@/lib/redis';
import { getCurrentUser } from '@/lib/auth';
import { cartItemSchema } from '@/lib/validations';

/**
 * Get user's cart
 */
export async function getCart() {
  const user = await getCurrentUser();
  
  if (!user) {
    return null;
  }

  const cart = await prisma.cart.findUnique({
    where: { userId: user.id },
    include: {
      items: {
        include: {
          product: {
            select: {
              id: true,
              name: true,
              slug: true,
              price: true,
              images: true,
              stockQuantity: true,
            },
          },
          variant: true,
        },
      },
    },
  });

  return cart;
}

/**
 * Add item to cart
 */
export async function addToCart(formData: FormData) {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      redirect('/auth/login');
    }

    const data = {
      productId: formData.get('productId') as string,
      variantId: formData.get('variantId') as string | undefined,
      quantity: parseInt(formData.get('quantity') as string) || 1,
    };

    // Validate input
    cartItemSchema.parse(data);

    // Verify product exists and is in stock
    const product = await prisma.product.findUnique({
      where: { id: data.productId },
    });

    if (!product || product.status !== 'ACTIVE') {
      return { error: 'Product not available' };
    }

    if (product.trackInventory && product.stockQuantity < data.quantity) {
      return { error: 'Not enough stock available' };
    }

    // Get or create cart
    let cart = await prisma.cart.findUnique({
      where: { userId: user.id },
    });

    if (!cart) {
      cart = await prisma.cart.create({
        data: { userId: user.id },
      });
    }

    // Check if item already exists in cart
    const existingItem = await prisma.cartItem.findFirst({
      where: {
        cartId: cart.id,
        productId: data.productId,
        variantId: data.variantId || null,
      },
    });

    if (existingItem) {
      // Update quantity
      const newQuantity = existingItem.quantity + data.quantity;
      
      // Check stock
      if (product.trackInventory && product.stockQuantity < newQuantity) {
        return { error: 'Not enough stock available' };
      }

      await prisma.cartItem.update({
        where: { id: existingItem.id },
        data: { quantity: newQuantity },
      });
    } else {
      // Create new item
      await prisma.cartItem.create({
        data: {
          cartId: cart.id,
          productId: data.productId,
          variantId: data.variantId || null,
          quantity: data.quantity,
        },
      });
    }

    // Invalidate cart cache
    await cache.del(`cart:${user.id}`);

    return { success: true };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { error: error.errors[0].message };
    }
    console.error('Add to cart error:', error);
    return { error: 'Failed to add item to cart' };
  }
}

/**
 * Update cart item quantity
 */
export async function updateCartItemQuantity(
  itemId: string,
  quantity: number
) {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      return { error: 'Not authenticated' };
    }

    // Verify item belongs to user
    const cart = await prisma.cart.findUnique({
      where: { userId: user.id },
      include: {
        items: {
          where: { id: itemId },
        },
      },
    });

    if (!cart || cart.items.length === 0) {
      return { error: 'Item not found in cart' };
    }

    const cartItem = cart.items[0];

    // Get product to check stock
    const product = await prisma.product.findUnique({
      where: { id: cartItem.productId },
    });

    if (product?.trackInventory && product.stockQuantity < quantity) {
      return { error: 'Not enough stock available' };
    }

    if (quantity <= 0) {
      // Remove item
      await prisma.cartItem.delete({
        where: { id: itemId },
      });
    } else {
      // Update quantity
      await prisma.cartItem.update({
        where: { id: itemId },
        data: { quantity },
      });
    }

    // Invalidate cart cache
    await cache.del(`cart:${user.id}`);

    return { success: true };
  } catch (error) {
    console.error('Update cart item error:', error);
    return { error: 'Failed to update cart item' };
  }
}

/**
 * Remove item from cart
 */
export async function removeFromCart(itemId: string) {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      return { error: 'Not authenticated' };
    }

    // Verify item belongs to user
    const cart = await prisma.cart.findUnique({
      where: { userId: user.id },
      include: {
        items: {
          where: { id: itemId },
        },
      },
    });

    if (!cart || cart.items.length === 0) {
      return { error: 'Item not found in cart' };
    }

    await prisma.cartItem.delete({
      where: { id: itemId },
    });

    // Invalidate cart cache
    await cache.del(`cart:${user.id}`);

    return { success: true };
  } catch (error) {
    console.error('Remove from cart error:', error);
    return { error: 'Failed to remove item from cart' };
  }
}

/**
 * Clear cart
 */
export async function clearCart() {
  try {
    const user = await getCurrentUser();
    
    if (!user) {
      return { error: 'Not authenticated' };
    }

    await prisma.cartItem.deleteMany({
      where: { cart: { userId: user.id } },
    });

    // Invalidate cart cache
    await cache.del(`cart:${user.id}`);

    return { success: true };
  } catch (error) {
    console.error('Clear cart error:', error);
    return { error: 'Failed to clear cart' };
  }
}

/**
 * Get cart total
 */
export async function getCartTotal() {
  const cart = await getCart();
  
  if (!cart) {
    return { subtotal: 0, itemCount: 0 };
  }

  let subtotal = 0;
  let itemCount = 0;

  for (const item of cart.items) {
    const price = item.variant?.price 
      ? parseFloat(item.variant.price.toString())
      : parseFloat(item.product.price.toString());
    subtotal += price * item.quantity;
    itemCount += item.quantity;
  }

  return { subtotal, itemCount };
}

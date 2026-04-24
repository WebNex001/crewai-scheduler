'use server';

import { redirect } from 'next/navigation';
import { z } from 'zod';
import prisma from '@/lib/db';
import { hashPassword, verifyPassword, generateToken, setAuthCookie, removeAuthCookie } from '@/lib/auth';
import { registerSchema, loginSchema } from '@/lib/validations';

/**
 * Register a new user
 */
export async function registerUser(formData: FormData) {
  try {
    const data = {
      name: formData.get('name') as string,
      email: formData.get('email') as string,
      password: formData.get('password') as string,
      confirmPassword: formData.get('confirmPassword') as string,
    };

    // Validate input
    const validated = registerSchema.extend({
      confirmPassword: z.string(),
    }).parse({
      ...data,
      password: data.password,
    });

    // Check if passwords match
    if (data.password !== data.confirmPassword) {
      return { error: 'Passwords do not match' };
    }

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email: data.email },
    });

    if (existingUser) {
      return { error: 'User with this email already exists' };
    }

    // Hash password
    const hashedPassword = await hashPassword(data.password);

    // Create user
    const user = await prisma.user.create({
      data: {
        email: data.email,
        name: data.name,
        password: hashedPassword,
      },
    });

    // Generate token and set cookie
    const token = generateToken(user.id, user.role);
    setAuthCookie(token);

    return { success: true, userId: user.id };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { error: error.errors[0].message };
    }
    console.error('Registration error:', error);
    return { error: 'An error occurred during registration' };
  }
}

/**
 * Login user
 */
export async function loginUser(formData: FormData) {
  try {
    const data = {
      email: formData.get('email') as string,
      password: formData.get('password') as string,
    };

    // Validate input
    loginSchema.parse(data);

    // Find user
    const user = await prisma.user.findUnique({
      where: { email: data.email },
    });

    if (!user) {
      return { error: 'Invalid email or password' };
    }

    // Verify password
    const isValid = await verifyPassword(data.password, user.password);

    if (!isValid) {
      return { error: 'Invalid email or password' };
    }

    // Generate token and set cookie
    const token = generateToken(user.id, user.role);
    setAuthCookie(token);

    return { success: true, userId: user.id };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { error: error.errors[0].message };
    }
    console.error('Login error:', error);
    return { error: 'An error occurred during login' };
  }
}

/**
 * Logout user
 */
export async function logoutUser() {
  removeAuthCookie();
  redirect('/');
}

/**
 * Update user profile
 */
export async function updateProfile(
  userId: string,
  data: {
    name?: string;
    phone?: string;
    avatar?: string;
  }
) {
  try {
    const user = await prisma.user.update({
      where: { id: userId },
      data,
      select: {
        id: true,
        name: true,
        email: true,
        phone: true,
        avatar: true,
      },
    });

    return { success: true, user };
  } catch (error) {
    console.error('Update profile error:', error);
    return { error: 'Failed to update profile' };
  }
}

/**
 * Change password
 */
export async function changePassword(
  userId: string,
  currentPassword: string,
  newPassword: string
) {
  try {
    // Get user
    const user = await prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      return { error: 'User not found' };
    }

    // Verify current password
    const isValid = await verifyPassword(currentPassword, user.password);

    if (!isValid) {
      return { error: 'Current password is incorrect' };
    }

    // Hash new password
    const hashedPassword = await hashPassword(newPassword);

    // Update password
    await prisma.user.update({
      where: { id: userId },
      data: { password: hashedPassword },
    });

    return { success: true };
  } catch (error) {
    console.error('Change password error:', error);
    return { error: 'Failed to change password' };
  }
}

/**
 * Request password reset
 */
export async function requestPasswordReset(email: string) {
  try {
    const user = await prisma.user.findUnique({
      where: { email },
    });

    // Always return success to prevent email enumeration
    if (!user) {
      return { success: true, message: 'If an account exists, a reset email will be sent' };
    }

    // TODO: Generate reset token and send email
    // For now, just return success
    return { success: true, message: 'Password reset email sent' };
  } catch (error) {
    console.error('Password reset request error:', error);
    return { error: 'Failed to request password reset' };
  }
}

/**
 * NextAuth.js 认证配置
 * 支持邮箱密码登录和 OAuth 第三方登录
 */

import { NextAuthOptions } from 'next-auth';
import { PrismaAdapter } from '@next-auth/prisma-adapter';
import CredentialsProvider from 'next-auth/providers/credentials';
import GoogleProvider from 'next-auth/providers/google';
import GitHubProvider from 'next-auth/providers/github';
import bcrypt from 'bcryptjs';
import prisma from './db';

/**
 * 认证选项配置
 */
export const authOptions: NextAuthOptions = {
  // 使用 Prisma 适配器
  adapter: PrismaAdapter(prisma) as NextAuthOptions['adapter'],

  // 会话配置
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30天
  },

  // JWT 配置
  jwt: {
    maxAge: 30 * 24 * 60 * 60, // 30天
  },

  // 页面配置
  pages: {
    signIn: '/auth/login',
    signOut: '/auth/logout',
    error: '/auth/error',
    verifyRequest: '/auth/verify-request',
    newUser: '/auth/register',
  },

  // 提供商配置
  providers: [
    // 邮箱密码登录
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: '邮箱', type: 'email' },
        password: { label: '密码', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error('请输入邮箱和密码');
        }

        // 查找用户
        const user = await prisma.user.findUnique({
          where: { email: credentials.email },
        });

        if (!user || !user.password) {
          throw new Error('邮箱或密码错误');
        }

        // 验证密码
        const isPasswordValid = await bcrypt.compare(
          credentials.password,
          user.password
        );

        if (!isPasswordValid) {
          throw new Error('邮箱或密码错误');
        }

        // 返回用户信息（不包含密码）
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.image,
          role: user.role,
        };
      },
    }),

    // Google OAuth 登录
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
      ? [
          GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET,
          }),
        ]
      : []),

    // GitHub OAuth 登录
    ...(process.env.GITHUB_ID && process.env.GITHUB_SECRET
      ? [
          GitHubProvider({
            clientId: process.env.GITHUB_ID,
            clientSecret: process.env.GITHUB_SECRET,
          }),
        ]
      : []),
  ],

  // 回调函数
  callbacks: {
    // JWT 回调 - 每次 Token 刷新时调用
    async jwt({ token, user, trigger, session }) {
      if (user) {
        token.id = user.id;
        token.role = (user as { role?: string }).role || 'CUSTOMER';
      }

      // 处理会话更新（如更新用户名）
      if (trigger === 'update' && session) {
        token.name = session.name;
        token.picture = session.image;
      }

      return token;
    },

    // 会话回调 - 每次获取会话时调用
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = token.role as string;
      }
      return session;
    },
  },

  // 事件处理
  events: {
    async signIn({ user, account, profile }) {
      console.log('用户登录:', user.email);
    },
    async signOut({ token }) {
      console.log('用户登出:', token?.id);
    },
    async createUser({ user }) {
      console.log('新用户注册:', user.email);
    },
  },

  // 调试模式
  debug: process.env.NODE_ENV === 'development',
};

/**
 * 获取当前用户 ID
 * 用于在 API 路由中获取登录用户信息
 */
export async function getCurrentUserId(): Promise<string | null> {
  // 注意：这里需要在实际使用中通过 getServerSession 获取
  // 此函数作为类型提示和占位符
  return null;
}

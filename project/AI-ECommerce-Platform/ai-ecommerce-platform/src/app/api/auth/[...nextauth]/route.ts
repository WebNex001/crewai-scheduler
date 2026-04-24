/**
 * NextAuth.js 认证 API 路由
 * 处理用户登录、登出、注册等认证操作
 */

import NextAuth from 'next-auth';
import { authOptions } from '@/lib/auth';

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };

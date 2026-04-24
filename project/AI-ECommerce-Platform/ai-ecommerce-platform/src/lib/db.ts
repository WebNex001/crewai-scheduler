/**
 * Prisma 数据库客户端单例
 * 确保在开发环境中避免 HMR 导致的连接池耗尽问题
 */

import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

// 创建 Prisma 客户端实例
export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['query', 'error', 'warn'] : ['error'],
  });

// 在开发环境中将实例挂载到全局，避免热重载时重复创建
if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

/**
 * 断连数据库连接
 * 用于服务器关闭时的清理
 */
export async function disconnectDatabase() {
  await prisma.$disconnect();
}

export default prisma;

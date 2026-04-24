/**
 * Prisma Client Singleton
 * 
 * This module provides a singleton instance of the Prisma Client
 * to avoid creating multiple connections during development.
 * 
 * In production, this ensures proper connection pooling and
 * avoids exhausting database connections.
 */

import { PrismaClient } from '@prisma/client'

// Define global type for prisma client
declare global {
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined
}

/**
 * Creates a new Prisma Client instance with logging enabled in development
 */
function createPrismaClient(): PrismaClient {
  const client = new PrismaClient({
    log: process.env.NODE_ENV === 'development' 
      ? ['query', 'error', 'warn'] 
      : ['error'],
  })

  return client
}

// Export a singleton instance
export const prisma = globalThis.prisma ?? createPrismaClient()

// In development, cache the client to prevent reconnecting
if (process.env.NODE_ENV !== 'production') {
  globalThis.prisma = prisma
}

/**
 * Disconnect from the database
 * Useful for testing or graceful shutdown
 */
export async function disconnect(): Promise<void> {
  await prisma.$disconnect()
}

/**
 * Connect to the database
 * Useful for testing or when using $disconnect
 */
export async function connect(): Promise<void> {
  await prisma.$connect()
}

export default prisma

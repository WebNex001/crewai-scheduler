import OpenAI from 'openai';
import { cache } from './redis';
import prisma from './db';

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/**
 * Generate AI product summary
 */
export async function generateProductSummary(productDescription: string): Promise<string> {
  const cacheKey = `ai:summary:${Buffer.from(productDescription).toString('base64').slice(0, 32)}`;
  
  // Check cache first
  const cached = await cache.get<string>(cacheKey);
  if (cached) return cached;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are an expert e-commerce copywriter. Create engaging, concise product summaries that highlight key features and benefits.',
        },
        {
          role: 'user',
          content: `Create a compelling 2-3 sentence product summary for: ${productDescription}`,
        },
      ],
      max_tokens: 150,
      temperature: 0.7,
    });

    const summary = response.choices[0]?.message?.content || '';
    
    // Cache for 24 hours
    await cache.set(cacheKey, summary, 86400);
    
    return summary;
  } catch (error) {
    console.error('OpenAI summary generation error:', error);
    return productDescription.slice(0, 200);
  }
}

/**
 * Generate product tags using AI
 */
export async function generateProductTags(productName: string, description: string): Promise<string[]> {
  const cacheKey = `ai:tags:${Buffer.from(productName + description).toString('base64').slice(0, 32)}`;
  
  const cached = await cache.get<string[]>(cacheKey);
  if (cached) return cached;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a product tagging expert. Generate relevant tags for e-commerce products.',
        },
        {
          role: 'user',
          content: `Generate 5-8 relevant search tags for this product. Return only a JSON array of strings.\n\nProduct: ${productName}\nDescription: ${description}`,
        },
      ],
      max_tokens: 100,
      temperature: 0.5,
    });

    const content = response.choices[0]?.message?.content || '';
    const tags = JSON.parse(content) as string[];
    
    await cache.set(cacheKey, tags, 86400);
    
    return tags;
  } catch (error) {
    console.error('OpenAI tags generation error:', error);
    return [];
  }
}

/**
 * Get personalized recommendations based on user behavior
 */
export async function getPersonalizedRecommendations(
  userId: string | null,
  sessionId: string | null,
  viewedProducts: string[] = [],
  purchaseHistory: string[] = []
): Promise<string[]> {
  // Try to get cached recommendations
  const cacheKey = userId 
    ? `ai:recs:user:${userId}` 
    : `ai:recs:session:${sessionId}`;
  
  const cached = await cache.get<string[]>(cacheKey);
  if (cached) return cached;

  try {
    // Get product details for context
    const products = await prisma.product.findMany({
      where: {
        id: { in: [...viewedProducts, ...purchaseHistory] },
        status: 'ACTIVE',
      },
      select: {
        id: true,
        name: true,
        category: { select: { name: true } },
        price: true,
      },
      take: 10,
    });

    const prompt = userId
      ? `Based on user's recently viewed products: ${products.map(p => p.name).join(', ')}, recommend 10 product IDs that the user might like.`
      : `Based on browsing history: ${products.map(p => p.name).join(', ')}, recommend 10 product IDs for similar products.`;

    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a product recommendation engine. Return a JSON array of product IDs that match user preferences.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      max_tokens: 200,
      temperature: 0.7,
    });

    const content = response.choices[0]?.message?.content || '[]';
    const recommendations = JSON.parse(content) as string[];
    
    // Cache for 1 hour
    await cache.set(cacheKey, recommendations, 3600);
    
    // Save to database
    if (userId || sessionId) {
      await prisma.aIRecommendation.create({
        data: {
          userId: userId || undefined,
          sessionId: sessionId || undefined,
          type: 'PERSONALIZED',
          products: JSON.stringify(recommendations),
          context: JSON.stringify({ viewedProducts, purchaseHistory }),
          expiresAt: new Date(Date.now() + 3600000),
        },
      });
    }
    
    return recommendations;
  } catch (error) {
    console.error('OpenAI recommendations error:', error);
    return [];
  }
}

/**
 * Get similar products recommendation
 */
export async function getSimilarProducts(productId: string): Promise<string[]> {
  const cacheKey = `ai:similar:${productId}`;
  
  const cached = await cache.get<string[]>(cacheKey);
  if (cached) return cached;

  try {
    const product = await prisma.product.findUnique({
      where: { id: productId },
      include: { category: true },
    });

    if (!product) return [];

    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a product recommendation engine. Suggest similar products based on category and features.',
        },
        {
          role: 'user',
          content: `Find similar products to: ${product.name}. Category: ${product.category?.name}. Price: $${product.price}. Return a JSON array of similar product names.`,
        },
      ],
      max_tokens: 200,
      temperature: 0.7,
    });

    const content = response.choices[0]?.message?.content || '[]';
    const similarNames = JSON.parse(content) as string[];
    
    // Find matching products in database
    const similarProducts = await prisma.product.findMany({
      where: {
        name: { in: similarNames, mode: 'insensitive' },
        status: 'ACTIVE',
        id: { not: productId },
      },
      select: { id: true },
      take: 10,
    });

    const productIds = similarProducts.map(p => p.id);
    
    await cache.set(cacheKey, productIds, 86400);
    
    return productIds;
  } catch (error) {
    console.error('OpenAI similar products error:', error);
    return [];
  }
}

/**
 * Generate search query improvements
 */
export async function improveSearchQuery(query: string): Promise<string[]> {
  const cacheKey = `ai:search:${Buffer.from(query).toString('base64')}`;
  
  const cached = await cache.get<string[]>(cacheKey);
  if (cached) return cached;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a search optimization assistant. Suggest alternative search terms.',
        },
        {
          role: 'user',
          content: `Suggest 5 alternative search terms for: "${query}". Return a JSON array of strings.`,
        },
      ],
      max_tokens: 200,
      temperature: 0.5,
    });

    const content = response.choices[0]?.message?.content || '[]';
    const suggestions = JSON.parse(content) as string[];
    
    await cache.set(cacheKey, suggestions, 86400);
    
    return suggestions;
  } catch (error) {
    console.error('OpenAI search improvement error:', error);
    return [];
  }
}

/**
 * Analyze review sentiment
 */
export async function analyzeReviewSentiment(reviewText: string): Promise<{
  sentiment: 'positive' | 'neutral' | 'negative';
  keywords: string[];
}> {
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'Analyze the sentiment of customer reviews. Return a JSON object with sentiment (positive/neutral/negative) and key phrases.',
        },
        {
          role: 'user',
          content: `Analyze this review: "${reviewText}". Return JSON: {"sentiment": "positive|neutral|negative", "keywords": ["key", "phrases"]}`,
        },
      ],
      max_tokens: 100,
      temperature: 0.3,
    });

    const content = response.choices[0]?.message?.content || '{}';
    return JSON.parse(content);
  } catch (error) {
    console.error('OpenAI sentiment analysis error:', error);
    return { sentiment: 'neutral', keywords: [] };
  }
}

export default openai;

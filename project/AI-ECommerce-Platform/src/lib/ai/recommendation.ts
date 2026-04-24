/**
 * OpenAI Integration for AI-Powered Recommendations
 * 
 * This module provides AI-powered product recommendations using OpenAI's
 * embeddings and chat completion APIs.
 */

import OpenAI from 'openai'

// Initialize OpenAI client
const openaiApiKey = process.env.OPENAI_API_KEY

export const openai = openaiApiKey
  ? new OpenAI({ apiKey: openaiApiKey })
  : null

/**
 * Generate embeddings for a text using OpenAI's text-embedding-ada-002 model
 * @param text - Text to generate embeddings for
 * @returns Embedding vector or null
 */
export async function generateEmbedding(text: string): Promise<number[] | null> {
  if (!openai) {
    console.warn('OpenAI is not configured')
    return null
  }

  try {
    const response = await openai.embeddings.create({
      model: 'text-embedding-ada-002',
      input: text,
    })

    return response.data[0].embedding
  } catch (error) {
    console.error('Error generating embedding:', error)
    return null
  }
}

/**
 * Generate product embedding from product data
 * @param product - Product object with name, description, category
 * @returns Embedding vector or null
 */
export async function generateProductEmbedding(product: {
  name: string
  description?: string | null
  category?: string
  brand?: string
}): Promise<number[] | null> {
  const text = [
    product.name,
    product.description,
    product.category,
    product.brand,
  ]
    .filter(Boolean)
    .join(' ')

  return generateEmbedding(text)
}

/**
 * Generate user preference embedding from browsing history
 * @param viewedProducts - Array of viewed products
 * @returns Embedding vector or null
 */
export async function generateUserPreferenceEmbedding(
  viewedProducts: Array<{ name: string; category: string; brand?: string }>
): Promise<number[] | null> {
  if (viewedProducts.length === 0) {
    return null
  }

  const text = viewedProducts
    .map(p => `${p.name} ${p.category} ${p.brand || ''}`)
    .join(' | ')

  return generateEmbedding(text)
}

/**
 * Get AI-powered product recommendations based on user preferences
 * @param userId - User ID
 * @param viewedProducts - Array of products user has viewed
 * @param limit - Number of recommendations to return
 * @returns Array of recommended product IDs or null
 */
export async function getPersonalizedRecommendations(
  userId: string,
  viewedProducts: Array<{ id: string; name: string; category: string; brand?: string }>,
  limit: number = 10
): Promise<string[] | null> {
  if (!openai) {
    // Return popular products as fallback when OpenAI is not configured
    return null
  }

  try {
    // Generate preference embedding from browsing history
    const preferenceEmbedding = await generateUserPreferenceEmbedding(viewedProducts)
    
    if (!preferenceEmbedding) {
      return null
    }

    // In a real implementation, we would:
    // 1. Store embeddings in a vector database (e.g., pgvector)
    // 2. Query for similar products using cosine similarity
    // 3. Return top k products excluding already viewed
    
    // For now, we'll generate a recommendation prompt
    const viewedCategories = [...new Set(viewedProducts.map(p => p.category))]
    const viewedBrands = [...new Set(viewedProducts.filter(p => p.brand).map(p => p.brand))]
    
    const systemPrompt = `You are a product recommendation assistant for an e-commerce store. 
Based on the user's browsing history, recommend ${limit} products they might be interested in.
The user has viewed products in categories: ${viewedCategories.join(', ')}.
They have shown interest in brands: ${viewedBrands.length > 0 ? viewedBrands.join(', ') : 'various'}.`

    // This would normally use vector similarity search
    // For demonstration, we return a placeholder
    console.log('Would generate recommendations using embedding:', preferenceEmbedding.slice(0, 5))
    
    return null // Return null to indicate we should use fallback
  } catch (error) {
    console.error('Error generating recommendations:', error)
    return null
  }
}

/**
 * Get AI-powered product description
 * @param productData - Basic product information
 * @returns Generated product description
 */
export async function generateProductDescription(productData: {
  name: string
  category: string
  features?: string[]
  brand?: string
}): Promise<string | null> {
  if (!openai) {
    return null
  }

  try {
    const featuresList = productData.features?.join(', ') || 'premium quality'
    
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a professional product copywriter. Write compelling, SEO-friendly product descriptions.',
        },
        {
          role: 'user',
          content: `Write a product description for:
Name: ${productData.name}
Category: ${productData.category}
Brand: ${productData.brand || 'Generic'}
Features: ${featuresList}

The description should be engaging, highlight benefits, and be around 150-200 words.`,
        },
      ],
      max_tokens: 300,
    })

    return response.choices[0]?.message?.content || null
  } catch (error) {
    console.error('Error generating product description:', error)
    return null
  }
}

/**
 * Get AI-powered review summary
 * @param reviews - Array of product reviews
 * @returns Summary of reviews
 */
export async function generateReviewSummary(reviews: Array<{
  rating: number
  content: string
}>): Promise<{ summary: string; pros: string[]; cons: string[] } | null> {
  if (!openai || reviews.length === 0) {
    return null
  }

  try {
    const reviewsText = reviews
      .map((r, i) => `Review ${i + 1} (${r.rating}/5): ${r.content}`)
      .join('\n\n')

    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a product review analyzer. Summarize customer reviews into a concise overview.',
        },
        {
          role: 'user',
          content: `Analyze these product reviews and provide:
1. A brief summary (2-3 sentences)
2. List of pros (key positive points)
3. List of cons (key negative points)

Reviews:
${reviewsText}`,
        },
      ],
      max_tokens: 500,
    })

    const content = response.choices[0]?.message?.content || ''
    
    // Parse the response (simplified parsing)
    const lines = content.split('\n')
    const summary = lines[0] || ''
    const pros: string[] = []
    const cons: string[] = []
    
    let currentList: 'pros' | 'cons' | null = null
    
    for (const line of lines) {
      if (line.toLowerCase().includes('pros')) {
        currentList = 'pros'
      } else if (line.toLowerCase().includes('cons')) {
        currentList = 'cons'
      } else if (line.trim().startsWith('-') && currentList) {
        const item = line.trim().substring(1).trim()
        if (currentList === 'pros') {
          pros.push(item)
        } else {
          cons.push(item)
        }
      }
    }

    return { summary, pros, cons }
  } catch (error) {
    console.error('Error generating review summary:', error)
    return null
  }
}

/**
 * Generate search query enhancement for better product search
 * @param userQuery - User's search query
 * @returns Enhanced search query
 */
export async function enhanceSearchQuery(userQuery: string): Promise<string | null> {
  if (!openai) {
    return null
  }

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'You are a search query enhancer. Expand user queries with related terms for better e-commerce search results.',
        },
        {
          role: 'user',
          content: `Enhance this search query for an e-commerce product search: "${userQuery}"
          
Add relevant synonyms, related terms, and common variations. Return only the enhanced query.`,
        },
      ],
      max_tokens: 100,
    })

    return response.choices[0]?.message?.content || null
  } catch (error) {
    console.error('Error enhancing search query:', error)
    return null
  }
}

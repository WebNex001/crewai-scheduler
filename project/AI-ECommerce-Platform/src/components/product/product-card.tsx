import Link from 'next/link';
import Image from 'next/image';
import { Star, Heart, ShoppingCart } from 'lucide-react';
import { formatPrice, calculateDiscount } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useCart } from '@/hooks/use-cart';
import { useState } from 'react';

interface ProductCardProps {
  product: {
    id: string;
    name: string;
    slug: string;
    price: number | string;
    comparePrice?: number | string | null;
    images: string[];
    category?: {
      name: string;
      slug: string;
    } | null;
    averageRating?: number;
    reviewCount?: number;
    stockQuantity?: number;
  };
  variant?: 'default' | 'compact' | 'horizontal';
}

/**
 * Product card component for displaying products in grid/list views
 */
export function ProductCard({ product, variant = 'default' }: ProductCardProps) {
  const { addItem } = useCart();
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [isAddingToCart, setIsAddingToCart] = useState(false);

  const price = typeof product.price === 'string' ? parseFloat(product.price) : product.price;
  const comparePrice = product.comparePrice
    ? typeof product.comparePrice === 'string'
      ? parseFloat(product.comparePrice)
      : product.comparePrice
    : null;
  const discount = comparePrice ? calculateDiscount(comparePrice, price) : 0;
  const image = product.images[0] || '/placeholder.jpg';
  const isOutOfStock = (product.stockQuantity || 0) <= 0;

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setIsAddingToCart(true);
    
    addItem({
      productId: product.id,
      productName: product.name,
      productImage: image,
      price,
      quantity: 1,
    });
    
    setTimeout(() => setIsAddingToCart(false), 500);
  };

  const handleToggleWishlist = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsWishlisted(!isWishlisted);
  };

  if (variant === 'horizontal') {
    return (
      <Link href={`/products/${product.slug}`}>
        <div className="flex gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50">
          <div className="relative h-24 w-24 flex-shrink-0 overflow-hidden rounded-md">
            <Image
              src={image}
              alt={product.name}
              fill
              className="object-cover"
            />
          </div>
          <div className="flex flex-1 flex-col justify-between">
            <div>
              <h3 className="font-semibold line-clamp-1">{product.name}</h3>
              {product.category && (
                <p className="text-sm text-muted-foreground">{product.category.name}</p>
              )}
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold">{formatPrice(price)}</span>
                {comparePrice && (
                  <span className="text-sm text-muted-foreground line-through">
                    {formatPrice(comparePrice)}
                  </span>
                )}
              </div>
              <Button size="sm" onClick={handleAddToCart} disabled={isOutOfStock}>
                <ShoppingCart className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </Link>
    );
  }

  if (variant === 'compact') {
    return (
      <Link href={`/products/${product.slug}`}>
        <div className="flex gap-3">
          <div className="relative h-16 w-16 flex-shrink-0 overflow-hidden rounded-md">
            <Image
              src={image}
              alt={product.name}
              fill
              className="object-cover"
            />
          </div>
          <div className="flex flex-1 flex-col justify-center">
            <h3 className="text-sm font-medium line-clamp-1">{product.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-semibold">{formatPrice(price)}</span>
              {product.averageRating !== undefined && product.averageRating > 0 && (
                <div className="flex items-center gap-1">
                  <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                  <span className="text-xs">{product.averageRating.toFixed(1)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </Link>
    );
  }

  // Default variant
  return (
    <Link href={`/products/${product.slug}`}>
      <div className="group relative overflow-hidden rounded-lg border bg-card transition-all hover:shadow-lg">
        {/* Image */}
        <div className="relative aspect-square overflow-hidden bg-muted">
          <Image
            src={image}
            alt={product.name}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
          />
          
          {/* Badges */}
          <div className="absolute left-2 top-2 flex flex-col gap-1">
            {discount > 0 && (
              <Badge variant="destructive" className="text-xs">
                -{discount}%
              </Badge>
            )}
            {product.stockQuantity !== undefined && product.stockQuantity <= 5 && product.stockQuantity > 0 && (
              <Badge variant="warning" className="text-xs bg-orange-500">
                Low Stock
              </Badge>
            )}
          </div>

          {/* Wishlist button */}
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-2 h-8 w-8 rounded-full bg-background/80 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={handleToggleWishlist}
          >
            <Heart
              className={`h-4 w-4 ${isWishlisted ? 'fill-red-500 text-red-500' : ''}`}
            />
          </Button>

          {/* Quick add to cart */}
          <div className="absolute bottom-2 left-2 right-2 opacity-0 transition-opacity group-hover:opacity-100">
            <Button
              className="w-full"
              size="sm"
              onClick={handleAddToCart}
              disabled={isOutOfStock || isAddingToCart}
            >
              <ShoppingCart className="mr-2 h-4 w-4" />
              {isOutOfStock ? 'Out of Stock' : isAddingToCart ? 'Added!' : 'Add to Cart'}
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          {product.category && (
            <p className="text-xs text-muted-foreground">{product.category.name}</p>
          )}
          <h3 className="mt-1 line-clamp-2 font-medium">{product.name}</h3>
          
          {/* Rating */}
          {product.averageRating !== undefined && product.averageRating > 0 && (
            <div className="mt-2 flex items-center gap-1">
              <div className="flex">
                {[1, 2, 3, 4, 5].map((star) => (
                  <Star
                    key={star}
                    className={`h-3 w-3 ${
                      star <= Math.round(product.averageRating!)
                        ? 'fill-yellow-400 text-yellow-400'
                        : 'text-muted'
                    }`}
                  />
                ))}
              </div>
              <span className="text-xs text-muted-foreground">
                ({product.reviewCount || 0})
              </span>
            </div>
          )}

          {/* Price */}
          <div className="mt-2 flex items-center gap-2">
            <span className="text-lg font-bold">{formatPrice(price)}</span>
            {comparePrice && (
              <span className="text-sm text-muted-foreground line-through">
                {formatPrice(comparePrice)}
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

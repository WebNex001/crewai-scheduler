/**
 * 全局类型定义
 */

// ============================================
// 用户相关类型
// ============================================

export interface User {
  id: string;
  email: string;
  name?: string | null;
  image?: string | null;
  phone?: string | null;
  role: 'CUSTOMER' | 'ADMIN' | 'MANAGER';
  emailVerified?: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface Address {
  id: string;
  userId: string;
  label: string;
  recipient: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  isDefault: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// ============================================
// 商品相关类型
// ============================================

export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  parentId?: string | null;
  image?: string | null;
  sortOrder: number;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
  children?: Category[];
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  price: number;
  originalPrice?: number | null;
  stock: number;
  images: string[];
  categoryId: string;
  category?: Category;
  brand?: string | null;
  tags: string[];
  isActive: boolean;
  isFeatured: boolean;
  views: number;
  sales: number;
  rating: number;
  reviewCount: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface ProductListItem extends Product {
  category?: {
    id: string;
    name: string;
    slug: string;
  };
}

// ============================================
// 购物车相关类型
// ============================================

export interface CartItem {
  id: string;
  cartId: string;
  productId: string;
  product?: Product;
  quantity: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface Cart {
  id: string;
  userId: string;
  items: CartItem[];
  createdAt: Date;
  updatedAt: Date;
  totalItems: number;
  subtotal: number;
}

// ============================================
// 订单相关类型
// ============================================

export interface Order {
  id: string;
  orderNumber: string;
  userId: string;
  status: OrderStatus;
  paymentStatus: PaymentStatus;
  paymentMethod?: string | null;
  paymentId?: string | null;
  subtotal: number;
  shippingFee: number;
  discount: number;
  total: number;
  currency: string;
  recipient: string;
  phone: string;
  shippingAddress: string;
  note?: string | null;
  paidAt?: Date | null;
  shippedAt?: Date | null;
  deliveredAt?: Date | null;
  createdAt: Date;
  updatedAt: Date;
  items?: OrderItem[];
}

export interface OrderItem {
  id: string;
  orderId: string;
  productId: string;
  productName: string;
  productImage?: string | null;
  price: number;
  quantity: number;
  subtotal: number;
  product?: Product;
}

export type OrderStatus =
  | 'PENDING'
  | 'PAID'
  | 'PROCESSING'
  | 'SHIPPED'
  | 'DELIVERED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'REFUNDED';

export type PaymentStatus = 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED' | 'PARTIALLY_REFUNDED';

// ============================================
// 评价相关类型
// ============================================

export interface Review {
  id: string;
  userId: string;
  user?: User;
  productId: string;
  product?: Product;
  orderId?: string | null;
  rating: number;
  title?: string | null;
  content?: string | null;
  images: string[];
  isVerified: boolean;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'SPAM';
  createdAt: Date;
  updatedAt: Date;
}

// ============================================
// 优惠券相关类型
// ============================================

export interface Coupon {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  type: 'FIXED' | 'PERCENTAGE' | 'SHIPPING';
  value: number;
  minAmount?: number | null;
  maxDiscount?: number | null;
  usageLimit?: number | null;
  usageCount: number;
  userUsageLimit: number;
  productIds: string[];
  categoryIds: string[];
  startsAt: Date;
  expiresAt: Date;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// ============================================
// AI 推荐相关类型
// ============================================

export interface Recommendation {
  id: string;
  userId: string;
  productId: string;
  product?: Product;
  type: RecommendationType;
  score: number;
  reason?: string | null;
  createdAt: Date;
  expiresAt: Date;
}

export type RecommendationType =
  | 'PERSONALIZED'
  | 'SIMILAR'
  | 'FREQUENTLY_BOUGHT'
  | 'TRENDING'
  | 'NEW_ARRIVALS'
  | 'RECENTLY_VIEWED';

// ============================================
// 通知相关类型
// ============================================

export interface Notification {
  id: string;
  userId: string;
  type: NotificationType;
  title: string;
  content: string;
  data?: Record<string, unknown>;
  isRead: boolean;
  createdAt: Date;
}

export type NotificationType =
  | 'ORDER_STATUS'
  | 'PAYMENT'
  | 'SHIPPING'
  | 'REVIEW'
  | 'COUPON'
  | 'SYSTEM'
  | 'RECOMMENDATION';

// ============================================
// API 响应类型
// ============================================

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
    hasNextPage: boolean;
    hasPrevPage: boolean;
  };
}

// ============================================
// 表单数据类型
// ============================================

export interface LoginFormData {
  email: string;
  password: string;
}

export interface RegisterFormData {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface AddressFormData {
  label: string;
  recipient: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  isDefault: boolean;
}

export interface ProductFormData {
  name: string;
  description?: string;
  price: number;
  originalPrice?: number;
  stock: number;
  categoryId: string;
  brand?: string;
  tags: string[];
  images: string[];
}

// ============================================
// 统计数据类型
// ============================================

export interface DashboardStats {
  totalRevenue: number;
  totalOrders: number;
  totalUsers: number;
  totalProducts: number;
  revenueGrowth: number;
  ordersGrowth: number;
  usersGrowth: number;
  productsGrowth: number;
}

export interface SalesData {
  date: string;
  revenue: number;
  orders: number;
}

export interface CategorySales {
  categoryId: string;
  categoryName: string;
  sales: number;
  percentage: number;
}

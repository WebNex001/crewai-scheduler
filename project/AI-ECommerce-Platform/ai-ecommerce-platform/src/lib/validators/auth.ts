/**
 * 数据验证 Schema
 * 使用 Zod 进行运行时类型验证
 */

import { z } from 'zod';

// ============================================
// 用户相关验证
// ============================================

/**
 * 用户登录验证
 */
export const loginSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(6, '密码至少6位'),
});

/**
 * 用户注册验证
 */
export const registerSchema = z
  .object({
    name: z.string().min(2, '用户名至少2位').max(50, '用户名最多50位'),
    email: z.string().email('请输入有效的邮箱地址'),
    password: z.string().min(6, '密码至少6位').max(100, '密码最多100位'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '两次密码输入不一致',
    path: ['confirmPassword'],
  });

/**
 * 更新用户资料验证
 */
export const updateProfileSchema = z.object({
  name: z.string().min(2).max(50).optional(),
  phone: z.string().regex(/^1[3-9]\d{9}$/, '请输入有效的手机号').optional(),
  image: z.string().url().optional(),
});

// ============================================
// 地址相关验证
// ============================================

/**
 * 地址创建/更新验证
 */
export const addressSchema = z.object({
  label: z.string().min(1, '请输入地址标签').max(20, '标签最多20位'),
  recipient: z.string().min(2, '请输入收货人姓名').max(50),
  phone: z.string().regex(/^1[3-9]\d{9}$/, '请输入有效的手机号'),
  province: z.string().min(1, '请选择省份'),
  city: z.string().min(1, '请选择城市'),
  district: z.string().min(1, '请选择区县'),
  detail: z.string().min(5, '请输入详细地址').max(200),
  isDefault: z.boolean().default(false),
});

// ============================================
// 商品相关验证
// ============================================

/**
 * 商品列表查询验证
 */
export const productListQuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(50).default(20),
  category: z.string().optional(),
  search: z.string().optional(),
  minPrice: z.coerce.number().optional(),
  maxPrice: z.coerce.number().optional(),
  brand: z.string().optional(),
  tags: z.string().optional(),
  sort: z
    .enum(['newest', 'price-asc', 'price-desc', 'sales', 'rating'])
    .default('newest'),
  isFeatured: z.coerce.boolean().optional(),
});

/**
 * 商品创建验证
 */
export const productCreateSchema = z.object({
  name: z.string().min(2, '商品名称至少2位').max(200),
  description: z.string().optional(),
  price: z.number().positive('价格必须大于0'),
  originalPrice: z.number().positive().optional(),
  stock: z.number().int().min(0, '库存不能为负数'),
  categoryId: z.string().min(1, '请选择分类'),
  brand: z.string().optional(),
  tags: z.array(z.string()).optional(),
  images: z.array(z.string().url()).min(1, '请至少上传一张图片'),
  isFeatured: z.boolean().default(false),
});

// ============================================
// 购物车相关验证
// ============================================

/**
 * 添加购物车验证
 */
export const addToCartSchema = z.object({
  productId: z.string().min(1, '商品ID不能为空'),
  quantity: z.number().int().min(1, '数量至少为1').max(99, '数量最多99'),
});

/**
 * 更新购物车数量验证
 */
export const updateCartItemSchema = z.object({
  quantity: z.number().int().min(1).max(99),
});

// ============================================
// 订单相关验证
// ============================================

/**
 * 创建订单验证
 */
export const createOrderSchema = z.object({
  addressId: z.string().min(1, '请选择收货地址'),
  paymentMethod: z.enum(['stripe', 'alipay', 'wechat']),
  couponCode: z.string().optional(),
  note: z.string().max(500).optional(),
});

/**
 * 订单列表查询验证
 */
export const orderListQuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(50).default(10),
  status: z
    .enum([
      'PENDING',
      'PAID',
      'PROCESSING',
      'SHIPPED',
      'DELIVERED',
      'COMPLETED',
      'CANCELLED',
      'REFUNDED',
    ])
    .optional(),
});

// ============================================
// 评价相关验证
// ============================================

/**
 * 创建评价验证
 */
export const createReviewSchema = z.object({
  productId: z.string().min(1, '商品ID不能为空'),
  orderId: z.string().optional(),
  rating: z.number().int().min(1).max(5, '评分1-5分'),
  title: z.string().max(100).optional(),
  content: z.string().max(2000).optional(),
  images: z.array(z.string().url()).optional(),
});

// ============================================
// 优惠券相关验证
// ============================================

/**
 * 验证优惠券
 */
export const validateCouponSchema = z.object({
  code: z.string().min(1, '请输入优惠券码'),
  orderAmount: z.number().positive('订单金额必须大于0'),
});

// ============================================
// 分类相关验证
// ============================================

/**
 * 分类创建/更新验证
 */
export const categorySchema = z.object({
  name: z.string().min(1, '分类名称不能为空').max(50),
  description: z.string().max(500).optional(),
  parentId: z.string().optional(),
  image: z.string().url().optional(),
  sortOrder: z.number().int().default(0),
  isActive: z.boolean().default(true),
});

// ============================================
// 导出类型
// ============================================

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type UpdateProfileInput = z.infer<typeof updateProfileSchema>;
export type AddressInput = z.infer<typeof addressSchema>;
export type ProductListQuery = z.infer<typeof productListQuerySchema>;
export type ProductCreateInput = z.infer<typeof productCreateSchema>;
export type AddToCartInput = z.infer<typeof addToCartSchema>;
export type UpdateCartItemInput = z.infer<typeof updateCartItemSchema>;
export type CreateOrderInput = z.infer<typeof createOrderSchema>;
export type OrderListQuery = z.infer<typeof orderListQuerySchema>;
export type CreateReviewInput = z.infer<typeof createReviewSchema>;
export type ValidateCouponInput = z.infer<typeof validateCouponSchema>;
export type CategoryInput = z.infer<typeof categorySchema>;

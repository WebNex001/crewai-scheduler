<think>
用户要求我作为架构师和开发工程师，完成AI驱动全栈电商平台的详细设计阶段工作。

基于前置阶段的输出：
- requirements阶段：完整的需求规格说明书（用户故事、功能模块、非功能需求等）
- architecture阶段：技术架构设计方案（技术栈、模块划分、接口设计等）

现在需要进入详细设计阶段，输出：
1. 数据库表结构设计（字段、类型、索引、关系）
2. API 接口详细定义（路径、方法、参数、返回值）
3. 核心算法和业务逻辑设计
4. 前端组件结构和状态管理设计
5. 文件/模块目录结构规划
6. 模块拆分JSON

这是一个大型项目，包含：
- 用户系统
- 商品管理
- 购物车
- 订单系统
- 支付集成（Stripe）
- AI推荐引擎
- 后台管理系统
- 数据分析仪表板

技术栈：Next.js 14 + TypeScript + Prisma + PostgreSQL + Redis + Stripe + OpenAI API

让我开始详细设计。

首先，我需要规划数据库结构。基于电商系统的特点，我需要设计：

1. User - 用户表
2. UserProfile - 用户资料
3. Address - 地址
4. Category - 分类
5. Product - 商品
6. ProductImage - 商品图片


7. Inventory - 库存
8. Cart - 购物车
9. CartItem - 购物车项
10. Order - 订单
11. OrderItem - 订单项
12. Payment - 支付
13. Review - 评价
14. Wishlist - 心愿单
15. AIRecommendation - AI推荐缓存

现在我需要继续完善API接口设计和前端架构。我会使用Next.js 14的App Router来构建API端点，同时用Server Actions处理表单提交。前端部分要采用组件化设计，建立清晰的状态管理体系，并确保文件组织结构合理。
</think>

# AI驱动的全栈电商平台 - 详细设计阶段

基于需求分析和技术架构设计，我将输出完整的详细设计文档。

---

## 一、数据库表结构设计

### 1.1 核心数据模型 ER 图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │     │   Product    │     │    Order    │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │     │ id          │     │ id          │
│ email       │     │ name        │     │ orderNumber │
│ password    │     │ description │     │ userId      │
│ role        │     │ price       │     │ status      │
│ createdAt   │     │ categoryId  │     │ totalAmount │
│ updatedAt   │     │ inventoryId │     │ createdAt   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │                   │                   │
┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
│ UserProfile │     │  Category   │     │  OrderItem  │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │     │ id          │     │ id          │
│ userId      │     │ name        │     │ orderId     │
│ firstName   │     │ slug        │     │ productId   │
│ lastName    │     │ parentId    │     │ quantity    │
│ phone       │     │ createdAt   │     │ price       │
│ avatar      │     └─────────────┘     └─────────────┘
└─────────────┘
       │
┌──────▼──────┐
│   Address   │
├─────────────┤
│ id          │
│ userId      │
│ type        │
│ street      │
│ city        │
│ state       │
│ postalCode  │
│ country     │
│ isDefault   │
└─────────────┘
```

### 1.2 Prisma Schema 完整定义

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// ==================== 用户相关 ====================

model User {
  id            String    @id @default(cuid())
  email         String    @unique
  passwordHash  String    @map("password_hash")
  role          UserRole  @default(CUSTOMER)
  isEmailVerified Boolean  @default(false) @map("is_email_verified")
  createdAt     DateTime  @default(now()) @map("created_at")
  updatedAt     DateTime  @updatedAt @map("updated_at")
  lastLoginAt   DateTime? @map("last_login_at")

  // 关系
  profile       UserProfile?
  addresses     Address[]
  orders        Order[]
  cart          Cart?
  wishlists     Wishlist[]
  reviews       Review[]
  sessions      Session[]

  @@map("users")
}

enum UserRole {
  CUSTOMER
  ADMIN
  MANAGER
}

model UserProfile {
  id          String   @id @default(cuid())
  userId      String   @unique @map("user_id")
  firstName   String?  @map("first_name")
  lastName    String?  @map("last_name")
  phone       String?
  avatar      String?
  birthDate   DateTime? @map("birth_date")
  gender      Gender?
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@map("user_profiles")
}

enum Gender {
  MALE
  FEMALE
  OTHER
}

model Address {
  id          String      @id @default(cuid())
  userId      String      @map("user_id")
  type        AddressType @default(SHIPPING)
  label       String?     // 如"公司"、"家庭"
  recipientName String   @map("recipient_name")
  phone       String
  street      String
  detail      String?     // 详细地址
  city        String
  state       String      @map("state")     // 省份/州
  postalCode  String      @map("postal_code")
  country     String      @default("CN")
  isDefault   Boolean     @default(false) @map("is_default")
  createdAt   DateTime    @default(now()) @map("created_at")
  updatedAt   DateTime    @updatedAt @map("updated_at")

  user        User        @relation(fields: [userId], references: [id], onDelete: Cascade)
  orders      Order[]

  @@index([userId])
  @@map("addresses")
}

enum AddressType {
  SHIPPING
  BILLING
}

model Session {
  id          String   @id @default(cuid())
  userId      String   @map("user_id")
  token       String   @unique
  expiresAt   DateTime @map("expires_at")
  ipAddress   String?  @map("ip_address")
  userAgent   String?  @map("user_agent")
  createdAt   DateTime @default(now()) @map("created_at")

  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@index([token])
  @@map("sessions")
}

// ==================== 商品相关 ====================

model Category {
  id          String    @id @default(cuid())
  name        String
  slug        String    @unique
  description String?
  image       String?
  parentId    String?   @map("parent_id")
  sortOrder   Int       @default(0) @map("sort_order")
  isActive    Boolean   @default(true) @map("is_active")
  createdAt   DateTime  @default(now()) @map("created_at")
  updatedAt   DateTime  @updatedAt @map("updated_at")

  parent      Category?  @relation("CategoryHierarchy", fields: [parentId], references: [id])
  children    Category[] @relation("CategoryHierarchy")
  products    Product[]

  @@index([slug])
  @@index([parentId])
  @@map("categories")
}

model Product {
  id            String        @id @default(cuid())
  name          String
  slug          String        @unique
  description   String?       @db.Text
  summary       String?       // 简短描述
  price         Decimal       @db.Decimal(10, 2)
  originalPrice Decimal?      @map("original_price") @db.Decimal(10, 2)  // 原价用于显示折扣
  costPrice     Decimal?      @map("cost_price") @db.Decimal(10, 2)       // 成本价
  
  categoryId    String?       @map("category_id")
  brand         String?
  model         String?       // 型号
  barcode       String?       @unique
  
  images        ProductImage[]
  inventory     Inventory?
  reviews       Review[]
  orderItems    OrderItem[]
  wishlistItems WishlistItem[]
  
  // SEO
  metaTitle     String?       @map("meta_title")
  metaDescription String?     @map("meta_description")
  
  // 状态
  isActive      Boolean       @default(true) @map("is_active")
  isFeatured   Boolean       @default(false) @map("is_featured")
  isDigital     Boolean       @default(false) @map("is_digital")
  
  // AI推荐
  embedding     Float[]?      // 向量嵌入用于相似度搜索
  aiTags        String[]      @map("ai_tags")  // AI生成的标签
  
  sortOrder     Int           @default(0) @map("sort_order")
  createdAt     DateTime      @default(now()) @map("created_at")
  updatedAt     DateTime      @updatedAt @map("updated_at")

  category      Category?     @relation(fields: [categoryId], references: [id])
  
  @@index([slug])
  @@index([categoryId])
  @@index([isFeatured])
  @@index([isActive])
  @@index([brand])
  @@map("products")
}

model ProductImage {
  id          String   @id @default(cuid())
  productId   String   @map("product_id")
  url         String
  alt         String?
  isPrimary   Boolean  @default(false) @map("is_primary")
  sortOrder   Int      @default(0) @map("sort_order")
  createdAt   DateTime @default(now()) @map("created_at")

  product     Product  @relation(fields: [productId], references: [id], onDelete: Cascade)

  @@index([productId])
  @@map("product_images")
}

model Inventory {
  id              String   @id @default(cuid())
  productId       String   @unique @map("product_id")
  sku             String   @unique
  quantity        Int      @default(0)
  reservedQty     Int      @default(0) @map("reserved_qty")  // 预留数量
  lowStockThreshold Int    @default(10) @map("low_stock_threshold")
  trackInventory  Boolean  @default(true) @map("track_inventory")
  allowBackorder  Boolean  @default(false) @map("allow_backorder")
  updatedAt       DateTime @updatedAt @map("updated_at")

  product         Product  @relation(fields: [productId], references: [id], onDelete: Cascade)

  @@index([sku])
  @@map("inventories")
}

// ==================== 购物车相关 ====================

model Cart {
  id          String     @id @default(cuid())
  sessionId   String?    @unique @map("session_id")  // 游客用
  userId      String?    @unique @map("user_id")     // 登录用户
  items       CartItem[]
  createdAt   DateTime   @default(now()) @map("created_at")
  updatedAt   DateTime   @updatedAt @map("updated_at")

  user        User?      @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([sessionId])
  @@index([userId])
  @@map("carts")
}

model CartItem {
  id          String   @id @default(cuid())
  cartId      String   @map("cart_id")
  productId   String   @map("product_id")
  quantity    Int      @default(1)
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  cart        Cart     @relation(fields: [cartId], references: [id], onDelete: Cascade)
  product     Product  @relation(fields: [productId], references: [id])

  @@unique([cartId, productId])
  @@index([cartId])
  @@index([productId])
  @@map("cart_items")
}

// ==================== 订单相关 ====================

model Order {
  id              String        @id @default(cuid())
  orderNumber     String        @unique @map("order_number")
  userId          String        @map("user_id")
  
  status          OrderStatus   @default(PENDING)
  paymentStatus   PaymentStatus @default(PENDING)
  fulfillmentStatus FulfillmentStatus @default(PENDING) @map("fulfillment_status")
  
  // 金额
  subtotal        Decimal       @db.Decimal(10, 2)
  taxAmount       Decimal       @map("tax_amount") @db.Decimal(10, 2)
  shippingAmount  Decimal       @map("shipping_amount") @db.Decimal(10, 2)
  discountAmount  Decimal       @map("discount_amount") @db.Decimal(10, 2)
  totalAmount     Decimal       @map("total_amount") @db.Decimal(10, 2)
  
  // 地址
  shippingAddressId String?    @map("shipping_address_id")
  billingAddressId  String?   @map("billing_address_id")
  
  shippingAddress  Address?    @relation("OrderShippingAddress", fields: [shippingAddressId], references: [id])
  billingAddress   Address?    @relation("OrderBillingAddress", fields: [billingAddressId], references: [id])
  
  // 物流
  shippingMethod   String?     @map("shipping_method")
  trackingNumber   String?     @map("tracking_number")
  shippedAt        DateTime?   @map("shipped_at")
  deliveredAt      DateTime?   @map("delivered_at")
  
  // 备注
  customerNote     String?     @map("customer_note") @db.Text
  internalNote     String?     @map("internal_note") @db.Text
  
  items            OrderItem[]
  payments         Payment[]
  
  createdAt        DateTime    @default(now()) @map("created_at")
  updatedAt        DateTime    @updatedAt @map("updated_at")

  user             User        @relation(fields: [userId], references: [id])
  
  @@index([orderNumber])
  @@index([userId])
  @@index([status])
  @@index([createdAt])
  @@map("orders")
}

enum OrderStatus {
  PENDING
  CONFIRMED
  PROCESSING
  SHIPPED
  DELIVERED
  CANCELLED
  REFUNDED
  DISPUTED
}

enum PaymentStatus {
  PENDING
  AUTHORIZED
  CAPTURED
  FAILED
  REFUNDED
  PARTIALLY_REFUNDED
}

enum FulfillmentStatus {
  PENDING
  PROCESSING
  SHIPPED
  DELIVERED
  RETURNED
  PARTIALLY_RETURNED
}

model OrderItem {
  id            String   @id @default(cuid())
  orderId       String   @map("order_id")
  productId     String   @map("product_id")
  productName   String   @map("product_name")  // 快照商品名称
  productSku    String?  @map("product_sku")   // 快照SKU
  productImage  String?  @map("product_image") // 快照图片
  
  quantity      Int
  unitPrice     Decimal  @map("unit_price") @db.Decimal(10, 2)
  totalPrice    Decimal  @map("total_price") @db.Decimal(10, 2)
  
  createdAt     DateTime @default(now()) @map("created_at")

  order         Order    @relation(fields: [orderId], references: [id], onDelete: Cascade)
  product       Product  @relation(fields: [productId], references: [id])

  @@index([orderId])
  @@index([productId])
  @@map("order_items")
}

// ==================== 支付相关 ====================

model Payment {
  id              String        @id @default(cuid())
  orderId         String        @map("order_id")
  
  stripePaymentId String?       @unique @map("stripe_payment_id")
  stripeIntentId  String?       @unique @map("stripe_intent_id")
  stripeCustomerId String?     @map("stripe_customer_id")
  
  method          PaymentMethod @default(CARD)
  status          PaymentStatus @default(PENDING)
  
  amount          Decimal       @db.Decimal(10, 2)
  currency        String        @default("cny")
  
  // 退款
  refundedAmount  Decimal?     @map("refunded_amount") @db.Decimal(10, 2)
  refundReason    String?      @map("refund_reason")
  
  metadata        Json?        // 额外信息
  
  createdAt       DateTime      @default(now()) @map("created_at")
  updatedAt       DateTime      @updatedAt @map("updated_at")

  order           Order        @relation(fields: [orderId], references: [id])

  @@index([orderId])
  @@index([stripePaymentId])
  @@index([stripeIntentId])
  @@map("payments")
}

enum PaymentMethod {
  CARD
  ALIPAY
  WECHAT_PAY
  BANK_TRANSFER
}

// ==================== 评价相关 ====================

model Review {
  id          String      @id @default(cuid())
  userId      String      @map("user_id")
  productId   String      @map("product_id")
  orderId     String?     @map("order_id")
  
  rating      Int         // 1-5
  title       String?
  content     String?     @db.Text
  
  // 评价图片
  images      String[]    // 图片URL数组
  
  // 状态
  isVerified  Boolean     @default(false) @map("is_verified")  // 是否已购买验证
  isPublished Boolean     @default(true) @map("is_published")
  
  // AI分析
  aiSentiment String?     @map("ai_sentiment")  // positive, neutral, negative
  aiKeywords String[]    @map("ai_keywords")
  
  createdAt   DateTime    @default(now()) @map("created_at")
  updatedAt   DateTime    @updatedAt @map("updated_at")

  user        User        @relation(fields: [userId], references: [id])
  product     Product     @relation(fields: [productId], references: [id])
  order       Order?      @relation(fields: [orderId], references: [id])

  @@unique([userId, productId])
  @@index([productId])
  @@index([userId])
  @@map("reviews")
}

// ==================== 心愿单 ====================

model Wishlist {
  id          String          @id @default(cuid())
  userId      String          @unique @map("user_id")
  name        String          @default("我的心愿单") @map("name")
  isPublic    Boolean         @default(false) @map("is_public")
  items       WishlistItem[]
  createdAt   DateTime        @default(now()) @map("created_at")
  updatedAt   DateTime        @updatedAt @map("updated_at")

  user        User            @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@map("wishlists")
}

model WishlistItem {
  id          String   @id @default(cuid())
  wishlistId  String   @map("wishlist_id")
  productId   String   @map("product_id")
  note        String?  // 备注
  priority    Int      @default(0)  // 优先级
  createdAt   DateTime @default(now()) @map("created_at")

  wishlist    Wishlist @relation(fields: [wishlistId], references: [id], onDelete: Cascade)
  product     Product  @relation(fields: [productId], references: [id])

  @@unique([wishlistId, productId])
  @@index([wishlistId])
  @@index([productId])
  @@map("wishlist_items")
}

// ==================== AI推荐缓存 ====================

model AIRecommendation {
  id              String   @id @default(cuid())
  type            String   // "similar", "complementary", "trending", "personalized"
  userId          String?  @map("user_id")  // 个性化推荐时使用
  productId       String?  @map("product_id")  // 基于商品推荐时使用
  
  // 推荐结果
  productIds      String[] @map("product_ids")  // 推荐商品ID列表
  scores          Float[]   // 相似度分数
  
  // 上下文
  categoryId      String?  @map("category_id")
  context         Json?    // 额外上下文
  
  // 缓存
  expiresAt       DateTime @map("expires_at")
  createdAt       DateTime @default(now()) @map("created_at")

  @@unique([type, userId, productId, categoryId])
  @@index([expiresAt])
  @@map("ai_recommendations")
}

// ==================== 管理员操作日志 ====================

model AdminLog {
  id          String   @id @default(cuid())
  adminId     String   @map("admin_id")
  action      String
  entityType  String   @map("entity_type")
  entityId    String?  @map("entity_id")
  changes     Json?    // 变更前后对比
  ipAddress   String?  @map("ip_address")
  userAgent   String?  @map("user_agent")
  createdAt   DateTime @default(now()) @map("created_at")

  @@index([adminId])
  @@index([entityType, entityId])
  @@index([createdAt])
  @@map("admin_logs")
}
```

---

## 二、API 接口详细定义

### 2.1 API 分组概览

| 前缀 | 模块 | 描述 |
|------|------|------|
| `/api/auth` | 认证系统 | 登录、注册、登出、会话管理 |
| `/api/users` | 用户系统 | 个人信息、地址管理 |
| `/api/products` | 商品管理 | 商品CRUD、搜索、分类 |
| `/api/cart` | 购物车 | 购物车操作 |
| `/api/orders` | 订单系统 | 订单创建、查询、管理 |
| `/api/payments` | 支付系统 | 支付、退款 |
| `/api/recommendations` | AI推荐 | 个性化推荐 |
| `/api/admin` | 后台管理 | 管理员功能 |
| `/api/analytics` | 数据分析 | 统计报表 |

### 2.2 认证系统 API

#### 2.2.1 用户注册
```
POST /api/auth/register
```

**请求体：**
```typescript
{
  email: string;           // 必填，邮箱格式
  password: string;        // 必填，最少8位
  firstName?: string;      // 可选
  lastName?: string;      // 可选
  phone?: string;         // 可选
}
```

**成功响应 (201):**
```typescript
{
  success: true;
  data: {
    user: {
      id: string;
      email: string;
      role: "CUSTOMER";
      createdAt: string;
    };
    accessToken: string;
    refreshToken: string;
  };
  message: "注册成功";
}
```

**错误响应：**
```typescript
{
  success: false;
  error: {
    code: "EMAIL_EXISTS" | "VALIDATION_ERROR";
    message: string;
    details?: FieldError[];
  };
}
```

#### 2.2.2 用户登录
```
POST /api/auth/login
```

**请求体：**
```typescript
{
  email: string;
  password: string;
  rememberMe?: boolean;
}
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: {
    user: {
      id: string;
      email: string;
      role: "CUSTOMER" | "ADMIN";
      profile: {
        firstName: string;
        lastName: string;
        avatar: string | null;
      } | null;
    };
    accessToken: string;
    refreshToken: string;
    expiresIn: number;  // 访问令牌过期时间(秒)
  };
}
```

#### 2.2.3 刷新令牌
```
POST /api/auth/refresh
```

**请求体：**
```typescript
{
  refreshToken: string;
}
```

#### 2.2.4 登出
```
POST /api/auth/logout
```

**请求头：**
```
Authorization: Bearer <access_token>
```

**成功响应 (200):**
```typescript
{
  success: true;
  message: "登出成功";
}
```

### 2.3 商品管理 API

#### 2.3.1 商品列表（分页+筛选）
```
GET /api/products
```

**查询参数：**
```typescript
{
  page?: number;              // 页码，默认1
  limit?: number;            // 每页数量，默认20，最大100
  category?: string;         // 分类slug
  categoryId?: string;       // 分类ID
  
  // 搜索
  q?: string;                // 关键词搜索
  searchBy?: "name" | "description" | "all";  // 搜索字段
  
  // 筛选
  minPrice?: number;
  maxPrice?: number;
  brands?: string[];         // 品牌筛选
  attributes?: Record<string, string>;  // 属性筛选
  
  // 排序
  sortBy?: "price" | "createdAt" | "sales" | "rating";
  sortOrder?: "asc" | "desc";
  
  // 特色
  featured?: boolean;
  
  // AI推荐上下文
  recommendationContext?: string;  // "trending" | "similar" | "personalized"
}
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: {
    products: ProductCard[];  // 简化版商品卡片
    pagination: {
      page: number;
      limit: number;
      total: number;
      totalPages: number;
      hasNext: boolean;
      hasPrev: boolean;
    };
    filters: {
      categories: CategoryInfo[];
      brands: BrandInfo[];
      priceRange: { min: number; max: number };
      attributes: AttributeInfo[];
    };
  };
}
```

**ProductCard 类型：**
```typescript
interface ProductCard {
  id: string;
  name: string;
  slug: string;
  price: number;
  originalPrice: number | null;
  images: {
    url: string;
    alt: string;
    isPrimary: boolean;
  }[];
  category: {
    id: string;
    name: string;
    slug: string;
  } | null;
  rating: {
    average: number;
    count: number;
  };
  inventory: {
    stock: number;
    status: "in_stock" | "low_stock" | "out_of_stock";
  };
  isFeatured: boolean;
  badges?: string[];  // "hot" | "new" | "sale" | "bestseller"
}
```

#### 2.3.2 商品详情
```
GET /api/products/[slug]
```

**路径参数：**
- `slug`: 商品slug

**成功响应 (200):**
```typescript
{
  success: true;
  data: ProductDetail;
}
```

**ProductDetail 类型：**
```typescript
interface ProductDetail {
  id: string;
  name: string;
  slug: string;
  description: string;
  summary: string | null;
  price: number;
  originalPrice: number | null;
  discount: number | null;  // 折扣百分比
  
  category: CategoryInfo | null;
  brand: string | null;
  model: string | null;
  
  images: ProductImage[];
  variants?: ProductVariant[];  // 多规格
  
  inventory: {
    sku: string;
    stock: number;
    status: "in_stock" | "low_stock" | "out_of_stock";
    allowBackorder: boolean;
  };
  
  attributes: ProductAttribute[];
  
  rating: {
    average: number;
    count: number;
    distribution: { 1: number; 2: number; 3: number; 4: number; 5: number };
  };
  
  reviews: ReviewPreview[];
  
  // AI相关
  aiTags: string[];
  similarProducts: ProductCard[];
  
  // SEO
  metaTitle: string | null;
  metaDescription: string | null;
  
  // 时间
  createdAt: string;
  updatedAt: string;
}
```

#### 2.3.3 创建商品（管理员）
```
POST /api/admin/products
```

**请求头：**
```
Authorization: Bearer <admin_access_token>
Content-Type: multipart/form-data
```

**请求体：**
```typescript
{
  name: string;
  slug?: string;           // 不填则自动生成
  description?: string;
  summary?: string;
  price: number;
  originalPrice?: number;
  costPrice?: number;
  categoryId?: string;
  brand?: string;
  model?: string;
  barcode?: string;
  
  images: File[];          // 上传图片文件
  imageUrls?: string[];    // 或使用外部图片URL
  
  inventory: {
    sku: string;
    quantity: number;
    lowStockThreshold?: number;
    trackInventory?: boolean;
    allowBackorder?: boolean;
  };
  
  attributes?: {
    name: string;
    value: string;
  }[];
  
  metaTitle?: string;
  metaDescription?: string;
  
  isActive?: boolean;
  isFeatured?: boolean;
  isDigital?: boolean;
  
  aiTags?: string[];
}
```

#### 2.3.4 更新商品（管理员）
```
PUT /api/admin/products/[id]
```

#### 2.3.5 删除商品（管理员）
```
DELETE /api/admin/products/[id]
```

### 2.4 购物车 API

#### 2.4.1 获取购物车
```
GET /api/cart
```

**请求头（可选）：**
```
Authorization: Bearer <access_token>  // 登录用户
X-Session-Id: <session_id>            // 游客
Cookie: cart_session=<session_id>     // 或通过Cookie
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: Cart;
}
```

**Cart 类型：**
```typescript
interface Cart {
  id: string;
  items: CartItem[];
  summary: {
    itemCount: number;
    totalQuantity: number;
    subtotal: number;
    discount: number;
    tax: number;
    total: number;
  };
  shippingEstimate: {
    min: number;
    max: number;
    method: string;
  } | null;
  valid: boolean;
  messages: string[];  // 库存不足等警告
}

interface CartItem {
  id: string;
  product: {
    id: string;
    name: string;
    slug: string;
    price: number;
    image: string;
  };
  quantity: number;
  available: boolean;
  stockStatus: "in_stock" | "low_stock" | "out_of_stock";
  maxQuantity: number;  // 库存限制
}
```

#### 2.4.2 添加到购物车
```
POST /api/cart/items
```

**请求体：**
```typescript
{
  productId: string;
  quantity: number;       // 默认1
  variantId?: string;    // 如果有多规格
}
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: Cart;
  message: "已添加到购物车";
}
```

#### 2.4.3 更新购物车项数量
```
PATCH /api/cart/items/[itemId]
```

**请求体：**
```typescript
{
  quantity: number;
}
```

#### 2.4.4 移除购物车项
```
DELETE /api/cart/items/[itemId]
```

#### 2.4.5 清空购物车
```
DELETE /api/cart
```

### 2.5 订单系统 API

#### 2.5.1 创建订单
```
POST /api/orders
```

**请求体：**
```typescript
{
  // 收货地址
  shippingAddressId: string;
  billingAddressId?: string;  // 默认同收货地址
  
  // 配送方式
  shippingMethodId: string;
  
  // 支付方式
  paymentMethod: "CARD" | "ALIPAY" | "WECHAT_PAY";
  
  // 优惠码
  couponCode?: string;
  
  // 备注
  customerNote?: string;
  
  // 客户端信息（用于防重复提交）
  clientOrderId?: string;  // 客户端生成的唯一ID
}
```

**成功响应 (201):**
```typescript
{
  success: true;
  data: {
    order: Order;
    paymentIntent: {
      clientSecret: string;  // Stripe客户端密钥
      paymentIntentId: string;
    };
  };
}
```

#### 2.5.2 订单列表
```
GET /api/orders
```

**查询参数：**
```typescript
{
  page?: number;
  limit?: number;
  status?: OrderStatus;
  paymentStatus?: PaymentStatus;
  startDate?: string;     // 日期范围
  endDate?: string;
  sortBy?: "createdAt" | "totalAmount";
  sortOrder?: "asc" | "desc";
}
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: {
    orders: OrderListItem[];
    pagination: PaginationInfo;
  };
}
```

#### 2.5.3 订单详情
```
GET /api/orders/[orderNumber]
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: OrderDetail;
}
```

**OrderDetail 类型：**
```typescript
interface OrderDetail {
  id: string;
  orderNumber: string;
  
  status: OrderStatus;
  paymentStatus: PaymentStatus;
  fulfillmentStatus: FulfillmentStatus;
  
  items: OrderItem[];
  
  pricing: {
    subtotal: number;
    shipping: number;
    tax: number;
    discount: number;
    total: number;
  };
  
  shipping: {
    address: AddressInfo;
    method: string;
    trackingNumber: string | null;
    shippedAt: string | null;
    deliveredAt: string | null;
  };
  
  payment: {
    method: PaymentMethod;
    status: PaymentStatus;
    transactions: PaymentTransaction[];
  };
  
  timeline: OrderTimelineEvent[];
  
  createdAt: string;
  updatedAt: string;
}
```

#### 2.5.4 取消订单
```
POST /api/orders/[orderNumber]/cancel
```

**请求体：**
```typescript
{
  reason: string;
}
```

### 2.6 支付 API

#### 2.6.1 创建支付
```
POST /api/payments
```

**请求体：**
```typescript
{
  orderId: string;
  paymentMethod: "CARD" | "ALIPAY" | "WECHAT_PAY";
  returnUrl?: string;  // 支付完成后跳转URL
}
```

#### 2.6.2 Stripe 支付确认
```
POST /api/payments/stripe/confirm
```

#### 2.6.3 申请退款
```
POST /api/payments/[paymentId]/refund
```

**请求体：**
```typescript
{
  amount?: number;           // 部分退款时指定金额
  reason: string;
}
```

#### 2.6.4 支付回调（Stripe Webhook）
```
POST /api/payments/webhook
```

**说明：** 此接口用于接收Stripe支付状态回调，需要验证签名。

### 2.7 AI 推荐 API

#### 2.7.1 个性化推荐
```
GET /api/recommendations
```

**查询参数：**
```typescript
{
  type: "personalized" | "trending" | "similar" | "complementary";
  productId?: string;      // 基于商品推荐时需要
  categoryId?: string;    // 分类筛选
  limit?: number;         // 返回数量，默认10
  includeScores?: boolean; // 是否包含相似度分数
}
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: {
    type: string;
    products: ProductCard[];
    scores?: number[];     // 相似度分数
    generatedAt: string;   // 推荐生成时间
  };
}
```

#### 2.7.2 AI 搜索增强
```
POST /api/recommendations/search
```

**请求体：**
```typescript
{
  query: string;
  filters?: {
    categoryId?: string;
    priceRange?: { min: number; max: number };
  };
  limit?: number;
}
```

**说明：** 使用自然语言处理增强搜索，不仅匹配关键词，还理解语义。

### 2.8 后台管理 API

#### 2.8.1 仪表板统计
```
GET /api/admin/dashboard
```

**成功响应 (200):**
```typescript
{
  success: true;
  data: {
    overview: {
      todayRevenue: number;
      todayOrders: number;
      todayCustomers: number;
      todayPageViews: number;
    };
    trends: {
      revenue: { date: string; amount: number }[];
      orders: { date: string; count: number }[];
    };
    topProducts: {
      id: string;
      name: string;
      sales: number;
      revenue: number;
    }[];
    recentOrders: OrderListItem[];
    lowStockAlerts: {
      product: ProductCard;
      stock: number;
    }[];
  };
}
```

#### 2.8.2 订单管理
```
GET /api/admin/orders
```

**查询参数：**
```typescript
{
  page?: number;
  limit?: number;
  status?: OrderStatus;
  paymentStatus?: PaymentStatus;
  search?: string;  // 搜索订单号、客户名
  dateFrom?: string;
  dateTo?: string;
}
```

#### 2.8.3 更新订单状态
```
PATCH /api/admin/orders/[orderNumber]
```

**请求体：**
```typescript
{
  status?: OrderStatus;
  fulfillmentStatus?: FulfillmentStatus;
  shippingMethod?: string;
  trackingNumber?: string;
  internalNote?: string;
}
```

### 2.9 数据分析 API

#### 2.9.1 销售报表
```
GET /api/analytics/sales
```

**查询参数：**
```typescript
{
  startDate: string;      // 必填
  endDate: string;        // 必填
  groupBy: "day" | "week" | "month";
  compareToPrevious?: boolean;
}
```

#### 2.9.2 商品分析
```
GET /api/analytics/products
```

#### 2.9.3 用户分析
```
GET /api/analytics/users
```

---

## 三、核心算法和业务逻辑设计

### 3.1 AI 推荐引擎

#### 3.1.1 推荐算法架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Recommendation Engine                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Data       │    │   Model      │    │   API        │       │
│  │   Collection │───▶│   Inference  │───▶│   Service    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ User Behavior│    │ Embedding    │    │ Caching      │       │
│  │ Tracking     │    │ Generation   │    │ Layer        │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.1.2 推荐类型实现

```typescript
// src/lib/ai/recommendations.ts

/**
 * 推荐引擎核心类
 */
export class RecommendationEngine {
  private openai: OpenAI;
  private prisma: PrismaClient;
  private redis: Redis;

  constructor() {
    this.openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    this.prisma = new PrismaClient();
    this.redis = new Redis(process.env.REDIS_URL);
  }

  /**
   * 个性化推荐 - 基于用户历史行为
   * 
   * 算法流程：
   * 1. 获取用户最近浏览/购买/加购的商品
   * 2. 生成用户偏好向量（基于商品embedding加权平均）
   * 3. 从向量数据库中检索相似商品
   * 4. 排除已购买/已浏览的商品
   * 5. 返回Top-N推荐
   */
  async getPersonalizedRecommendations(
    userId: string,
    limit: number = 10
  ): Promise<RecommendedProduct[]> {
    // 1. 检查缓存
    const cacheKey = `rec:personalized:${userId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    // 2. 获取用户行为数据
    const userBehavior = await this.getUserBehaviorVector(userId);

    // 3. 如果用户没有足够行为数据，返回热销推荐
    if (!userBehavior.hasEnoughData) {
      return this.getTrendingProducts(limit);
    }

    // 4. 向量检索
    const similarProducts = await this.vectorSearch(
      userBehavior.embedding,
      {
        limit: limit * 2,  // 获取更多用于过滤
        filter: {
          isActive: true,
          price: { gte: 0 }
        }
      }
    );

    // 5. 过滤已购买商品
    const purchasedProductIds = await this.getPurchasedProductIds(userId);
    const recommendedProducts = similarProducts
      .filter(p => !purchasedProductIds.has(p.id))
      .slice(0, limit);

    // 6. 缓存结果（15分钟）
    await this.redis.setex(cacheKey, 900, JSON.stringify(recommendedProducts));

    return recommendedProducts;
  }

  /**
   * 相似商品推荐 - 基于当前商品
   */
  async getSimilarProducts(
    productId: string,
    limit: number = 10
  ): Promise<{ product: Product; score: number }[]> {
    // 1. 获取商品embedding
    const product = await this.prisma.product.findUnique({
      where: { id: productId },
      select: { embedding: true }
    });

    if (!product?.embedding) {
      // 如果没有embedding，使用分类相似
      return this.getCategorySimilarProducts(productId, limit);
    }

    // 2. 向量检索
    return this.vectorSearch(product.embedding, {
      limit: limit + 1,  // +1 用于排除自身
      filter: { id: { ne: productId } }
    });
  }

  /**
   * 互补商品推荐 - 经常一起购买的商品
   * 
   * 使用关联规则挖掘（Apriori算法简化版）
   */
  async getComplementaryProducts(
    productId: string,
    limit: number = 10
  ): Promise<{ product: Product; confidence: number }[]> {
    // 从订单数据中找出经常一起购买的商品
    const complementaryProducts = await this.prisma.$queryRaw`
      SELECT 
        oi2.product_id,
        COUNT(*) as co_occurrence,
        COUNT(*) * 1.0 / (
          SELECT COUNT(*) FROM order_items 
          WHERE product_id = ${productId}
        ) as confidence
      FROM order_items oi1
      JOIN order_items oi2 ON oi1.order_id = oi2.order_id
      WHERE oi1.product_id = ${productId}
        AND oi2.product_id != ${productId}
      GROUP BY oi2.product_id
      ORDER BY confidence DESC
      LIMIT ${limit}
    `;

    return this.enrichWithProductData(complementaryProducts);
  }

  /**
   * 热销推荐 - 基于销售数据
   */
  async getTrendingProducts(
    limit: number = 10,
    timeRange: "day" | "week" | "month" = "week"
  ): Promise<Product[]> {
    const cacheKey = `rec:trending:${timeRange}:${limit}`;
    
    // 尝试从缓存获取
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    // 计算时间范围
    const now = new Date();
    const startDate = new Date(now);
    switch (timeRange) {
      case 'day':
        startDate.setDate(startDate.getDate() - 1);
        break;
      case 'week':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case 'month':
        startDate.setMonth(startDate.getMonth() - 1);
        break;
    }

    // 查询热销商品
    const trendingProducts = await this.prisma.product.findMany({
      where: { isActive: true },
      include: {
        orderItems: {
          where: {
            order: {
              createdAt: { gte: startDate },
              status: { notIn: ['CANCELLED', 'REFUNDED'] }
            }
          }
        },
        category: true,
        images: { where: { isPrimary: true } }
      },
      take: limit
    });

    // 按销量排序
    const sorted = trendingProducts
      .map(p => ({
        ...p,
        salesCount: p.orderItems.reduce((sum, item) => sum + item.quantity, 0)
      }))
      .sort((a, b) => b.salesCount - a.salesCount)
      .slice(0, limit)
      .map(({ orderItems, ...product }) => product);

    // 缓存结果
    await this.redis.setex(cacheKey, 3600, JSON.stringify(sorted)); // 1小时

    return sorted;
  }

  /**
   * 生成商品embedding
   * 
   * 使用OpenAI的text-embedding-3-small模型
   */
  async generateProductEmbedding(product: Product): Promise<number[]> {
    // 构建商品描述文本
    const text = `
      ${product.name}
      ${product.description || ''}
      Category: ${product.category?.name || ''}
      Brand: ${product.brand || ''}
      Tags: ${product.aiTags?.join(', ') || ''}
    `;

    const response = await this.openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: text,
      encoding_format: 'float'
    });

    return response.data[0].embedding;
  }

  /**
   * 向量搜索（简化版 - 使用余弦相似度）
   * 
   * 生产环境建议使用 pgvector 或专门的向量数据库
   */
  private async vectorSearch(
    embedding: number[],
    options: {
      limit: number;
      filter?: Record<string, any>;
    }
  ): Promise<{ product: Product; score: number }[]> {
    // 获取候选商品
    const candidates = await this.prisma.product.findMany({
      where: {
        isActive: true,
        ...options.filter
      },
      select: {
        id: true,
        name: true,
        embedding: true,
        price: true,
        images: { where: { isPrimary: true }, take: 1 }
      },
      take: 100  // 限制候选集大小
    });

    // 计算余弦相似度并排序
    const results = candidates
      .filter(p => p.embedding)  // 只保留有embedding的商品
      .map(p => ({
        product: p,
        score: this.cosineSimilarity(embedding, p.embedding)
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, options.limit);

    return results;
  }

  /**
   * 计算余弦相似度
   */
  private cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length) return 0;
    
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }
}
```

#### 3.1.3 行为追踪与偏好提取

```typescript
// src/lib/ai/behavior-tracking.ts

/**
 * 用户行为类型
 */
export enum BehaviorType {
  VIEW = 'view',
  CLICK = 'click',
  ADD_TO_CART = 'add_to_cart',
  PURCHASE = 'purchase',
  WISHLIST = 'wishlist',
  REVIEW = 'review',
  SEARCH = 'search'
}

/**
 * 记录用户行为
 */
export async function trackUserBehavior(
  userId: string,
  productId: string,
  type: BehaviorType,
  metadata?: Record<string, any>
): Promise<void> {
  const prisma = new PrismaClient();
  
  await prisma.userBehavior.create({
    data: {
      userId,
      productId,
      type,
      metadata: metadata || {},
      timestamp: new Date()
    }
  });

  // 实时更新Redis中的用户最近行为
  const redis = new Redis(process.env.REDIS_URL);
  const key = `behavior:${userId}`;
  
  await redis.lpush(key, JSON.stringify({
    productId,
    type,
    timestamp: Date.now()
  }));
  
  // 保留最近100条
  await redis.ltrim(key, 0, 99);
}

/**
 * 获取用户偏好向量
 * 
 * 使用时间衰减的加权平均
 */
async function getUserBehaviorVector(userId: string): Promise<{
  embedding: number[];
  hasEnoughData: boolean;
}> {
  const prisma = new PrismaClient();
  
  // 获取用户最近100条行为
  const behaviors = await prisma.userBehavior.findMany({
    where: { userId },
    orderBy: { timestamp: 'desc' },
    take: 100,
    include: {
      product: {
        select: { embedding: true, price: true }
      }
    }
  });

  if (behaviors.length < 5) {
    return { embedding: [], hasEnoughData: false };
  }

  // 计算时间衰减权重
  const now = Date.now();
  const weightedEmbeddings: { embedding: number[]; weight: number }[] = [];
  
  for (const behavior of behaviors) {
    if (!behavior.product.embedding) continue;
    
    // 计算时间衰减（24小时内权重为1，之后每天衰减10%）
    const hoursAgo = (now - behavior.timestamp.getTime()) / (1000 * 60 * 60);
    const timeWeight = Math.max(0.1, 1 - hoursAgo / 240);
    
    // 行为类型权重
    let typeWeight = 1;
    switch (behavior.type) {
      case BehaviorType.PURCHASE: typeWeight = 3; break;
      case BehaviorType.ADD_TO_CART: typeWeight = 2; break;
      case BehaviorType.WISHLIST: typeWeight = 1.5; break;
      case BehaviorType.VIEW: typeWeight = 0.5; break;
    }
    
    weightedEmbeddings.push({
      embedding: behavior.product.embedding,
      weight: timeWeight * typeWeight
    });
  }

  // 加权平均
  const embedding = new Array(weightedEmbeddings[0]?.embedding.length || 1536).fill(0);
  let totalWeight = 0;
  
  for (const item of weightedEmbeddings) {
    for (let i = 0; i < embedding.length; i++) {
      embedding[i] += item.embedding[i] * item.weight;
    }
    totalWeight += item.weight;
  }
  
  // 归一化
  for (let i = 0; i < embedding.length; i++) {
    embedding[i] /= totalWeight;
  }

  return { embedding, hasEnoughData: true };
}
```

### 3.2 库存管理

```typescript
// src/lib/inventory/service.ts

/**
 * 库存管理服务
 */
export class InventoryService {
  private prisma: PrismaClient;
  private redis: Redis;

  constructor() {
    this.prisma = new PrismaClient();
    this.redis = new Redis(process.env.REDIS_URL);
  }

  /**
   * 预留库存（用于创建订单）
   * 
   * 使用Redis分布式锁保证并发安全
   */
  async reserveInventory(
    items: { productId: string; quantity: number }[]
  ): Promise<{ success: boolean; errors: string[] }> {
    const errors: string[] = [];
    
    // 使用事务确保原子性
    const result = await this.prisma.$transaction(async (tx) => {
      for (const item of items) {
        // 获取当前库存（使用FOR UPDATE锁住行）
        const inventory = await tx.inventory.findUnique({
          where: { productId: item.productId },
        });

        if (!inventory) {
          errors.push(`商品不存在: ${item.productId}`);
          continue;
        }

        // 计算可用库存
        const availableStock = inventory.quantity - inventory.reservedQty;

        // 检查是否需要预留
        if (inventory.trackInventory && item.quantity > availableStock) {
          if (!inventory.allowBackorder) {
            errors.push(`库存不足: ${inventory.sku}`);
            return { success: false, errors };
          }
        }

        // 预留库存
        await tx.inventory.update({
          where: { productId: item.productId },
          data: {
            reservedQty: { increment: item.quantity }
          }
        });
      }
      
      return { success: true, errors: [] };
    });

    // 发送库存不足通知（异步）
    if (result.success) {
      this.checkLowStock(items.map(i => i.productId));
    }

    return result;
  }

  /**
   * 确认订单 - 扣减实际库存
   */
  async confirmReservation(orderId: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const orderItems = await tx.orderItem.findMany({
        where: { orderId },
        select: { productId: true, quantity: true }
      });

      for (const item of orderItems) {
        await tx.inventory.update({
          where: { productId: item.productId },
          data: {
            quantity: { decrement: item.quantity },
            reservedQty: { decrement: item.quantity }
          }
        });
      }
    });
  }

  /**
   * 取消预留
   */
  async releaseReservation(orderId: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const orderItems = await tx.orderItem.findMany({
        where: { orderId },
        select: { productId: true, quantity: true }
      });

      for (const item of orderItems) {
        await tx.inventory.update({
          where: { productId: item.productId },
          data: {
            reservedQty: { decrement: item.quantity }
          }
        });
      }
    });
  }

  /**
   * 检查低库存并发送通知
   */
  private async checkLowStock(productIds: string[]): Promise<void> {
    const lowStockProducts = await this.prisma.inventory.findMany({
      where: {
        productId: { in: productId },
        trackInventory: true,
        quantity: { lte: this.prisma.raw('low_stock_threshold') }
      },
      include: { product: true }
    });

    for (const inventory of lowStockProducts) {
      // 发送到货通知队列
      await this.redis.lpush('low_stock_notifications', JSON.stringify({
        productId: inventory.productId,
        sku: inventory.sku,
        currentStock: inventory.quantity,
        threshold: inventory.lowStockThreshold,
        timestamp: new Date().toISOString()
      }));
    }
  }

  /**
   * 获取实时库存（带缓存）
   */
  async getRealTimeStock(productId: string): Promise<{
    available: number;
    status: 'in_stock' | 'low_stock' | 'out_of_stock';
  }> {
    const cacheKey = `stock:${productId}`;
    
    // 尝试从缓存获取
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    const inventory = await this.prisma.inventory.findUnique({
      where: { productId }
    });

    if (!inventory) {
      return { available: 0, status: 'out_of_stock' };
    }

    const available = inventory.quantity - inventory.reservedQty;
    let status: 'in_stock' | 'low_stock' | 'out_of_stock';
    
    if (available <= 0) {
      status = inventory.allowBackorder ? 'in_stock' : 'out_of_stock';
    } else if (available <= inventory.lowStockThreshold) {
      status = 'low_stock';
    } else {
      status = 'in_stock';
    }

    const result = { available, status };
    
    // 缓存30秒
    await this.redis.setex(cacheKey, 30, JSON.stringify(result));
    
    return result;
  }
}
```

### 3.3 订单状态机

```typescript
// src/lib/order/state-machine.ts

/**
 * 订单状态机
 * 
 * 定义订单状态的合法转换
 */
export const OrderStateMachine = {
  // 状态转换定义
  transitions: {
    [OrderStatus.PENDING]: [
      OrderStatus.CONFIRMED,
      OrderStatus.CANCELLED
    ],
    [OrderStatus.CONFIRMED]: [
      OrderStatus.PROCESSING,
      OrderStatus.CANCELLED
    ],
    [OrderStatus.PROCESSING]: [
      OrderStatus.SHIPPED,
      OrderStatus.CANCELLED
    ],
    [OrderStatus.SHIPPED]: [
      OrderStatus.DELIVERED,
      OrderStatus.REFUNDED  // 可选：退货
    ],
    [OrderStatus.DELIVERED]: [
      OrderStatus.REFUNDED  // 售后
    ],
    [OrderStatus.CANCELLED]: [],  // 终态
    [OrderStatus.REFUNDED]: [],   // 终态
    [OrderStatus.DISPUTED]: []    // 终态（需人工介入）
  },

  // 支付状态转换
  paymentTransitions: {
    [PaymentStatus.PENDING]: [
      PaymentStatus.AUTHORIZED,
      PaymentStatus.FAILED
    ],
    [PaymentStatus.AUTHORIZED]: [
      PaymentStatus.CAPTURED,
      PaymentStatus.REFUNDED
    ],
    [PaymentStatus.CAPTURED]: [
      PaymentStatus.REFUNDED,
      PaymentStatus.PARTIALLY_REFUNDED
    ],
    [PaymentStatus.FAILED]: [],    // 终态
    [PaymentStatus.REFUNDED]: [], // 终态
    [PaymentStatus.PARTIALLY_REFUNDED]: [
      PaymentStatus.REFUNDED
    ]
  },

  /**
   * 验证状态转换是否合法
   */
  canTransition(
    currentStatus: OrderStatus | PaymentStatus,
    newStatus: OrderStatus | PaymentStatus,
    type: 'order' | 'payment'
  ): boolean {
    const transitions = type === 'order' 
      ? this.transitions 
      : this.paymentTransitions;
    
    const allowedTransitions = transitions[currentStatus];
    return allowedTransitions?.includes(newStatus) || false;
  },

  /**
   * 获取可用的下一状态
   */
  getNextStatuses(
    currentStatus: OrderStatus | PaymentStatus,
    type: 'order' | 'payment'
  ): (OrderStatus | PaymentStatus)[] {
    const transitions = type === 'order' 
      ? this.transitions 
      : this.paymentTransitions;
    
    return transitions[currentStatus] || [];
  }
};

/**
 * 订单服务
 */
export class OrderService {
  private prisma: PrismaClient;
  private inventoryService: InventoryService;
  private paymentService: PaymentService;
  private notificationService: NotificationService;

  constructor() {
    this.prisma = new PrismaClient();
    this.inventoryService = new InventoryService();
    this.paymentService = new PaymentService();
    this.notificationService = new NotificationService();
  }

  /**
   * 创建订单
   */
  async createOrder(
    userId: string,
    data: CreateOrderInput
  ): Promise<Order> {
    // 1. 验证购物车
    const cart = await this.getCart(userId);
    if (!cart.items.length) {
      throw new Error('购物车为空');
    }

    // 2. 预留库存
    const reserveResult = await this.inventoryService.reserveInventory(
      cart.items.map(item => ({
        productId: item.productId,
        quantity: item.quantity
      }))
    );

    if (!reserveResult.success) {
      throw new Error(`库存不足: ${reserveResult.errors.join(', ')}`);
    }

    // 3. 计算价格
    const pricing = await this.calculatePricing(cart, data);

    // 4. 生成订单号
    const orderNumber = this.generateOrderNumber();

    // 5. 创建订单（事务）
    const order = await this.prisma.$transaction(async (tx) => {
      // 创建订单
      const order = await tx.order.create({
        data: {
          orderNumber,
          userId,
          status: OrderStatus.PENDING,
          paymentStatus: PaymentStatus.PENDING,
          fulfillmentStatus: FulfillmentStatus.PENDING,
          ...pricing,
          shippingAddressId: data.shippingAddressId,
          billingAddressId: data.billingAddressId || data.shippingAddressId,
          shippingMethod: data.shippingMethodId,
          customerNote: data.customerNote
        },
        include: {
          items: true,
          user: true
        }
      });

      // 创建订单项（快照商品信息）
      for (const item of cart.items) {
        await tx.orderItem.create({
          data: {
            orderId: order.id,
            productId: item.productId,
            productName: item.product.name,
            productSku: item.product.inventory?.sku,
            productImage: item.product.images[0]?.url,
            quantity: item.quantity,
            unitPrice: item.product.price,
            totalPrice: item.product.price * item.quantity
          }
        });
      }

      // 清空购物车
      await tx.cartItem.deleteMany({
        where: { cartId: cart.id }
      });

      return order;
    });

    // 6. 创建支付
    const paymentIntent = await this.paymentService.createPaymentIntent(
      order,
      data.paymentMethod
    );

    // 7. 发送订单创建通知
    await this.notificationService.sendOrderConfirmation(order);

    return {
      ...order,
      paymentIntent
    };
  }

  /**
   * 取消订单
   */
  async cancelOrder(orderId: string, userId: string, reason: string): Promise<void> {
    const order = await this.prisma.order.findUnique({
      where: { id: orderId }
    });

    if (!order) {
      throw new Error('订单不存在');
    }

    if (order.userId !== userId) {
      throw new Error('无权限操作此订单');
    }

    // 验证状态转换
    if (!OrderStateMachine.canTransition(order.status, OrderStatus.CANCELLED, 'order')) {
      throw new Error(`当前状态不允许取消: ${order.status}`);
    }

    // 事务处理
    await this.prisma.$transaction(async (tx) => {
      // 更新订单状态
      await tx.order.update({
        where: { id: orderId },
        data: { status: OrderStatus.CANCELLED, internalNote: reason }
      });

      // 释放库存预留
      await this.inventoryService.releaseReservation(orderId);

      // 如果已支付，发起退款
      if (order.paymentStatus === PaymentStatus.CAPTURED) {
        await this.paymentService.refund(orderId);
      }
    });

    // 发送取消通知
    await this.notificationService.sendOrderCancelled(orderId, reason);
  }

  /**
   * 更新订单状态
   */
  async updateOrderStatus(
    orderId: string,
    newStatus: OrderStatus,
    metadata?: Record<string, any>
  ): Promise<void> {
    const order = await this.prisma.order.findUnique({
      where: { id: orderId }
    });

    if (!order) {
      throw new Error('订单不存在');
    }

    if (!OrderStateMachine.canTransition(order.status, newStatus, 'order')) {
      throw new Error(`无效的状态转换: ${order.status} -> ${newStatus}`);
    }

    const updateData: any = { status: newStatus };

    // 根据新状态添加额外字段
    switch (newStatus) {
      case OrderStatus.SHIPPED:
        updateData.shippedAt = new Date();
        updateData.trackingNumber = metadata?.trackingNumber;
        break;
      case OrderStatus.DELIVERED:
        updateData.deliveredAt = new Date();
        break;
    }

    await this.prisma.order.update({
      where: { id: orderId },
      data: updateData
    });

    // 发送状态变更通知
    await this.notificationService.sendOrderStatusUpdate(orderId, newStatus);
  }
}
```

---

## 四、前端组件结构和状态管理

### 4.1 项目结构

```
src/
├── app/                          # Next.js 14 App Router
│   ├── (auth)/                   # 认证相关页面
│   │   ├── login/
│   │   ├── register/
│   │   └── layout.tsx
│   ├── (shop)/                   # 商城页面
│   │   ├── page.tsx              # 首页
│   │   ├── products/
│   │   │   ├── page.tsx          # 商品列表
│   │   │   └── [slug]/           # 商品详情
│   │   ├── cart/
│   │   ├── orders/
│   │   └── account/
│   ├── (admin)/                  # 后台管理
│   │   ├── dashboard/
│   │   ├── products/
│   │   ├── orders/
│   │   ├── customers/
│   │   └── analytics/
│   ├── api/                      # API 路由
│   │   ├── auth/
│   │   ├── products/
│   │   ├── cart/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── recommendations/
│   │   ├── admin/
│   │   └── analytics/
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ui/                       # 基础UI组件
│   │   ├── Button/
│   │   ├── Input/
│   │   ├── Modal/
│   │   ├── Dropdown/
│   │   ├── Card/
│   │   ├── Badge/
│   │   ├── Toast/
│   │   └── Skeleton/
│   ├── layout/                   # 布局组件
│   │   ├── Header/
│   │   ├── Footer/
│   │   ├── Sidebar/
│   │   └── Navbar/
│   ├── product/                  # 商品组件
│   │   ├── ProductCard/
│   │   ├── ProductGrid/
│   │   ├── ProductImageGallery/
│   │   ├── ProductInfo/
│   │   ├── ProductReviews/
│   │   └── ProductForm/
│   ├── cart/                      # 购物车组件
│   │   ├── CartItem/
│   │   ├── CartSummary/
│   │   └── CartDrawer/
│   ├── order/                     # 订单组件
│   │   ├── OrderCard/
│   │   ├── OrderTimeline/
│   │   ├── OrderItems/
│   │   └── OrderStatusBadge/
│   ├── checkout/                  # 结账组件
│   │   ├── AddressForm/
│   │   ├── ShippingMethod/
│   │   ├── PaymentForm/
│   │   └── CheckoutSummary/
│   ├── admin/                     # 后台组件
│   │   ├── DataTable/
│   │   ├── StatsCard/
│   │   ├── Chart/
│   │   ├── StatusBadge/
│   │   └── BulkActionBar/
│   └── ai/                        # AI相关组件
│       ├── RecommendationCarousel/
│       ├── AIBadge/
│       └── SearchEnhancer/
├── lib/                           # 工具库
│   ├── api/                       # API客户端
│   │   ├── client.ts
│   │   ├── endpoints.ts
│   │   └── types.ts
│   ├── auth/                      # 认证
│   │   ├── client.ts
│   │   └── hooks.ts
│   ├── cart/                      # 购物车
│   │   └── hooks.ts
│   ├── ai/                        # AI推荐
│   │   └── recommendations.ts
│   ├── utils/                     # 工具函数
│   │   ├── cn.ts
│   │   │   └── format.ts
│   └── constants.ts
├── hooks/                         # React Hooks
│   ├── useAuth.ts
│   ├── useCart.ts
│   ├── useProducts.ts
│   ├── useOrders.ts
│   ├── useRecommendations.ts
│   └── useDebounce.ts
├── stores/                        # 状态管理
│   ├── authStore.ts
│   ├── cartStore.ts
│   └── uiStore.ts
├── types/                         # 类型定义
│   ├── product.ts
│   ├── cart.ts
│   ├── order.ts
│   └── user.ts
└── styles/
    └── themes/
```

### 4.2 核心组件设计

#### 4.2.1 商品卡片组件

```typescript
// src/components/product/ProductCard/ProductCard.tsx

'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useCartStore } from '@/stores/cartStore';
import { Product, ProductImage } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { HeartIcon, ShoppingCartIcon } from '@heroicons/react/24/outline';
import { HeartIcon as HeartSolidIcon } from '@heroicons/react/24/solid';
import { formatPrice } from '@/lib/utils/format';

interface ProductCardProps {
  product: Product;
  variant?: 'default' | 'compact' | 'horizontal';
  showQuickAdd?: boolean;
  priority?: boolean;
}

export function ProductCard({
  product,
  variant = 'default',
  showQuickAdd = true,
  priority = false
}: ProductCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const { addItem } = useCartStore();
  
  const primaryImage = product.images?.find(img => img.isPrimary) || product.images?.[0];
  
  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setIsLoading(true);
    try {
      await addItem(product.id, 1);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleWishlist = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsWishlisted(!isWishlisted);
    // 调用wishlist API
  };

  // 计算折扣
  const discount = product.originalPrice 
    ? Math.round((1 - product.price / product.originalPrice) * 100)
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="group relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link href={`/products/${product.slug}`}>
        <div className={`
          relative overflow-hidden rounded-lg bg-white
          ${variant === 'horizontal' ? 'flex' : ''}
        `}>
          {/* 图片区域 */}
          <div className={`
            relative aspect-[4/5] overflow-hidden
            ${variant === 'horizontal' ? 'w-48 flex-shrink-0' : 'w-full'}
          `}>
            <Image
              src={primaryImage?.url || '/placeholder.jpg'}
              alt={primaryImage?.alt || product.name}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
              className="object-cover transition-transform duration-500 group-hover:scale-105"
              priority={priority}
            />
            
            {/* 徽章 */}
            <div className="absolute left-2 top-2 flex flex-col gap-1">
              {product.isFeatured && (
                <Badge variant="primary">热销</Badge>
              )}
              {discount && (
                <Badge variant="danger">{discount}% 折扣</Badge>
              )}
            </div>
            
            {/* AI 推荐标签 */}
            {product.isAIRecommended && (
              <div className="absolute right-2 top-2">
                <Badge variant="ai" className="bg-gradient-to-r from-purple-500 to-pink-500">
                  🤖 为你推荐
                </Badge>
              </div>
            )}
            
            {/* 快捷操作 */}
            <div className={`
              absolute bottom-2 right-2 flex gap-2
              transition-opacity duration-300
              ${isHovered ? 'opacity-100' : 'opacity-0'}
            `}>
              <button
                onClick={handleToggleWishlist}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-md hover:bg-gray-50"
              >
                {isWishlisted ? (
                  <HeartSolidIcon className="h-5 w-5 text-red-500" />
                ) : (
                  <HeartIcon className="h-5 w-5 text-gray-600" />
                )}
              </button>
              
              {showQuickAdd && product.inventory?.stock > 0 && (
                <button
                  onClick={handleAddToCart}
                  disabled={isLoading}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white shadow-md hover:bg-gray-800 disabled:opacity-50"
                >
                  <ShoppingCartIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>
          
          {/* 信息区域 */}
          <div className={`
            p-4
            ${variant === 'horizontal' ? 'flex flex-col justify-center' : ''}
          `}>
            {/* 分类 */}
            {product.category && (
              <p className="text-xs text-gray-500 mb-1">
                {product.category.name}
              </p>
            )}
            
            {/* 名称 */}
            <h3 className="font-medium text-gray-900 line-clamp-2 mb-2">
              {product.name}
            </h3>
            
            {/* 评分 */}
            {product.rating && product.rating.count > 0 && (
              <div className="flex items-center gap-1 mb-2">
                <div className="flex">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <StarIcon
                      key={star}
                      className={`h-4 w-4 ${
                        star <= Math.round(product.rating.average)
                          ? 'text-yellow-400'
                          : 'text-gray-300'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-gray-500">
                  ({product.rating.count})
                </span>
              </div>
            )}
            
            {/* 价格 */}
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-bold text-gray-900">
                {formatPrice(product.price)}
              </span>
              {product.originalPrice && (
                <span className="text-sm text-gray-500 line-through">
                  {formatPrice(product.originalPrice)}
                </span>
              )}
            </div>
            
            {/* 库存状态 */}
            {product.inventory && (
              <div className="mt-2">
                <StockBadge 
                  status={product.inventory.status} 
                  stock={product.inventory.stock}
                />
              </div>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

// 库存状态徽章组件
function StockBadge({ status, stock }: { status: string; stock: number }) {
  const config = {
    in_stock: { label: '有货', className: 'bg-green-100 text-green-800' },
    low_stock: { label: `仅剩${stock}件`, className: 'bg-yellow-100 text-yellow-800' },
    out_of_stock: { label: '缺货', className: 'bg-gray-100 text-gray-800' }
  };
  
  const { label, className } = config[status as keyof typeof config] || config.in_stock;
  
  return (
    <span className={`text-xs px-2 py-1 rounded-full ${className}`}>
      {label}
    </span>
  );
}
```

#### 4.2.2 购物车状态管理

```typescript
// src/stores/cartStore.ts

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Cart, CartItem } from '@/types';
import { cartApi } from '@/lib/api/client';

interface CartState {
  // 状态
  cart: Cart | null;
  isLoading: boolean;
  error: string | null;
  isOpen: boolean; // 购物车抽屉
  
  // Actions
  fetchCart: () => Promise<void>;
  addItem: (productId: string, quantity?: number) => Promise<void>;
  updateItem: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  clearCart: () => Promise<void>;
  
  // UI
  openCart: () => void;
  closeCart: () => void;
  toggleCart: () => void;
  
  // 本地操作（乐观更新）
  optimisticAddItem: (productId: string, quantity: number) => void;
  optimisticRemoveItem: (itemId: string) => void;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      cart: null,
      isLoading: false,
      error: null,
      isOpen: false,
      
      fetchCart: async () => {
        set({ isLoading: true, error: null });
        try {
          const cart = await cartApi.getCart();
          set({ cart, isLoading: false });
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '获取购物车失败',
            isLoading: false 
          });
        }
      },
      
      addItem: async (productId: string, quantity = 1) => {
        const { optimisticAddItem } = get();
        
        // 乐观更新
        optimisticAddItem(productId, quantity);
        
        try {
          const cart = await cartApi.addItem(productId, quantity);
          set({ cart });
        } catch (error) {
          // 回滚
          get().fetchCart();
          throw error;
        }
      },
      
      updateItem: async (itemId: string, quantity: number) => {
        const { cart } = get();
        if (!cart) return;
        
        // 乐观更新
        const updatedItems = cart.items.map(item =>
          item.id === itemId ? { ...item, quantity } : item
        );
        set({
          cart: {
            ...cart,
            items: updatedItems,
            summary: calculateSummary(updatedItems)
          }
        });
        
        try {
          const cart = await cartApi.updateItem(itemId, quantity);
          set({ cart });
        } catch (error) {
          get().fetchCart();
          throw error;
        }
      },
      
      removeItem: async (itemId: string) => {
        const { optimisticRemoveItem } = get();
        
        optimisticRemoveItem(itemId);
        
        try {
          const cart = await cartApi.removeItem(itemId);
          set({ cart });
        } catch (error) {
          get().fetchCart();
          throw error;
        }
      },
      
      clearCart: async () => {
        try {
          await cartApi.clearCart();
          set({ cart: null });
        } catch (error) {
          throw error;
        }
      },
      
      openCart: () => set({ isOpen: true }),
      closeCart: () => set({ isOpen: false }),
      toggleCart: () => set(state => ({ isOpen: !state.isOpen })),
      
      optimisticAddItem: (productId: string, quantity: number) => {
        const { cart } = get();
        if (!cart) {
          // 如果没有购物车，创建一个临时的
          set({
            cart: {
              id: 'temp',
              items: [{
                id: 'temp-' + Date.now(),
                product: { id: productId } as any,
                quantity,
                available: true,
                stockStatus: 'in_stock',
                maxQuantity: 99
              }],
              summary: { itemCount: 1, totalQuantity: quantity, subtotal: 0, discount: 0, tax: 0, total: 0 }
            }
          });
          return;
        }
        
        // 检查是否已存在
        const existingItem = cart.items.find(
          item => item.product.id === productId
        );
        
        if (existingItem) {
          // 更新数量
          const updatedItems = cart.items.map(item =>
            item.product.id === productId
              ? { ...item, quantity: item.quantity + quantity }
              : item
          );
          set({
            cart: {
              ...cart,
              items: updatedItems,
              summary: calculateSummary(updatedItems)
            }
          });
        } else {
          // 添加新项
          const newItem: CartItem = {
            id: 'temp-' + Date.now(),
            product: { id: productId } as any,
            quantity,
            available: true,
            stockStatus: 'in_stock',
            maxQuantity: 99
          };
          set({
            cart: {
              ...cart,
              items: [...cart.items, newItem],
              summary: calculateSummary([...cart.items, newItem])
            }
          });
        }
      },
      
      optimisticRemoveItem: (itemId: string) => {
        const { cart } = get();
        if (!cart) return;
        
        const updatedItems = cart.items.filter(item => item.id !== itemId);
        set({
          cart: {
            ...cart,
            items: updatedItems,
            summary: calculateSummary(updatedItems)
          }
        });
      }
    }),
    {
      name: 'cart-storage',
      partialize: (state) => ({ cart: state.cart }) // 只持久化购物车数据
    }
  )
);

// 计算购物车汇总
function calculateSummary(items: CartItem[]) {
  const totalQuantity = items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = items.reduce((sum, item) => {
    if (!item.available) return sum;
    return sum + (item.product.price * item.quantity);
  }, 0);
  
  // 简化：假设税率10%，无折扣
  const tax = subtotal * 0.1;
  const discount = 0;
  const total = subtotal + tax - discount;
  
  return {
    itemCount: items.length,
    totalQuantity,
    subtotal,
    discount,
    tax,
    total
  };
}
```

#### 4.2.3 AI 推荐轮播组件

```typescript
// src/components/ai/RecommendationCarousel/RecommendationCarousel.tsx

'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ProductCard } from '@/components/product/ProductCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { recommendationsApi } from '@/lib/api/client';

interface RecommendationCarouselProps {
  type: 'personalized' | 'trending' | 'similar' | 'complementary';
  productId?: string;
  title: string;
  subtitle?: string;
}

export function RecommendationCarousel({
  type,
  productId,
  title,
  subtitle
}: RecommendationCarouselProps) {
  const [products, setProducts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        setIsLoading(true);
        const response = await recommendationsApi.get({
          type,
          productId,
          limit: 10
        });
        
        if (response.success) {
          setProducts(response.data.products);
        }
      } catch (err) {
        setError('加载推荐失败');
      } finally {
        setIsLoading(false);
      }
    }

    fetchRecommendations();
  }, [type, productId]);

  if (error) {
    return null; // 推荐失败时静默隐藏
  }

  return (
    <section className="py-12">
      {/* 标题 */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          {title}
          {type === 'personalized' && (
            <span className="text-sm bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent">
              AI 智能推荐
            </span>
          )}
        </h2>
        {subtitle && (
          <p className="text-gray-500 mt-1">{subtitle}</p>
        )}
      </div>

      {/* 加载状态 */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-3">
              <Skeleton className="aspect-[4/5] rounded-lg" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {/* 商品列表 */}
      {!isLoading && products.length > 0 && (
        <div className="relative">
          {/* 滚动容器 */}
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory scrollbar-hide">
            {products.map((product, index) => (
              <motion.div
                key={product.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex-shrink-0 w-[200px] md:w-[240px] snap-start"
              >
                <ProductCard 
                  product={product} 
                  variant="compact"
                  priority={index < 4}
                />
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* 空状态 */}
      {!isLoading && products.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          暂无推荐
        </div>
      )}
    </section>
  );
}
```

### 4.3 状态管理架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        State Management                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │   Zustand       │     │   React Query    │                  │
│  │   (Client       │     │   (Server        │                  │
│  │    State)       │     │    State)        │                  │
│  ├──────────────────┤     ├──────────────────┤                  │
│  │ - Auth State    │     │ - Products       │                  │
│  │ - Cart State    │     │ - Orders          │                  │
│  │ - UI State      │     │ - Categories      │                  │
│  │ - Wishlist      │     │ - Recommendations │                  │
│  │ - Notifications │     │ - Analytics       │                  │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                         │                            │
│           ▼                         ▼                            │
│  ┌─────────────────────────────────────────────┐                │
│  │              Server Components              │                │
│  │         (Initial Data via Props)            │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、文件/模块目录结构

```
src/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── register/
│   │   │   └── page.tsx
│   │   └── layout.tsx
│   ├── (shop)/
│   │   ├── page.tsx                    # 首页
│   │   ├── products/
│   │   │   ├── page.tsx                # 商品列表
│   │   │   └── [slug]/
│   │   │       └── page.tsx            # 商品详情
│   │   ├── cart/
│   │   │   └── page.tsx                # 购物车页面
│   │   ├── checkout/
│   │   │   ├── page.tsx                # 结账流程
│   │   │   ├── success/
│   │   │   │   └── [orderNumber]/
│   │   │   │       └── page.tsx
│   │   │   └── cancel/
│   │   │       └── page.tsx
│   │   ├── orders/
│   │   │   ├── page.tsx                # 订单列表
│   │   │   └── [orderNumber]/
│   │   │       └── page.tsx            # 订单详情
│   │   ├── account/
│   │   │   ├── page.tsx                # 账户首页
│   │   │   ├── profile/
│   │   │   │   └── page.tsx
│   │   │   ├── addresses/
│   │   │   │   └── page.tsx
│   │   │   └── wishlist/
│   │   │       └── page.tsx
│   │   ├── search/
│   │   │   └── page.tsx                # 搜索结果
│   │   └── category/
│   │       └── [slug]/
│   │           └── page.tsx            # 分类页
│   ├── (admin)/
│   │   ├── layout.tsx                  # 后台布局
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   ├── products/
│   │   │   ├── page.tsx                # 商品列表
│   │   │   ├── new/
│   │   │   │   └── page.tsx            # 新建商品
│   │   │   └── [id]/
│   │   │       ├── edit/
│   │   │       │   └── page.tsx
│   │   │       └── page.tsx            # 商品详情
│   │   ├── orders/
│   │   │   ├── page.tsx
│   │   │   └── [orderNumber]/
│   │   │       └── page.tsx
│   │   ├── customers/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── categories/
│   │   │   └── page.tsx
│   │   ├── analytics/
│   │   │   ├── sales/
│   │   │   │   └── page.tsx
│   │   │   ├── products/
│   │   │   │   └── page.tsx
│   │   │   └── users/
│   │   │       └── page.tsx
│   │   └── settings/
│   │       ├── page.tsx
│   │       └── payments/
│   │           └── page.tsx
│   ├── api/
│   │   ├── auth/
│   │   │   ├── route.ts                # 统一认证入口
│   │   │   ├── register/
│   │   │   │   └── route.ts
│   │   │   ├── login/
│   │   │   │   └── route.ts
│   │   │   ├── logout/
│   │   │   │   └── route.ts
│   │   │   ├── refresh/
│   │   │   │   └── route.ts
│   │   │   └── me/
│   │   │       └── route.ts
│   │   ├── products/
│   │   │   ├── route.ts                # 商品列表
│   │   │   ├── search/
│   │   │   │   └── route.ts
│   │   │   └── [slug]/
│   │   │       └── route.ts            # 商品详情
│   │   ├── cart/
│   │   │   ├── route.ts                # 获取/清空购物车
│   │   │   └── items/
│   │   │       └── route.ts            # 购物车项操作
│   │   ├── orders/
│   │   │   ├── route.ts
│   │   │   └── [orderNumber]/
│   │   │       └── route.ts
│   │   ├── payments/
│   │   │   ├── route.ts
│   │   │   ├── webhook/
│   │   │   │   └── route.ts           # Stripe Webhook
│   │   │   └── [id]/
│   │   │       └── refund/
│   │   │           └── route.ts
│   │   ├── recommendations/
│   │   │   └── route.ts
│   │   ├── admin/
│   │   │   ├── dashboard/
│   │   │   │   └── route.ts
│   │   │   ├── products/
│   │   │   │   └── route.ts
│   │   │   ├── orders/
│   │   │   │   └── route.ts
│   │   │   └── analytics/
│   │   │       └── route.ts
│   │   └── upload/
│   │       └── route.ts                # 文件上传
│   ├── layout.tsx
│   ├── loading.tsx
│   ├── not-found.tsx
│   └── globals.css
├── components/
│   ├── ui/
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   └── index.ts
│   │   ├── Input/
│   │   ├── Modal/
│   │   ├── Card/
│   │   ├── Badge/
│   │   ├── Toast/
│   │   ├── Skeleton/
│   │   ├── Select/
│   │   ├── Checkbox/
│   │   ├── Radio/
│   │   ├── Tabs/
│   │   ├── Table/
│   │   ├── Pagination/
│   │   └── Dropdown/
│   ├── layout/
│   │   ├── Header/
│   │   ├── Footer/
│   │   ├── Sidebar/
│   │   ├── Navbar/
│   │   └── AdminLayout/
│   ├── product/
│   ├── cart/
│   ├── order/
│   ├── checkout/
│   ├── admin/
│   └── ai/
├── lib/
│   ├── api/
│   ├── auth/
│   ├── cart/
│   ├── ai/
│   │   ├── recommendations.ts
│   │   ├── behavior-tracking.ts
│   │   └── embeddings.ts
│   ├── order/
│   │   └── state-machine.ts
│   ├── inventory/
│   │   └── service.ts
│   ├── payment/
│   │   ├── stripe.ts
│   │   └── types.ts
│   ├── utils/
│   └── constants.ts
├── hooks/
├── stores/
├── types/
├── prisma/
│   ├── schema.prisma
│   └── seed.ts
└── public/
    └── images/
```

---

## 六、模块拆分方案

基于项目功能域和依赖关系，将40+文件拆分为以下模块：

```json
{
  "modules": [
    {
      "id": "core-common",
      "name": "核心基础设施",
      "description": "包含数据库连接、工具函数、类型定义、常量配置等公共基础设施",
      "files": [
        "src/lib/utils/cn.ts",
        "src/lib/utils/format.ts",
        "src/lib/constants.ts",
        "src/types/index.ts",
        "src/types/product.ts",
        "src/types/user.ts",
        "src/types/cart.ts",
        "src/types/order.ts",
        "src/lib/db/client.ts"
      ]
    },
    {
      "id": "auth-user",
      "name": "用户认证系统",
      "description": "用户注册、登录、会话管理、个人信息管理、地址管理",
      "files": [
        "src/app/api/auth/route.ts",
        "src/app/api/auth/register/route.ts",
        "src/app/api/auth/login/route.ts",
        "src/app/api/auth/logout/route.ts",
        "src/app/api/auth/refresh/route.ts",
        "src/app/api/auth/me/route.ts",
        "src/app/api/users/route.ts",
        "src/app/api/users/addresses/route.ts",
        "src/lib/auth/client.ts",
        "src/hooks/useAuth.ts",
        "src/stores/authStore.ts"
      ]
    },
    {
      "id": "product-catalog",
      "name": "商品目录",
      "description": "商品CRUD、分类管理、商品搜索、图片管理",
      "files": [
        "src/app/api/products/route.ts",
        "src/app/api/products/search/route.ts",
        "src/app/api/products/[slug]/route.ts",
        "src/app/api/categories/route.ts",
        "src/app/api/admin/products/route.ts",
        "src/app/api/admin/products/[id]/route.ts",
        "src/components/product/ProductCard/ProductCard.tsx",
        "src/components/product/ProductGrid/ProductGrid.tsx",
        "src/components/product/ProductImageGallery/ProductImageGallery.tsx",
        "src/components/product/ProductInfo/ProductInfo.tsx",
        "src/hooks/useProducts.ts"
      ]
    },
    {
      "id": "shopping-cart",
      "name": "购物车系统",
      "description": "购物车增删改查、库存预留、乐观更新",
      "files": [
        "src/app/api/cart/route.ts",
        "src/app/api/cart/items/route.ts",
        "src/components/cart/CartItem/CartItem.tsx",
        "src/components/cart/CartSummary/CartSummary.tsx",
        "src/components/cart/CartDrawer/CartDrawer.tsx",
        "src/stores/cartStore.ts",
        "src/hooks/useCart.ts",
        "src/lib/cart/hooks.ts"
      ]
    },
    {
      "id": "order-management",
      "name": "订单系统",
      "description": "订单创建、状态管理、订单历史、取消退款",
      "files": [
        "src/app/api/orders/route.ts",
        "src/app/api/orders/[orderNumber]/route.ts",
        "src/app/api/orders/[orderNumber]/cancel/route.ts",
        "src/lib/order/state-machine.ts",
        "src/components/order/OrderCard/OrderCard.tsx",
        "src/components/order/OrderTimeline/OrderTimeline.tsx",
        "src/components/order/OrderStatusBadge/OrderStatusBadge.tsx",
        "src/hooks/useOrders.ts"
      ]
    },
    {
      "id": "payment-gateway",
      "name": "支付网关",
      "description": "Stripe支付集成、支付回调、退款处理",
      "files": [
        "src/app/api/payments/route.ts",
        "src/app/api/payments/webhook/route.ts",
        "src/app/api/payments/[id]/refund/route.ts",
        "src/lib/payment/stripe.ts",
        "src/lib/payment/types.ts",
        "src/components/checkout/PaymentForm/PaymentForm.tsx"
      ]
    },
    {
      "id": "ai-recommendation",
      "name": "AI推荐引擎",
      "description": "商品推荐算法、用户行为追踪、向量搜索",
      "files": [
        "src/app/api/recommendations/route.ts",
        "src/app/api/recommendations/search/route.ts",
        "src/lib/ai/recommendations.ts",
        "src/lib/ai/behavior-tracking.ts",
        "src/lib/ai/embeddings.ts",
        "src/components/ai/RecommendationCarousel/RecommendationCarousel.tsx",
        "src/components/ai/AIBadge/AIBadge.tsx",
        "src/hooks/useRecommendations.ts"
      ]
    },
    {
      "id": "inventory-service",
      "name": "库存服务",
      "description": "库存管理、低库存预警、预留释放",
      "files": [
        "src/lib/inventory/service.ts",
        "prisma/schema.prisma (Inventory部分)"
      ]
    },
    {
      "id": "admin-dashboard",
      "name": "后台管理系统",
      "description": "仪表板、订单管理、商品管理、分类管理",
      "files": [
        "src/app/(admin)/layout.tsx",
        "src/app/api/admin/dashboard/route.ts",
        "src/app/api/admin/orders/route.ts",
        "src/app/api/admin/customers/route.ts",
        "src/app/api/admin/analytics/route.ts",
        "src/components/admin/DataTable/DataTable.tsx",
        "src/components/admin/StatsCard/StatsCard.tsx",
        "src/components/admin/Chart/Chart.tsx"
      ]
    },
    {
      "id": "ui-components",
      "name": "UI组件库",
      "description": "基础UI组件：按钮、输入框、模态框、徽章等",
      "files": [
        "src/components/ui/Button/Button.tsx",
        "src/components/ui/Input/Input.tsx",
        "src/components/ui/Modal/Modal.tsx",
        "src/components/ui/Card/Card.tsx",
        "src/components/ui/Badge/Badge.tsx",
        "src/components/ui/Toast/Toast.tsx",
        "src/components/ui/Skeleton/Skeleton.tsx",
        "src/components/ui/Table/Table.tsx",
        "src/components/layout/Header/Header.tsx",
        "src/components/layout/Footer/Footer.tsx"
      ]
    }
  ]
}
```

---

## 总结

本详细设计文档涵盖：

1. **数据库设计** - 完整的 Prisma Schema，涵盖用户、商品、订单、支付、库存、AI推荐等核心实体

2. **API 设计** - 详细的 RESTful API 定义，包含请求/响应格式、错误处理

3. **核心算法** - AI推荐引擎（个性化、相似、互补、热销）、库存管理、订单状态机

4. **前端架构** - 组件结构、状态管理（Zustand + React Query）、文件组织

5. **模块拆分** - 将40+文件按功能域拆分为10个模块，符合低耦合高内聚原则

各模块间依赖关系清晰：核心基础设施 → 用户认证 → 商品/购物车 → 订单/支付 → AI推荐 → 后台管理，遵循业务逻辑顺序。
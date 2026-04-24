<think>
用户希望我作为架构师和开发工程师，完成"详细设计"阶段的工作。我需要基于需求分析和架构设计文档，输出详细的、可指导编码的技术方案。

根据要求，我需要输出：
1. 数据库表结构设计（字段、类型、索引、关系）
2. API 接口详细定义（路径、方法、参数、返回值）
3. 核心算法和业务逻辑设计
4. 前端组件结构和状态管理设计
5. 文件/模块目录结构规划
6. 模块拆分 JSON 输出

让我开始详细设计：

首先，我需要了解项目的完整信息：
- 项目类型：任务管理Web应用
- 技术栈：Python Flask + SQLite + HTML/CSS/JS
- 功能：用户注册登录、任务CRUD、任务分类和优先级、到期日提醒、团队协作

让我开始详细设计：

## 1. 数据库表结构设计

根据需求，需要设计以下表：
- users（用户表）
- tasks（任务表）
- categories（分类表）
- teams（团队表）
- team_members（团队成员表）
- task_comments（任务评论表）
- notifications（通知表）

## 2. API 接口详细定义

需要定义 RESTful API：
- 用户认证：/api/auth/register, /api/auth/login, /api/auth/logout
- 任务管理：/api/tasks, /api/tasks/{id}
- 分类管理：/api/categories


- 团队协作：/api/teams, /api/teams/{id}/members
- 通知系统：/api/notifications

## 3. 核心算法和业务逻辑设计

需要设计任务排序算法、优先级处理逻辑、提醒机制、权限验证等核心业务逻辑。

## 4. 前端组件结构

前端采用原生HTML/CSS/JS，实现登录注册、任务列表、任务详情、分类管理和团队协作等页面模块。

## 5. 模块拆分

根据功能域划分为：用户认证模块、任务管理模块、分类标签模块、团队协作模块和基础设施模块。

现在开始编写完整的设计文档。
</think>

# TaskFlow 任务管理系统 - 详细技术设计文档

**项目名称**：TaskFlow 任务管理系统  
**文档版本**：V1.0  
**编制角色**：高级开发工程师 / 系统架构师  
**项目阶段**：详细设计  

---

## 一、数据库表结构设计

### 1.1 数据库总体设计

**数据库类型**：SQLite3  
**数据库文件**：`instance/taskflow.db`  
**字符编码**：UTF-8  
**外键约束**：启用（PRAGMA foreign_keys = ON）

### 1.2 数据表详细设计

#### 1.2.1 用户表（users）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户唯一ID |
| username | VARCHAR(50) | UNIQUE NOT NULL | 用户名 |
| email | VARCHAR(100) | UNIQUE NOT NULL | 邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| full_name | VARCHAR(100) | | 真实姓名 |
| avatar_url | VARCHAR(255) | | 头像URL |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |
| last_login | DATETIME | | 最后登录时间 |
| is_active | BOOLEAN | NOT NULL DEFAULT 1 | 是否激活 |

**索引**：
- `idx_users_email` ON users(email)
- `idx_users_username` ON users(username)

---

#### 1.2.2 任务表（tasks）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 任务唯一ID |
| title | VARCHAR(200) | NOT NULL | 任务标题 |
| description | TEXT | | 任务描述 |
| user_id | INTEGER | FOREIGN KEY NOT NULL | 所属用户ID |
| category_id | INTEGER | FOREIGN KEY | 分类ID |
| priority | INTEGER | NOT NULL DEFAULT 2 | 优先级(1=高,2=中,3=低) |
| status | VARCHAR(20) | NOT NULL DEFAULT 'pending' | 状态(pending/in_progress/completed/archived) |
| due_date | DATETIME | | 截止日期 |
| completed_at | DATETIME | | 完成时间 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引**：
- `idx_tasks_user_id` ON tasks(user_id)
- `idx_tasks_category_id` ON tasks(category_id)
- `idx_tasks_status` ON tasks(status)
- `idx_tasks_due_date` ON tasks(due_date)

---

#### 1.2.3 分类表（categories）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 分类唯一ID |
| name | VARCHAR(50) | NOT NULL | 分类名称 |
| color | VARCHAR(7) | NOT NULL DEFAULT '#3498db' | 分类颜色(HEX) |
| user_id | INTEGER | FOREIGN KEY NOT NULL | 所属用户ID |
| is_default | BOOLEAN | NOT NULL DEFAULT 0 | 是否默认分类 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**：
- `idx_categories_user_id` ON categories(user_id)

---

#### 1.2.4 团队表（teams）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 团队唯一ID |
| name | VARCHAR(100) | NOT NULL | 团队名称 |
| description | TEXT | | 团队描述 |
| owner_id | INTEGER | FOREIGN KEY NOT NULL | 所有者ID |
| invite_code | VARCHAR(32) | UNIQUE | 邀请码 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引**：
- `idx_teams_owner_id` ON teams(owner_id)
- `idx_teams_invite_code` ON teams(invite_code)

---

#### 1.2.5 团队成员表（team_members）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 成员ID |
| team_id | INTEGER | FOREIGN KEY NOT NULL | 团队ID |
| user_id | INTEGER | FOREIGN KEY NOT NULL | 用户ID |
| role | VARCHAR(20) | NOT NULL DEFAULT 'member' | 角色(owner/admin/member) |
| joined_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 加入时间 |

**索引**：
- `idx_team_members_team_id` ON team_members(team_id)
- `idx_team_members_user_id` ON team_members(user_id)
- UNIQUE(team_id, user_id)

---

#### 1.2.6 团队任务表（team_tasks）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 任务ID |
| title | VARCHAR(200) | NOT NULL | 任务标题 |
| description | TEXT | | 任务描述 |
| team_id | INTEGER | FOREIGN KEY NOT NULL | 团队ID |
| assignee_id | INTEGER | FOREIGN KEY | 负责人ID |
| category_id | INTEGER | FOREIGN KEY | 分类ID |
| priority | INTEGER | NOT NULL DEFAULT 2 | 优先级 |
| status | VARCHAR(20) | NOT NULL DEFAULT 'pending' | 状态 |
| due_date | DATETIME | | 截止日期 |
| completed_at | DATETIME | | 完成时间 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引**：
- `idx_team_tasks_team_id` ON team_tasks(team_id)
- `idx_team_tasks_assignee_id` ON team_tasks(assignee_id)

---

#### 1.2.7 任务评论表（task_comments）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 评论ID |
| task_id | INTEGER | FOREIGN KEY NOT NULL | 任务ID |
| task_type | VARCHAR(20) | NOT NULL | 任务类型(personal/team) |
| user_id | INTEGER | FOREIGN KEY NOT NULL | 评论者ID |
| content | TEXT | NOT NULL | 评论内容 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**：
- `idx_task_comments_task_id` ON task_comments(task_id, task_type)

---

#### 1.2.8 通知表（notifications）

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 通知ID |
| user_id | INTEGER | FOREIGN KEY NOT NULL | 接收用户ID |
| type | VARCHAR(50) | NOT NULL | 通知类型 |
| title | VARCHAR(200) | NOT NULL | 通知标题 |
| content | TEXT | | 通知内容 |
| related_id | INTEGER | | 关联ID |
| related_type | VARCHAR(50) | | 关联类型 |
| is_read | BOOLEAN | NOT NULL DEFAULT 0 | 是否已读 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**：
- `idx_notifications_user_id` ON notifications(user_id)
- `idx_notifications_is_read` ON notifications(user_id, is_read)

---

### 1.3 数据库关系图

```
users (1) ──────< (N) tasks
     │
     └──────< (N) categories
     │
     └──────< (N) notifications
     │
     └──────< (N) team_members >───── (1) teams (1) ──────< (N) team_tasks
                                                      │
                                                      └──────< (N) task_comments
```

---

## 二、API 接口详细定义

### 2.1 接口设计规范

- **基础路径**：`/api/v1`
- **认证方式**：JWT Token（Header: `Authorization: Bearer <token>`）
- **请求格式**：JSON
- **响应格式**：`{ "code": 200, "message": "success", "data": {...} }`

### 2.2 认证模块 API

#### 2.2.1 用户注册

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/auth/register` |
| **方法** | POST |
| **请求体** | `{ "username": "string", "email": "string", "password": "string", "full_name": "string?" }` |
| **成功响应** | `{ "code": 201, "message": "注册成功", "data": { "user_id": 1, "token": "jwt_token" } }` |
| **错误响应** | 400: 参数错误, 409: 用户名/邮箱已存在 |

#### 2.2.2 用户登录

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/auth/login` |
| **方法** | POST |
| **请求体** | `{ "email": "string", "password": "string" }` |
| **成功响应** | `{ "code": 200, "message": "登录成功", "data": { "user": {...}, "token": "jwt_token" } }` |
| **错误响应** | 401: 用户名或密码错误, 403: 账户未激活 |

#### 2.2.3 获取当前用户信息

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/auth/me` |
| **方法** | GET |
| **请求头** | Authorization: Bearer `<token>` |
| **成功响应** | `{ "code": 200, "data": { "id": 1, "username": "...", "email": "...", ... } }` |

#### 2.2.4 更新用户信息

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/auth/me` |
| **方法** | PUT/PATCH |
| **请求体** | `{ "full_name": "string?", "avatar_url": "string?" }` |
| **成功响应** | `{ "code": 200, "message": "更新成功", "data": {...} }` |

#### 2.2.5 修改密码

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/auth/password` |
| **方法** | PUT |
| **请求体** | `{ "old_password": "string", "new_password": "string" }` |
| **成功响应** | `{ "code": 200, "message": "密码修改成功" }` |

---

### 2.3 任务模块 API

#### 2.3.1 获取任务列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks` |
| **方法** | GET |
| **查询参数** | `status?: string`, `category_id?: integer`, `priority?: integer`, `due_date?: string`, `page?: integer`, `per_page?: integer`, `sort?: string`, `order?: asc|desc` |
| **成功响应** | `{ "code": 200, "data": { "tasks": [...], "total": 100, "page": 1, "per_page": 20 } }` |

#### 2.3.2 获取单个任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": { "id": 1, "title": "...", ... } }` |
| **错误响应** | 404: 任务不存在 |

#### 2.3.3 创建任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks` |
| **方法** | POST |
| **请求体** | `{ "title": "string (required)", "description": "string?", "category_id": "integer?", "priority": "integer?", "due_date": "datetime string?" }` |
| **成功响应** | `{ "code": 201, "message": "任务创建成功", "data": {...} }` |

#### 2.3.4 更新任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>` |
| **方法** | PUT/PATCH |
| **请求体** | `{ "title": "string?", "description": "string?", "category_id": "integer?", "priority": "integer?", "status": "string?", "due_date": "datetime string?" }` |
| **成功响应** | `{ "code": 200, "message": "任务更新成功", "data": {...} }` |

#### 2.3.5 删除任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>` |
| **方法** | DELETE |
| **成功响应** | `{ "code": 200, "message": "任务删除成功" }` |
| **错误响应** | 404: 任务不存在, 403: 无权限 |

#### 2.3.6 完成任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>/complete` |
| **方法** | POST |
| **成功响应** | `{ "code": 200, "message": "任务已完成", "data": {...} }` |

#### 2.3.7 获取任务统计

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/stats` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": { "total": 100, "pending": 50, "in_progress": 30, "completed": 20, "overdue": 5 } }` |

---

### 2.4 分类模块 API

#### 2.4.1 获取分类列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/categories` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": [{ "id": 1, "name": "工作", "color": "#3498db", ... }, ...] }` |

#### 2.4.2 创建分类

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/categories` |
| **方法** | POST |
| **请求体** | `{ "name": "string (required)", "color": "string (hex)?" }` |
| **成功响应** | `{ "code": 201, "data": {...} }` |

#### 2.4.3 更新分类

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/categories/<int:category_id>` |
| **方法** | PUT/PATCH |
| **请求体** | `{ "name": "string?", "color": "string?" }` |

#### 2.4.4 删除分类

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/categories/<int:category_id>` |
| **方法** | DELETE |
| **说明** | 删除分类后，该分类的任务 category_id 设为 NULL |

---

### 2.5 团队模块 API

#### 2.5.1 获取我的团队列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": [...] }` |

#### 2.5.2 创建团队

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams` |
| **方法** | POST |
| **请求体** | `{ "name": "string (required)", "description": "string?" }` |
| **成功响应** | `{ "code": 201, "data": {...}, "invite_code": "xxx" }` |

#### 2.5.3 获取团队详情

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": { "id": 1, "name": "...", "members": [...], ... } }` |

#### 2.5.4 加入团队

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/join` |
| **方法** | POST |
| **请求体** | `{ "invite_code": "string (required)" }` |
| **成功响应** | `{ "code": 200, "message": "加入成功" }` |

#### 2.5.5 获取团队成员列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/members` |
| **方法** | GET |
| **成功响应** | `{ "code": 200, "data": [...] }` |

#### 2.5.6 移除团队成员

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/members/<int:user_id>` |
| **方法** | DELETE |
| **说明** | 仅管理员可操作，不能移除所有者 |

---

### 2.6 团队任务模块 API

#### 2.6.1 获取团队任务列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/tasks` |
| **方法** | GET |
| **查询参数** | `status?: string`, `assignee_id?: integer`, `priority?: integer` |

#### 2.6.2 创建团队任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/tasks` |
| **方法** | POST |
| **请求体** | `{ "title": "string", "description": "string?", "assignee_id": "integer?", "category_id": "integer?", "priority": "integer?", "due_date": "datetime?" }` |

#### 2.6.3 更新团队任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/tasks/<int:task_id>` |
| **方法** | PUT/PATCH |

#### 2.6.4 删除团队任务

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/teams/<int:team_id>/tasks/<int:task_id>` |
| **方法** | DELETE |

---

### 2.7 通知模块 API

#### 2.7.1 获取通知列表

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/notifications` |
| **方法** | GET |
| **查询参数** | `is_read?: boolean`, `page?: integer`, `per_page?: integer` |
| **成功响应** | `{ "code": 200, "data": { "notifications": [...], "unread_count": 5 } }` |

#### 2.7.2 标记通知为已读

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/notifications/<int:notification_id>/read` |
| **方法** | POST |

#### 2.7.3 全部标记为已读

| 项目 | 内容 |
|------|------|
| **路径** `/api/v1/notifications/read-all` | |
| **方法** | POST |
| **成功响应** | `{ "code": 200, "message": "已全部标记为已读" }` |

---

### 2.8 评论模块 API

#### 2.8.1 获取任务评论

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>/comments` |
| **方法** | GET |
| **查询参数** | `task_type: personal | team` |

#### 2.8.2 添加评论

| 项目 | 内容 |
|------|------|
| **路径** | `/api/v1/tasks/<int:task_id>/comments` |
| **方法** | POST |
| **请求体** | `{ "task_type": "personal | team (required)", "content": "string (required)" }` |

---

## 三、核心算法和业务逻辑设计

### 3.1 认证模块

#### 3.1.1 密码哈希
```python
# 使用 bcrypt 进行密码哈希
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
```

#### 3.1.2 JWT Token 生成
```python
# Token 配置
TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30

def generate_token(user_id: int) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def generate_refresh_token(user_id: int) -> str:
    payload = {
        'user_id': user_id,
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')
```

### 3.2 任务排序算法

#### 3.2.1 默认排序规则
```
优先级: 升序（高优先级在前）> 创建时间: 降序（新建在前）> 截止日期: 升序（紧急在前）
```

#### 3.2.2 排序实现
```python
def get_task_sort_key(sort_by: str) -> callable:
    """返回排序函数"""
    sort_map = {
        'priority': lambda t: (t.priority, -t.created_at.timestamp(), t.due_date or datetime.max),
        'created_at': lambda t: t.created_at,
        'due_date': lambda t: t.due_date or datetime.max,
        'updated_at': lambda t: t.updated_at,
    }
    return sort_map.get(sort_by, lambda t: t.created_at)
```

### 3.3 任务状态流转

```
pending → in_progress → completed
    ↓         ↓            ↓
  archived  archived    archived

任意状态 → archived（归档）
```

#### 3.3.1 状态验证
```python
VALID_TRANSITIONS = {
    'pending': ['in_progress', 'completed', 'archived'],
    'in_progress': ['pending', 'completed', 'archived'],
    'completed': ['archived', 'pending'],  # 可重新打开
    'archived': ['pending']  # 从归档恢复
}

def validate_status_transition(current: str, new: str) -> bool:
    return new in VALID_TRANSITIONS.get(current, [])
```

### 3.4 权限验证逻辑

#### 3.4.1 任务访问权限
```python
def can_access_task(user_id: int, task: Task) -> bool:
    # 个人任务：只有创建者可以访问
    if task.user_id == user_id:
        return True
    
    # 团队任务：检查团队成员身份
    if task.team_id:
        return TeamMember.query.filter_by(
            team_id=task.team_id, 
            user_id=user_id
        ).first() is not None
    
    return False
```

#### 3.4.2 团队权限检查
```python
def get_user_team_role(user_id: int, team_id: int) -> str:
    """获取用户在团队中的角色"""
    member = TeamMember.query.filter_by(
        user_id=user_id, 
        team_id=team_id
    ).first()
    return member.role if member else None

def require_team_role(user_id: int, team_id: int, roles: list) -> bool:
    """检查用户是否具有要求的角色"""
    user_role = get_user_team_role(user_id, team_id)
    return user_role in roles
```

### 3.5 到期提醒逻辑

#### 3.5.1 提醒规则
- 任务截止前 24 小时：发送提醒通知
- 任务截止前 1 小时：发送紧急提醒
- 任务逾期未完成：每天发送一次逾期提醒

#### 3.5.2 提醒检查定时任务
```python
def check_due_tasks():
    """检查并发送到期提醒"""
    now = datetime.utcnow()
    
    # 检查 24 小时内的任务
    due_soon = Task.query.filter(
        Task.due_date.between(now, now + timedelta(hours=24)),
        Task.status.in_(['pending', 'in_progress']),
        Task.user_id == current_user.id
    ).all()
    
    # 发送通知
    for task in due_soon:
        hours_left = (task.due_date - now).total_seconds() / 3600
        notification_type = 'due_urgent' if hours_left <= 1 else 'due_soon'
        
        create_notification(
            user_id=task.user_id,
            type=notification_type,
            title='任务到期提醒',
            content=f"任务「{task.title}」{'即将到期' if hours_left > 1 else '将在1小时内到期'}",
            related_id=task.id,
            related_type='task'
        )
```

### 3.6 数据验证规则

| 字段 | 验证规则 |
|------|----------|
| username | 3-50字符，字母数字下划线 |
| email | 有效邮箱格式 |
| password | 至少6位字符 |
| task.title | 1-200字符，必填 |
| category.name | 1-50字符，必填 |
| team.name | 1-100字符，必填 |
| priority | 1-3 整数 |
| status | pending/in_progress/completed/archived |

---

## 四、前端组件结构和状态管理设计

### 4.1 前端技术栈

- **核心框架**：原生 JavaScript (ES6+)
- **样式**：CSS3 + CSS Variables
- **模板**：原生 Template Literals
- **HTTP 客户端**：Fetch API 封装
- **状态管理**：Simple Store Pattern（轻量级）

### 4.2 目录结构

```
web/
├── index.html              # 单页应用入口
├── static/
│   ├── css/
│   │   ├── main.css        # 主样式
│   │   ├── components.css  # 组件样式
│   │   └── variables.css   # CSS变量
│   ├── js/
│   │   ├── app.js          # 应用入口
│   │   ├── router.js       # 路由管理
│   │   ├── store.js        # 状态管理
│   │   ├── api.js          # API封装
│   │   ├── utils.js        # 工具函数
│   │   ├── components/     # UI组件
│   │   │   ├── navbar.js
│   │   │   ├── modal.js
│   │   │   ├── toast.js
│   │   │   ├── task-card.js
│   │   │   ├── task-form.js
│   │   │   └── category-badge.js
│   │   └── pages/          # 页面模块
│   │       ├── auth.js
│   │       ├── dashboard.js
│   │       ├── task-list.js
│   │       ├── task-detail.js
│   │       ├── teams.js
│   │       └── settings.js
│   └── images/
│       └── logo.svg
└── favicon.ico
```

### 4.3 状态管理设计

#### 4.3.1 Store 结构
```javascript
// 状态树结构
const initialState = {
    // 认证状态
    auth: {
        isAuthenticated: false,
        user: null,
        token: null,
        loading: false
    },
    
    // 任务数据
    tasks: {
        items: [],
        currentTask: null,
        filters: {
            status: '',
            category_id: null,
            priority: null,
            sort: 'priority',
            order: 'asc'
        },
        pagination: {
            page: 1,
            per_page: 20,
            total: 0
        },
        loading: false
    },
    
    // 分类数据
    categories: {
        items: [],
        loading: false
    },
    
    // 团队数据
    teams: {
        items: [],
        currentTeam: null,
        members: [],
        tasks: [],
        loading: false
    },
    
    // 通知数据
    notifications: {
        items: [],
        unreadCount: 0,
        loading: false
    },
    
    // UI状态
    ui: {
        sidebarOpen: true,
        modal: null,
        toasts: []
    }
};
```

#### 4.3.2 Store 方法
```javascript
class Store {
    constructor(initialState) {
        this.state = initialState;
        this.listeners = [];
    }
    
    getState() {
        return this.state;
    }
    
    setState(reducer) {
        this.state = reducer(this.state);
        this.notify();
    }
    
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }
    
    notify() {
        this.listeners.forEach(listener => listener(this.state));
    }
    
    // 派发动作
    dispatch(action) {
        switch (action.type) {
            case 'SET_USER':
                this.setState(state => ({
                    ...state,
                    auth: { ...state.auth, user: action.payload, isAuthenticated: true }
                }));
                break;
            case 'SET_TASKS':
                this.setState(state => ({
                    ...state,
                    tasks: { ...state.tasks, items: action.payload.tasks, pagination: action.payload.pagination }
                }));
                break;
            // ... 更多 action 处理
        }
    }
}
```

### 4.4 页面组件设计

#### 4.4.1 认证页面 (auth.js)
```
┌─────────────────────────────────────────┐
│              TaskFlow Login              │
├─────────────────────────────────────────┤
│                                         │
│         [Logo: TaskFlow]                │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ Email                           │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ Password                        │    │
│  └─────────────────────────────────┘    │
│                                         │
│  [     Login Button     ]               │
│                                         │
│  Don't have an account? Register        │
│                                         │
└─────────────────────────────────────────┘
```

#### 4.4.2 任务列表页面 (task-list.js)
```
┌─────────────────────────────────────────────────────────┐
│ Navbar: [Logo] [Dashboard] [Teams] [Notifications: 3]  │
├────────────┬────────────────────────────────────────────┤
│ Sidebar   │  Main Content                              │
│           │                                            │
│ Categories│  ┌─ Filter Bar ───────────────────────┐   │
│ ├ Work    │  │ [All] [Pending] [Done] | Sort ▼ |  │   │
│ ├ Personal│  └─────────────────────────────────────┘   │
│ └ Study   │                                            │
│           │  ┌─────────────────────────────────────┐   │
│ Priorities│  │ Task Card                           │   │
│ ├ High    │  │ [●] 完成项目文档   [Work] [High]   │   │
│ ├ Medium  │  │ Due: 2024-01-15     [Edit] [✓]     │   │
│ └ Low     │  └─────────────────────────────────────┘   │
│           │                                            │
│ [+ Add]   │  ┌─────────────────────────────────────┐   │
│           │  │ Task Card                           │   │
│           │  │ [●] 准备周报         [Personal]     │   │
│           │  │ Due: 2024-01-20     [Edit] [✓]     │   │
│           │  └─────────────────────────────────────┘   │
│           │                                            │
└────────────┴────────────────────────────────────────────┘
```

#### 4.4.3 组件事件流
```
用户点击
    ↓
Component Event Handler
    ↓
API Service Call (api.js)
    ↓
Fetch Request → Flask Backend
    ↓
Response ← Flask Backend
    ↓
Store.dispatch({ type, payload })
    ↓
State Update → Re-render Components
```

### 4.5 API 客户端封装

```javascript
// api.js
class APIClient {
    constructor(baseURL = '/api/v1') {
        this.baseURL = baseURL;
    }
    
    getToken() {
        return localStorage.getItem('token');
    }
    
    async request(endpoint, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` }),
            ...options.headers
        };
        
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            ...options,
            headers
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new APIError(result.message || 'Request failed', result.code);
        }
        
        return result;
    }
    
    // 快捷方法
    get(endpoint, params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`${endpoint}${query ? '?' + query : ''}`, { method: 'GET' });
    }
    
    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

export const api = new APIClient();
```

---

## 五、文件/模块目录结构规划

### 5.1 项目总体目录

```
taskflow/
├── .env                         # 环境变量配置
├── .env.example                 # 环境变量示例
├── requirements.txt             # Python依赖
├── run.py                       # 应用入口
├── instance/                    # SQLite数据库目录
│   └── taskflow.db
├── docs/                        # 文档目录
│   └── stages/
├── app/                         # 应用主目录
│   ├── __init__.py              # Flask应用工厂
│   ├── config.py                # 配置管理
│   ├── models/                  # 数据模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── task.py
│   │   ├── category.py
│   │   ├── team.py
│   │   ├── notification.py
│   │   └── comment.py
│   ├── schemas/                 # 数据验证
│   │   ├── __init__.py
│   │   ├── user_schema.py
│   │   ├── task_schema.py
│   │   ├── category_schema.py
│   │   ├── team_schema.py
│   │   └── notification_schema.py
│   ├── api/                     # API路由
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── tasks.py
│   │   ├── categories.py
│   │   ├── teams.py
│   │   ├── notifications.py
│   │   └── comments.py
│   ├── services/                # 业务逻辑
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── task_service.py
│   │   ├── notification_service.py
│   │   └── email_service.py
│   ├── utils/                   # 工具函数
│   │   ├── __init__.py
│   │   ├── decorators.py
│   │   ├── helpers.py
│   │   └── validators.py
│   └── extensions/              # 扩展
│       ├── __init__.py
│       ├── db.py
│       └── jwt.py
├── migrations/                  # 数据库迁移
└── web/                         # 前端静态文件
    ├── index.html
    ├── static/
    │   ├── css/
    │   ├── js/
    │   └── images/
    └── favicon.ico
```

### 5.2 核心模块说明

| 模块 | 路径 | 职责 |
|------|------|------|
| 应用工厂 | `app/__init__.py` | 创建Flask应用实例 |
| 数据模型 | `app/models/*` | 数据库表定义和ORM关系 |
| 数据验证 | `app/schemas/*` | 请求参数验证和序列化 |
| API路由 | `app/api/*` | RESTful接口定义 |
| 业务服务 | `app/services/*` | 核心业务逻辑处理 |
| 工具函数 | `app/utils/*` | 通用工具和装饰器 |
| 扩展 | `app/extensions/*` | Flask扩展初始化 |

---

## 六、模块拆分 JSON 输出

基于以上设计，按照功能域将项目拆分为以下模块：

```json
{
  "modules": [
    {
      "id": "core",
      "name": "核心基础设施",
      "description": "应用配置、数据库连接、认证扩展、工具函数等核心基础设施",
      "files": [
        "app/__init__.py",
        "app/config.py",
        "app/extensions/__init__.py",
        "app/extensions/db.py",
        "app/extensions/jwt.py",
        "app/utils/__init__.py",
        "app/utils/decorators.py",
        "app/utils/helpers.py",
        "app/utils/validators.py"
      ]
    },
    {
      "id": "user",
      "name": "用户认证模块",
      "description": "用户注册、登录、密码管理、JWT Token认证",
      "files": [
        "app/models/user.py",
        "app/schemas/user_schema.py",
        "app/api/auth.py",
        "app/services/auth_service.py"
      ]
    },
    {
      "id": "task",
      "name": "任务管理模块",
      "description": "个人任务CRUD、状态管理、排序筛选、评论功能",
      "files": [
        "app/models/task.py",
        "app/models/comment.py",
        "app/schemas/task_schema.py",
        "app/api/tasks.py",
        "app/api/comments.py",
        "app/services/task_service.py"
      ]
    },
    {
      "id": "category",
      "name": "分类管理模块",
      "description": "任务分类的创建、编辑、删除和颜色管理",
      "files": [
        "app/models/category.py",
        "app/schemas/category_schema.py",
        "app/api/categories.py"
      ]
    },
    {
      "id": "team",
      "name": "团队协作模块",
      "description": "团队创建、成员管理、邀请码、团队任务管理",
      "files": [
        "app/models/team.py",
        "app/schemas/team_schema.py",
        "app/api/teams.py",
        "app/services/notification_service.py"
      ]
    },
    {
      "id": "notification",
      "name": "通知系统模块",
      "description": "任务到期提醒、团队协作通知、已读未读状态管理",
      "files": [
        "app/models/notification.py",
        "app/schemas/notification_schema.py",
        "app/api/notifications.py",
        "app/services/email_service.py"
      ]
    },
    {
      "id": "frontend",
      "name": "前端界面模块",
      "description": "HTML页面、CSS样式、JavaScript组件和页面逻辑",
      "files": [
        "web/index.html",
        "web/static/css/main.css",
        "web/static/css/components.css",
        "web/static/css/variables.css",
        "web/static/js/app.js",
        "web/static/js/router.js",
        "web/static/js/store.js",
        "web/static/js/api.js",
        "web/static/js/utils.js"
      ]
    },
    {
      "id": "frontend-components",
      "name": "前端组件模块",
      "description": "可复用的UI组件和页面模块",
      "files": [
        "web/static/js/components/navbar.js",
        "web/static/js/components/modal.js",
        "web/static/js/components/toast.js",
        "web/static/js/components/task-card.js",
        "web/static/js/components/task-form.js",
        "web/static/js/components/category-badge.js",
        "web/static/js/pages/auth.js",
        "web/static/js/pages/dashboard.js",
        "web/static/js/pages/task-list.js",
        "web/static/js/pages/task-detail.js",
        "web/static/js/pages/teams.js",
        "web/static/js/pages/settings.js"
      ]
    }
  ]
}
```

---

## 七、技术决策说明

### 7.1 架构选择理由

| 决策项 | 选择方案 | 理由 |
|--------|----------|------|
| 前后端分离 | 单页应用(SPA) | 用户体验流畅，无需刷新 |
| 数据库 | SQLite | 轻量级、零配置、适合小项目 |
| 认证方式 | JWT Token | 无状态、易扩展、支持API |
| 表单验证 | 服务端验证 | 安全性优先，前端辅助验证 |
| 前端状态 | 中央Store | 状态集中管理，组件解耦 |
| 任务排序 | 后端分页+排序 | 大数据量时性能更好 |

### 7.2 性能优化策略

1. **数据库索引**：为常用查询字段建立索引
2. **分页加载**：列表数据默认分页，避免一次性加载过多
3. **缓存策略**：用户信息和分类数据可考虑缓存
4. **延迟加载**：前端路由按需加载

### 7.3 安全策略

1. **密码存储**：使用 bcrypt 哈希存储
2. **SQL注入**：使用 ORM 防止 SQL 注入
3. **XSS防护**：前端转义用户输入
4. **CORS配置**：限制可访问的域名
5. **请求限流**：防止恶意请求

---

**文档编制完成时间**：2024年  
**下一阶段**：编码实现
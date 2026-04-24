<think>
用户要求我作为开发工程师，完成"部署上线"阶段的工作。根据系统提示，我需要：

1. 环境要求（操作系统、运行时、依赖）
2. 部署步骤（从零到上线）
3. 配置文件模板（环境变量、配置项）
4. 健康检查方案
5. 回滚策略

让我分析项目的技术栈：
- 后端：Python Flask
- 数据库：SQLite
- 前端：HTML/CSS/JavaScript
- WSGI服务器：Gunicorn

我需要设计一个完整的部署方案，包括：

## 1. 环境要求
- 操作系统：Ubuntu 20.04+ 或 CentOS 8+
- Python版本：3.9+
- 系统依赖：gcc, python-dev, libpq-dev等
- Python依赖：见requirements.txt

## 2. 部署步骤
- 代码部署方式（Git克隆/上传）
- 虚拟环境创建
- 依赖安装
- 数据库初始化
- Gunicorn配置
- Nginx反向代理配置
- Systemd服务配置
- SSL证书配置（可选）

## 3. 配置文件模板
- .env 文件模板
- gunicorn.conf.py 配置
- nginx.conf 配置

## 4. 健康检查方案
- 端口检查
- API端点健康检查
- 数据库连接检查
- 进程检查

## 5. 回滚策略
- 代码回滚流程


- 数据库回滚方案
- 版本标记和快速回退操作

现在开始编写详细的部署方案。
</think>

# TaskFlow 任务管理系统 - 部署方案

**项目名称**：TaskFlow 任务管理系统  
**文档版本**：V1.0  
**编制角色**：开发工程师 / DevOps工程师  
**项目阶段**：部署上线  

---

## 1. 环境要求

### 1.1 操作系统要求

| 项目 | 要求 | 说明 |
|------|------|------|
| 推荐系统 | Ubuntu 20.04 LTS / 22.04 LTS | 长期支持版本，稳定可靠 |
| 备选系统 | CentOS 8+ / Debian 11+ | 需适当调整命令 |
| 系统架构 | x86_64 (AMD64) | 通用服务器架构 |
| 磁盘空间 | 至少 10GB | 包含系统、应用、数据 |
| 内存 | 至少 2GB | 生产环境建议 4GB+ |

### 1.2 运行时要求

```
Python 版本: >= 3.9
数据库: SQLite 3.x (内置)
Web服务器: Nginx (反向代理)
WSGI服务器: Gunicorn
```

### 1.3 系统依赖

```bash
# Ubuntu/Debian 系统
sudo apt-get update
sudo apt-get install -y python3.9 python3-pip python3-venv \
    build-essential libpq-dev gcc \
    nginx curl wget git

# CentOS/RHEL 系统
sudo yum install -y python39 python39-pip python3-devel \
    gcc postgresql-devel make nginx \
    curl wget git
```

### 1.4 Python 依赖

```
# requirements.txt
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-JWT-Extended==4.6.0
Flask-Cors==4.0.0
Werkzeug==3.0.1
SQLAlchemy==2.0.23
python-dotenv==1.0.0
bcrypt==4.1.2
gunicorn==21.2.0
```

---

## 2. 部署步骤（从零到上线）

### 2.1 部署架构图

```
                    ┌─────────────┐
                    │   用户终端   │
                    └──────┬──────┘
                           │ HTTPS (443)
                    ┌──────▼──────┐
                    │    Nginx    │
                    │  (反向代理)  │
                    └──────┬──────┘
                           │ Unix Socket / 127.0.0.1:8000
                    ┌──────▼──────┐
                    │  Gunicorn   │
                    │  (WSGI)     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐    │    ┌───────▼──────┐
       │   Flask     │    │    │   Static     │
       │  (App)     │◄───┴───►│  (CSS/JS)    │
       └──────┬──────┘         └──────────────┘
              │
       ┌──────▼──────┐
       │   SQLite    │
       │  Database   │
       └─────────────┘
```

### 2.2 详细部署步骤

#### 步骤 1：创建应用用户和目录

```bash
# 创建专用应用用户（安全最佳实践）
sudo useradd -m -s /bin/bash -r appuser || echo "User already exists"

# 创建应用目录
sudo mkdir -p /var/www/taskflow
sudo chown appuser:appuser /var/www/taskflow
cd /var/www/taskflow
```

#### 步骤 2：获取应用代码

```bash
# 方式 A: Git 克隆（推荐）
sudo -u appuser git clone <your-repo-url> /var/www/taskflow
cd /var/www/taskflow

# 方式 B: 手动上传
# 将项目文件上传到 /var/www/taskflow 目录
```

#### 步骤 3：创建虚拟环境

```bash
cd /var/www/taskflow

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip
```

#### 步骤 4：安装 Python 依赖

```bash
# 安装依赖
pip install -r requirements.txt

# 验证安装
pip list | grep -E "Flask|Gunicorn|SQLAlchemy"
```

#### 步骤 5：配置环境变量

```bash
# 创建环境配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```

详细配置见 **第 3 节：配置文件模板**

#### 步骤 6：初始化数据库

```bash
# 激活虚拟环境
source venv/bin/activate

# 初始化数据库（自动创建表）
flask db init  # 如果使用 Flask-Migrate
# 或
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database initialized!')"
```

#### 步骤 7：配置 Gunicorn

```bash
# 复制 Gunicorn 配置文件
cp config/gunicorn.conf.py.example config/gunicorn.conf.py

# 编辑配置（可选）
nano config/gunicorn.conf.py
```

#### 步骤 8：配置 Nginx 反向代理

```bash
# 复制 Nginx 配置
sudo cp config/nginx.taskflow.conf /etc/nginx/sites-available/taskflow

# 创建符号链接
sudo ln -s /etc/nginx/sites-available/taskflow /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 删除默认配置（可选）
sudo rm /etc/nginx/sites-enabled/default
```

#### 步骤 9：配置 Systemd 服务

```bash
# 复制服务文件
sudo cp config/taskflow.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start taskflow

# 设置开机自启
sudo systemctl enable taskflow

# 检查服务状态
sudo systemctl status taskflow
```

#### 步骤 10：配置防火墙

```bash
# 开放 HTTP/HTTPS 端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 开放 SSH 端口（如果未开放）
sudo ufw allow 22/tcp

# 启用防火墙
sudo ufw enable
```

#### 步骤 11：验证部署

```bash
# 检查服务状态
sudo systemctl status taskflow

# 检查端口监听
sudo netstat -tlnp | grep -E "nginx|gunicorn"

# 访问健康检查端点
curl http://localhost:8000/api/health
curl http://localhost/api/health

# 查看日志
sudo journalctl -u taskflow -f
```

---

## 3. 配置文件模板

### 3.1 环境变量配置 (.env)

```bash
# ===========================================
# TaskFlow 应用配置
# ===========================================

# Flask 配置
FLASK_APP=run.py
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=your-secure-random-secret-key-here-min-32-chars

# 数据库配置
DATABASE_URL=sqlite:///taskflow.db
# 生产环境建议使用 PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/taskflow

# JWT 配置
JWT_SECRET_KEY=your-jwt-secret-key-here-min-32-chars
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=2592000

# 服务器配置
HOST=127.0.0.1
PORT=8000
WORKERS=4
WORKER_CLASS=sync
WORKER_TIMEOUT=30

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/taskflow/app.log

# CORS 配置
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 3.2 Gunicorn 配置文件 (gunicorn.conf.py)

```python
# ===========================================
# Gunicorn 配置文件
# ===========================================

import multiprocessing
import os

# 服务器socket配置
bind = "127.0.0.1:8000"
# 或使用 Unix socket:
# bind = "unix:/var/run/taskflow.sock"

# Worker 进程配置
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# 日志配置
accesslog = "/var/log/taskflow/access.log"
errorlog = "/var/log/taskflow/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 进程命名
proc_name = "taskflow"

# 服务器机制
daemon = False
pidfile = "/var/run/taskflow.pid"

# 预加载应用代码（可减少内存使用）
preload_app = True

# 钩子函数
def on_starting(server):
    """服务器启动前调用"""
    print("Gunicorn is starting...")

def on_reload(server):
    """重新加载时调用"""
    print("Gunicorn is reloading...")

def when_ready(server):
    """服务器准备就绪时调用"""
    print(f"Gunicorn is ready. Listening on: {server.bind}")

def on_exit(server):
    """服务器退出时调用"""
    print("Gunicorn is shutting down...")

# 工作进程回调
def worker_int(worker):
    """Worker 进程被终止时的回调"""
    print(f"Worker {worker.pid} received INT signal")

def worker_abort(worker):
    """Worker 进程被中止时的回调"""
    print(f"Worker {worker.pid} received SIGABRT signal")
```

### 3.3 Nginx 配置文件 (nginx.taskflow.conf)

```nginx
# ===========================================
# TaskFlow Nginx 配置
# ===========================================

upstream taskflow_app {
    server 127.0.0.1:8000 fail_timeout=0;
    # 或使用 Unix socket:
    # server unix:/var/run/taskflow.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL 证书配置
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 静态文件目录
    root /var/www/taskflow;
    index index.html;

    # 访问日志
    access_log /var/log/nginx/taskflow_access.log;
    error_log /var/log/nginx/taskflow_error.log;

    # API 代理
    location /api/ {
        proxy_pass http://taskflow_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态文件（前端）
    location /static/ {
        alias /var/www/taskflow/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 前端页面
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

### 3.4 Systemd 服务文件 (taskflow.service)

```ini
# ===========================================
# TaskFlow Systemd 服务配置
# ===========================================

[Unit]
Description=TaskFlow Task Management Application
After=network.target postgresql.service
Wants=network-online.target

[Service]
Type=notify
User=appuser
Group=appuser
WorkingDirectory=/var/www/taskflow
Environment="PATH=/var/www/taskflow/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/var/www/taskflow/venv/bin/gunicorn -c /var/www/taskflow/config/gunicorn.conf.py run:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

# 安全加固
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/www/taskflow /var/log/taskflow

[Install]
WantedBy=multi-user.target
```

---

## 4. 健康检查方案

### 4.1 健康检查端点

在 `app/routes/main.py` 中添加健康检查端点：

```python
@app.route('/api/health')
def health_check():
    """健康检查端点"""
    import os
    from datetime import datetime
    from flask import jsonify
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "taskflow",
        "version": "1.0.0"
    }
    
    # 检查数据库连接
    try:
        from app import db
        db.session.execute(db.text('SELECT 1'))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = f"error: {str(e)}"
    
    # 检查磁盘空间
    try:
        import shutil
        stats = shutil.disk_usage("/")
        health_status["disk"] = {
            "total": f"{stats.total / (1024**3):.2f} GB",
            "free": f"{stats.free / (1024**3):.2f} GB",
            "percent": f"{(stats.used / stats.total) * 100:.1f}%"
        }
    except Exception as e:
        health_status["disk"] = f"error: {str(e)}"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code
```

### 4.2 健康检查脚本

```bash
#!/bin/bash
# health_check.sh - 健康检查脚本

set -e

# 配置
API_URL="http://127.0.0.1:8000/api/health"
MAX_RETRIES=3
RETRY_DELAY=2

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "TaskFlow 健康检查"
echo "========================================"

# 检查进程
echo -n "检查 Gunicorn 进程... "
if pgrep -f "gunicorn.*taskflow" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAIL${NC} - Gunicorn 进程未运行"
    exit 1
fi

# 检查端口
echo -n "检查端口 8000... "
if netstat -tuln | grep -q ":8000 "; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAIL${NC} - 端口 8000 未监听"
    exit 1
fi

# 检查数据库
echo -n "检查数据库文件... "
if [ -f "/var/www/taskflow/taskflow.db" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAIL${NC} - 数据库文件不存在"
    exit 1
fi

# 检查 API 响应
echo -n "检查 API 健康端点... "
for i in $(seq 1 $MAX_RETRIES); do
    if response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL 2>/dev/null); then
        if [ "$response" = "200" ]; then
            echo -e "${GREEN}OK${NC} (HTTP $response)"
            break
        fi
    fi
    
    if [ $i -lt $MAX_RETRIES ]; then
        echo -e "${YELLOW}重试中... ($i/$MAX_RETRIES)${NC}"
        sleep $RETRY_DELAY
    else
        echo -e "${RED}FAIL${NC} - API 无响应"
        exit 1
    fi
done

# 检查日志目录
echo -n "检查日志目录... "
if [ -d "/var/log/taskflow" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARN${NC} - 日志目录不存在"
fi

echo "========================================"
echo -e "${GREEN}所有检查通过!${NC}"
echo "========================================"
exit 0
```

### 4.3 监控检查点

| 检查项 | 检查方法 | 阈值 | 告警级别 |
|--------|----------|------|----------|
| API 响应时间 | curl 请求 | > 2s 告警 | Warning |
| HTTP 状态码 | 端点检查 | 非 200 告警 | Critical |
| 磁盘使用率 | df 命令 | > 85% 告警 | Warning |
| 内存使用率 | free 命令 | > 90% 告警 | Critical |
| CPU 使用率 | top 命令 | > 80% 持续 5min | Warning |
| 数据库连接 | SQL 查询 | 失败告警 | Critical |
| 进程状态 | pgrep | 未运行告警 | Critical |

### 4.4 Systemd 定时健康检查

```bash
# 创建定时任务
sudo crontab -e

# 添加以下行（每5分钟检查一次）
*/5 * * * * /var/www/taskflow/scripts/health_check.sh >> /var/log/taskflow/health.log 2>&1
```

---

## 5. 回滚策略

### 5.1 回滚流程图

```
                    ┌─────────────────┐
                    │   检测到故障    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  评估故障影响   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼─────────┐   │   ┌──────────▼──────────┐
    │    API/页面异常   │   │   │    数据库故障       │
    └─────────┬─────────┘   │   └──────────┬──────────┘
              │              │              │
    ┌─────────▼─────────┐   │   ┌──────────▼──────────┐
    │  回滚代码版本     │   │   │   恢复数据库备份    │
    └─────────┬─────────┘   │   └──────────┬──────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │   验证服务      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    通知团队     │
                    └─────────────────┘
```

### 5.2 代码回滚

#### 方案 A：Git 回滚（推荐）

```bash
# 进入应用目录
cd /var/www/taskflow

# 查看版本标签
git tag -l

# 查看提交历史
git log --oneline -20

# 回滚到上一个版本
git revert HEAD  # 创建回滚提交
# 或
git checkout v1.0.0 .  # 切换到指定标签

# 安装依赖（如果有变化）
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
sudo systemctl restart taskflow

# 验证
curl http://localhost/api/health
```

#### 方案 B：文件备份回滚

```bash
# 备份当前版本
sudo cp -r /var/www/taskflow /var/www/taskflow.backup.$(date +%Y%m%d_%H%M%S)

# 恢复上一个版本
sudo rm -rf /var/www/taskflow
sudo cp -r /var/www/taskflow_backup /var/www/taskflow
sudo chown -R appuser:appuser /var/www/taskflow

# 重启服务
sudo systemctl restart taskflow
```

### 5.3 数据库回滚

#### 自动备份策略

```bash
# 每天凌晨 3 点执行数据库备份
sudo crontab -e

# 添加以下行
0 3 * * * /var/www/taskflow/scripts/backup_db.sh
```

#### 备份脚本 (backup_db.sh)

```bash
#!/bin/bash
# 数据库备份脚本

BACKUP_DIR="/var/backups/taskflow"
DB_PATH="/var/www/taskflow/taskflow.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 压缩备份
cp $DB_PATH $BACKUP_DIR/taskflow_$TIMESTAMP.db
gzip $BACKUP_DIR/taskflow_$TIMESTAMP.db

# 保留最近 7 天的备份
find $BACKUP_DIR -name "taskflow_*.db.gz" -mtime +7 -delete

echo "Database backup completed: taskflow_$TIMESTAMP.db.gz"
```

#### 恢复数据库

```bash
# 停止服务
sudo systemctl stop taskflow

# 恢复数据库
sudo cp /var/backups/taskflow/taskflow_YYYYMMDD_HHMMSS.db.gz /tmp/
sudo gunzip /tmp/taskflow_YYYYMMDD_HHMMSS.db.gz
sudo cp /tmp/taskflow_YYYYMMDD_HHMMSS.db /var/www/taskflow/taskflow.db
sudo chown appuser:appuser /var/www/taskflow/taskflow.db

# 启动服务
sudo systemctl start taskflow

# 验证
curl http://localhost/api/health
```

### 5.4 快速回滚脚本

```bash
#!/bin/bash
# rollback.sh - 一键回滚脚本

set -e

BACKUP_DIR="/var/www/taskflow_backup"
CURRENT_VER=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "TaskFlow 紧急回滚脚本"
echo "========================================"

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <backup-version>"
    echo "可用备份:"
    ls -1 $BACKUP_DIR/ 2>/dev/null || echo "无备份"
    exit 1
fi

BACKUP_VERSION=$1

# 停止服务
echo "停止服务..."
sudo systemctl stop taskflow

# 备份当前版本
echo "备份当前版本..."
sudo mkdir -p $BACKUP_DIR
sudo cp -r /var/www/taskflow $BACKUP_DIR/taskflow_$CURRENT_VER

# 恢复指定版本
echo "恢复版本: $BACKUP_VERSION"
sudo rm -rf /var/www/taskflow
sudo cp -r $BACKUP_DIR/$BACKUP_VERSION /var/www/taskflow
sudo chown -R appuser:appuser /var/www/taskflow

# 重新安装依赖
echo "重新安装依赖..."
cd /var/www/taskflow
source venv/bin/activate
pip install -r requirements.txt

# 启动服务
echo "启动服务..."
sudo systemctl start taskflow

# 等待服务启动
sleep 3

# 验证
echo "验证服务..."
if curl -s http://localhost/api/health | grep -q "healthy"; then
    echo -e "${GREEN}回滚成功!${NC}"
else
    echo -e "${RED}警告: 服务可能未正常启动${NC}"
    sudo systemctl status taskflow
fi

echo "========================================"
echo "回滚完成!"
echo "========================================"
```

### 5.5 回滚检查清单

| 检查项 | 说明 | 状态 |
|--------|------|------|
| 服务状态 | `systemctl status taskflow` 正常运行 | ⬜ |
| API 响应 | `curl /api/health` 返回 200 | ⬜ |
| 登录功能 | 用户可以正常登录 | ⬜ |
| 核心功能 | 任务 CRUD 功能正常 | ⬜ |
| 日志检查 | 无 ERROR 级别日志 | ⬜ |
| 通知团队 | 发送回滚通知 | ⬜ |

### 5.6 版本标记策略

```bash
# 在每次部署时创建版本标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 查看历史版本
git tag -l
git log --oneline --graph --decorate --all
```

---

## 附录：快速部署命令汇总

```bash
# 一键部署脚本
#!/bin/bash

set -e

echo "开始部署 TaskFlow..."

# 1. 安装系统依赖
apt-get update && apt-get install -y python3 python3-pip python3-venv nginx git

# 2. 创建目录
mkdir -p /var/www/taskflow /var/log/taskflow
useradd -m -s /bin/bash appuser || true
chown -R appuser:appuser /var/www/taskflow

# 3. 克隆代码
cd /var/www/taskflow
git clone <repo-url> .

# 4. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. 配置
cp .env.example .env
# 编辑 .env 文件...

# 6. 初始化数据库
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# 7. 配置服务
cp config/taskflow.service /etc/systemd/system/
cp config/nginx.taskflow.conf /etc/nginx/sites-available/taskflow
ln -s /etc/nginx/sites-available/taskflow /etc/nginx/sites-enabled/
nginx -t

# 8. 启动
systemctl daemon-reload
systemctl start taskflow
systemctl enable taskflow

echo "部署完成!"
```

---

**文档结束**

如有疑问或需要进一步优化，请随时告知！
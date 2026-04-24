/**
 * TaskFlow 任务管理系统 - 主 JavaScript 文件
 * 处理通用功能：认证、通知、模态框等
 */

// ===== 全局配置 =====
const API_BASE_URL = '/api';

// ===== 认证工具 =====
const Auth = {
    // 获取 Token
    getToken: () => localStorage.getItem('access_token'),
    
    // 获取用户信息
    getUser: () => {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },
    
    // 设置认证信息
    setAuth: (token, refreshToken, user) => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('refresh_token', refreshToken);
        localStorage.setItem('user', JSON.stringify(user));
    },
    
    // 清除认证信息
    clearAuth: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
    },
    
    // 检查是否已登录
    isLoggedIn: () => !!localStorage.getItem('access_token'),
    
    // 刷新 Token
    refreshToken: async () => {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) return false;
        
        try {
            const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${refreshToken}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Token 刷新失败:', error);
            return false;
        }
    }
};

// ===== API 请求工具 =====
const API = {
    // 通用请求方法
    async request(url, options = {}) {
        const token = Auth.getToken();
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` })
            }
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        try {
            const response = await fetch(url, mergedOptions);
            
            // 处理 401 未授权
            if (response.status === 401) {
                // 尝试刷新 Token
                const refreshed = await Auth.refreshToken();
                if (refreshed) {
                    // 重新发送请求
                    const newToken = Auth.getToken();
                    mergedOptions.headers['Authorization'] = `Bearer ${newToken}`;
                    return this.request(url, mergedOptions);
                } else {
                    // 刷新失败，清除认证信息并跳转登录
                    Auth.clearAuth();
                    window.location.href = '/login';
                    return null;
                }
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw { status: response.status, ...data };
            }
            
            return data;
        } catch (error) {
            console.error('API 请求错误:', error);
            throw error;
        }
    },
    
    // GET 请求
    get(url) {
        return this.request(url, { method: 'GET' });
    },
    
    // POST 请求
    post(url, body) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },
    
    // PUT 请求
    put(url, body) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    },
    
    // DELETE 请求
    delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};

// ===== 通知工具 =====
const Notification = {
    container: null,
    
    // 初始化容器
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'notification-container';
            document.body.appendChild(this.container);
        }
    },
    
    // 显示通知
    show(message, type = 'info', duration = 3000) {
        this.init();
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div>
                <strong>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</strong>
                <span>${message}</span>
            </div>
        `;
        
        this.container.appendChild(notification);
        
        // 自动关闭
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    },
    
    success(message) {
        this.show(message, 'success');
    },
    
    error(message) {
        this.show(message, 'error', 5000);
    },
    
    warning(message) {
        this.show(message, 'warning', 4000);
    },
    
    info(message) {
        this.show(message, 'info');
    }
};

// ===== 模态框工具 =====
const Modal = {
    // 显示模态框
    show(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    },
    
    // 隐藏模态框
    hide(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    },
    
    // 隐藏所有模态框
    hideAll() {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
};

// ===== 日期格式化 =====
const DateUtils = {
    format(dateStr, format = 'YYYY-MM-DD HH:mm') {
        if (!dateStr) return '-';
        
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return '-';
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        
        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes);
    },
    
    relative(dateStr) {
        if (!dateStr) return '-';
        
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return '-';
        
        const now = new Date();
        const diff = now - date;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);
        
        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes}分钟前`;
        if (hours < 24) return `${hours}小时前`;
        if (days < 7) return `${days}天前`;
        
        return this.format(dateStr, 'YYYY-MM-DD');
    },
    
    isOverdue(dateStr) {
        if (!dateStr) return false;
        return new Date(dateStr) < new Date();
    }
};

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    // 绑定模态框关闭事件
    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                Modal.hide(modal.id);
            }
        });
    });
    
    // 绑定 ESC 关闭模态框
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            Modal.hideAll();
        }
    });
    
    // 检查登录状态
    const currentPath = window.location.pathname;
    if (!Auth.isLoggedIn() && !currentPath.includes('/login') && !currentPath.includes('/register')) {
        window.location.href = '/login';
    }
});

// ===== 导出 =====
window.TaskFlow = {
    Auth,
    API,
    Notification,
    Modal,
    DateUtils,
    API_BASE_URL
};

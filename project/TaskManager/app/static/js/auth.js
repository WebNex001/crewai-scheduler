/**
 * TaskFlow 任务管理系统 - 认证 JavaScript
 * 处理用户登录、注册等功能
 */

// ===== 登录 =====
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        TaskFlow.Notification.error('请填写用户名和密码');
        return;
    }
    
    try {
        const response = await fetch(`${TaskFlow.API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw { message: data.error || '登录失败' };
        }
        
        // 保存认证信息
        TaskFlow.Auth.setAuth(
            data.access_token,
            data.refresh_token,
            data.user
        );
        
        TaskFlow.Notification.success('登录成功');
        
        // 跳转到首页
        setTimeout(() => {
            window.location.href = '/';
        }, 500);
        
    } catch (error) {
        TaskFlow.Notification.error(error.message || '登录失败，请重试');
    }
}

// ===== 注册 =====
async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const fullName = document.getElementById('fullName').value.trim();
    
    // 验证
    if (!username || !email || !password) {
        TaskFlow.Notification.error('请填写必填字段');
        return;
    }
    
    if (password.length < 6) {
        TaskFlow.Notification.error('密码长度至少6位');
        return;
    }
    
    if (password !== confirmPassword) {
        TaskFlow.Notification.error('两次输入的密码不一致');
        return;
    }
    
    try {
        const response = await fetch(`${TaskFlow.API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                email,
                password,
                full_name: fullName || undefined
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw { message: data.error || '注册失败' };
        }
        
        TaskFlow.Notification.success('注册成功，请登录');
        
        // 跳转到登录页
        setTimeout(() => {
            window.location.href = '/login';
        }, 1000);
        
    } catch (error) {
        TaskFlow.Notification.error(error.message || '注册失败，请重试');
    }
}

// ===== 登出 =====
async function handleLogout() {
    try {
        await fetch(`${TaskFlow.API_BASE_URL}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${TaskFlow.Auth.getToken()}`
            }
        });
    } catch (error) {
        // 忽略错误
    }
    
    TaskFlow.Auth.clearAuth();
    TaskFlow.Notification.success('已退出登录');
    
    setTimeout(() => {
        window.location.href = '/login';
    }, 500);
}

// ===== 初始化登录页面 =====
function initLoginPage() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
}

// ===== 初始化注册页面 =====
function initRegisterPage() {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
}

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    initLoginPage();
    initRegisterPage();
});

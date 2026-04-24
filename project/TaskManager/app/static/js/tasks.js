/**
 * TaskFlow 任务管理系统 - 任务 JavaScript
 * 处理任务列表、创建、编辑等功能
 */

// ===== 任务状态管理 =====
let currentFilters = {
    page: 1,
    status: '',
    priority: '',
    category_id: '',
    search: ''
};

// ===== 加载任务列表 =====
async function loadTasks() {
    try {
        // 构建查询参数
        const params = new URLSearchParams();
        if (currentFilters.page) params.append('page', currentFilters.page);
        if (currentFilters.status) params.append('status', currentFilters.status);
        if (currentFilters.priority) params.append('priority', currentFilters.priority);
        if (currentFilters.category_id) params.append('category_id', currentFilters.category_id);
        if (currentFilters.search) params.append('search', currentFilters.search);
        
        const data = await TaskFlow.API.get(`${TaskFlow.API_BASE_URL}/tasks?${params}`);
        
        renderTaskList(data.tasks || []);
        renderPagination(data.pagination);
        updateStats(data.tasks || []);
        
    } catch (error) {
        TaskFlow.Notification.error('加载任务失败');
        console.error(error);
    }
}

// ===== 渲染任务列表 =====
function renderTaskList(tasks) {
    const container = document.getElementById('taskList');
    if (!container) return;
    
    if (tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
                <h3>暂无任务</h3>
                <p>点击上方"新建任务"按钮创建您的第一个任务</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = tasks.map(task => {
        const categoryColor = task.category ? task.category.color : '#3498db';
        const categoryName = task.category ? task.category.name : '';
        const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'completed';
        
        return `
            <div class="task-item" onclick="showTaskDetail(${task.id})">
                <div class="task-header">
                    <span class="task-title">${escapeHtml(task.title)}</span>
                    <div class="task-actions">
                        <button class="btn btn-sm btn-icon" onclick="event.stopPropagation(); editTask(${task.id})" title="编辑">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                        </button>
                        <button class="btn btn-sm btn-icon" onclick="event.stopPropagation(); deleteTask(${task.id})" title="删除">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                        </button>
                    </div>
                </div>
                ${task.description ? `<p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 8px;">${escapeHtml(task.description.substring(0, 100))}</p>` : ''}
                <div class="task-meta">
                    <span class="priority-${task.priority}">● ${getPriorityText(task.priority)}</span>
                    <span class="status-${task.status}">● ${getStatusText(task.status)}</span>
                    ${task.due_date ? `<span class="${isOverdue ? 'text-danger' : ''}">📅 ${TaskFlow.DateUtils.format(task.due_date)}</span>` : ''}
                    ${categoryName ? `<span class="task-category" style="background-color: ${categoryColor}">${escapeHtml(categoryName)}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ===== 渲染分页 =====
function renderPagination(pagination) {
    const container = document.getElementById('pagination');
    if (!container || !pagination) return;
    
    if (pagination.pages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // 上一页
    html += `<button ${pagination.has_prev ? '' : 'disabled'} onclick="goToPage(${pagination.page - 1})">上一页</button>`;
    
    // 页码
    for (let i = 1; i <= pagination.pages; i++) {
        if (i === 1 || i === pagination.pages || (i >= pagination.page - 2 && i <= pagination.page + 2)) {
            html += `<button class="${i === pagination.page ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        } else if (i === pagination.page - 3 || i === pagination.page + 3) {
            html += `<button disabled>...</button>`;
        }
    }
    
    // 下一页
    html += `<button ${pagination.has_next ? '' : 'disabled'} onclick="goToPage(${pagination.page + 1})">下一页</button>`;
    
    container.innerHTML = html;
}

// ===== 更新统计 =====
function updateStats(tasks) {
    const stats = {
        total: tasks.length,
        pending: 0,
        in_progress: 0,
        completed: 0,
        overdue: 0
    };
    
    tasks.forEach(task => {
        if (task.status === 'pending') stats.pending++;
        if (task.status === 'in_progress') stats.in_progress++;
        if (task.status === 'completed') stats.completed++;
        if (task.due_date && new Date(task.due_date) < new Date() && task.status !== 'completed') {
            stats.overdue++;
        }
    });
    
    // 更新统计显示
    const elements = ['total', 'pending', 'in_progress', 'completed', 'overdue'];
    elements.forEach(key => {
        const el = document.getElementById(`stat-${key}`);
        if (el) el.textContent = stats[key];
    });
}

// ===== 创建任务 =====
async function createTask(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    const taskData = {
        title: formData.get('title'),
        description: formData.get('description') || undefined,
        priority: formData.get('priority') || 'medium',
        due_date: formData.get('due_date') || undefined,
        category_id: formData.get('category_id') ? parseInt(formData.get('category_id')) : undefined,
        is_reminder_set: formData.get('reminder') === 'on'
    };
    
    if (!taskData.title) {
        TaskFlow.Notification.error('请填写任务标题');
        return;
    }
    
    try {
        await TaskFlow.API.post(`${TaskFlow.API_BASE_URL}/tasks`, taskData);
        
        TaskFlow.Notification.success('任务创建成功');
        TaskFlow.Modal.hide('taskModal');
        form.reset();
        loadTasks();
        
    } catch (error) {
        TaskFlow.Notification.error(error.message || '创建任务失败');
    }
}

// ===== 编辑任务 =====
async function editTask(taskId) {
    try {
        const data = await TaskFlow.API.get(`${TaskFlow.API_BASE_URL}/tasks/${taskId}`);
        const task = data.task;
        
        // 填充表单
        document.getElementById('taskId').value = task.id;
        document.getElementById('taskTitle').value = task.title;
        document.getElementById('taskDescription').value = task.description || '';
        document.getElementById('taskPriority').value = task.priority;
        document.getElementById('taskStatus').value = task.status;
        document.getElementById('taskCategory').value = task.category_id || '';
        
        if (task.due_date) {
            const date = new Date(task.due_date);
            document.getElementById('taskDueDate').value = date.toISOString().slice(0, 16);
        }
        
        document.getElementById('taskReminder').checked = task.is_reminder_set;
        
        // 更新按钮文字
        document.getElementById('taskSubmitBtn').textContent = '保存修改';
        
        // 显示模态框
        TaskFlow.Modal.show('taskModal');
        
    } catch (error) {
        TaskFlow.Notification.error('加载任务失败');
    }
}

// ===== 保存任务（创建或更新） =====
async function saveTask(event) {
    event.preventDefault();
    
    const taskId = document.getElementById('taskId').value;
    const form = event.target;
    const formData = new FormData(form);
    
    const taskData = {
        title: formData.get('title'),
        description: formData.get('description') || undefined,
        priority: formData.get('priority') || 'medium',
        status: formData.get('status') || 'pending',
        category_id: formData.get('category_id') ? parseInt(formData.get('category_id')) : undefined,
        is_reminder_set: formData.get('reminder') === 'on'
    };
    
    const dueDate = formData.get('due_date');
    if (dueDate) {
        taskData.due_date = new Date(dueDate).toISOString();
    }
    
    try {
        if (taskId) {
            // 更新
            await TaskFlow.API.put(`${TaskFlow.API_BASE_URL}/tasks/${taskId}`, taskData);
            TaskFlow.Notification.success('任务更新成功');
        } else {
            // 创建
            await TaskFlow.API.post(`${TaskFlow.API_BASE_URL}/tasks`, taskData);
            TaskFlow.Notification.success('任务创建成功');
        }
        
        TaskFlow.Modal.hide('taskModal');
        form.reset();
        document.getElementById('taskId').value = '';
        document.getElementById('taskSubmitBtn').textContent = '创建任务';
        loadTasks();
        
    } catch (error) {
        TaskFlow.Notification.error(error.message || '保存任务失败');
    }
}

// ===== 删除任务 =====
async function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) return;
    
    try {
        await TaskFlow.API.delete(`${TaskFlow.API_BASE_URL}/tasks/${taskId}`);
        
        TaskFlow.Notification.success('任务删除成功');
        loadTasks();
        
    } catch (error) {
        TaskFlow.Notification.error('删除任务失败');
    }
}

// ===== 查看任务详情 =====
async function showTaskDetail(taskId) {
    try {
        const data = await TaskFlow.API.get(`${TaskFlow.API_BASE_URL}/tasks/${taskId}`);
        const task = data.task;
        
        // 填充详情
        document.getElementById('detailTitle').textContent = task.title;
        document.getElementById('detailDescription').textContent = task.description || '无描述';
        document.getElementById('detailPriority').textContent = getPriorityText(task.priority);
        document.getElementById('detailStatus').textContent = getStatusText(task.status);
        document.getElementById('detailDueDate').textContent = task.due_date ? TaskFlow.DateUtils.format(task.due_date) : '未设置';
        
        if (task.category) {
            document.getElementById('detailCategory').innerHTML = `<span class="task-category" style="background-color: ${task.category.color}">${task.category.name}</span>`;
        } else {
            document.getElementById('detailCategory').textContent = '无分类';
        }
        
        // 显示模态框
        TaskFlow.Modal.show('taskDetailModal');
        
    } catch (error) {
        TaskFlow.Notification.error('加载任务详情失败');
    }
}

// ===== 筛选任务 =====
function filterTasks() {
    currentFilters.page = 1;
    currentFilters.status = document.getElementById('filterStatus').value;
    currentFilters.priority = document.getElementById('filterPriority').value;
    currentFilters.category_id = document.getElementById('filterCategory').value;
    loadTasks();
}

// ===== 搜索任务 =====
function searchTasks() {
    currentFilters.search = document.getElementById('searchInput').value;
    currentFilters.page = 1;
    loadTasks();
}

// ===== 翻页 =====
function goToPage(page) {
    currentFilters.page = page;
    loadTasks();
}

// ===== 加载分类 =====
async function loadCategories() {
    try {
        const data = await TaskFlow.API.get(`${TaskFlow.API_BASE_URL}/categories`);
        
        // 更新筛选下拉框
        const filterCategory = document.getElementById('filterCategory');
        if (filterCategory) {
            filterCategory.innerHTML = '<option value="">全部分类</option>' + 
                data.categories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
        }
        
        // 更新任务表单下拉框
        const taskCategory = document.getElementById('taskCategory');
        if (taskCategory) {
            taskCategory.innerHTML = '<option value="">无分类</option>' + 
                data.categories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
        }
        
    } catch (error) {
        console.error('加载分类失败:', error);
    }
}

// ===== 工具函数 =====
function getPriorityText(priority) {
    const map = {
        'low': '低',
        'medium': '中',
        'high': '高',
        'urgent': '紧急'
    };
    return map[priority] || priority;
}

function getStatusText(status) {
    const map = {
        'pending': '待处理',
        'in_progress': '进行中',
        'completed': '已完成',
        'cancelled': '已取消'
    };
    return map[status] || status;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    // 绑定筛选事件
    document.getElementById('filterStatus')?.addEventListener('change', filterTasks);
    document.getElementById('filterPriority')?.addEventListener('change', filterTasks);
    document.getElementById('filterCategory')?.addEventListener('change', filterTasks);
    document.getElementById('searchBtn')?.addEventListener('click', searchTasks);
    document.getElementById('searchInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchTasks();
    });
    
    // 绑定任务表单
    document.getElementById('taskForm')?.addEventListener('submit', saveTask);
    
    // 加载初始数据
    loadCategories();
    loadTasks();
});

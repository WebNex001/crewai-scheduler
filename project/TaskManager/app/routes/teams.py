"""
TaskFlow 任务管理系统 - 团队路由
处理团队协作相关功能
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Team, TeamMember, Task, User, Notification

# 创建团队蓝图
teams_bp = Blueprint('teams', __name__)


@teams_bp.route('', methods=['GET'])
@jwt_required()
def get_teams():
    """获取当前用户所属的团队列表
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        teams: 团队列表
    """
    current_user_id = get_jwt_identity()
    
    # 获取用户所属的团队
    team_ids = db.session.query(TeamMember.team_id).filter_by(user_id=current_user_id)
    teams = Team.query.filter(Team.id.in_(team_ids)).all()
    
    return jsonify({
        'teams': [t.to_dict(include_members=True) for t in teams]
    }), 200


@teams_bp.route('/<int:team_id>', methods=['GET'])
@jwt_required()
def get_team(team_id):
    """获取团队详情
    
    路径参数:
        team_id: 团队ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        team: 团队详情
    
    错误响应:
        403: 无权限访问
        404: 团队不存在
    """
    current_user_id = get_jwt_identity()
    
    team = Team.query.get(team_id)
    
    if not team:
        return jsonify({'error': '团队不存在'}), 404
    
    # 检查是否是团队成员
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user_id
    ).first()
    
    if not membership:
        return jsonify({'error': '您不是该团队成员'}), 403
    
    return jsonify({
        'team': team.to_dict(include_members=True)
    }), 200


@teams_bp.route('', methods=['POST'])
@jwt_required()
def create_team():
    """创建新团队
    
    请求体:
        name: 团队名称（必填）
        description: 团队描述（可选）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 创建成功消息
        team: 新建的团队
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '团队名称不能为空'}), 400
    
    if len(name) > 100:
        return jsonify({'error': '团队名称不能超过100个字符'}), 400
    
    # 创建团队
    team = Team(
        name=name,
        description=data.get('description', '').strip() or None,
        owner_id=current_user_id
    )
    
    db.session.add(team)
    db.session.flush()  # 获取团队ID
    
    # 创建者自动成为团队成员（所有者角色）
    membership = TeamMember(
        team_id=team.id,
        user_id=current_user_id,
        role='owner'
    )
    db.session.add(membership)
    db.session.commit()
    
    return jsonify({
        'message': '团队创建成功',
        'team': team.to_dict(include_members=True)
    }), 201


@teams_bp.route('/<int:team_id>', methods=['PUT'])
@jwt_required()
def update_team(team_id):
    """更新团队信息
    
    路径参数:
        team_id: 团队ID
    
    请求体:
        name: 团队名称（可选）
        description: 团队描述（可选）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 更新成功消息
        team: 更新后的团队
    
    错误响应:
        403: 无权限修改
        404: 团队不存在
    """
    current_user_id = get_jwt_identity()
    
    team = Team.query.get(team_id)
    
    if not team:
        return jsonify({'error': '团队不存在'}), 404
    
    # 检查是否是团队所有者
    if team.owner_id != current_user_id:
        return jsonify({'error': '只有团队所有者可以修改团队信息'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({'error': '团队名称不能为空'}), 400
        if len(name) > 100:
            return jsonify({'error': '团队名称不能超过100个字符'}), 400
        team.name = name
    
    if 'description' in data:
        team.description = data['description'].strip() if data['description'] else None
    
    db.session.commit()
    
    return jsonify({
        'message': '团队更新成功',
        'team': team.to_dict(include_members=True)
    }), 200


@teams_bp.route('/<int:team_id>', methods=['DELETE'])
@jwt_required()
def delete_team(team_id):
    """删除团队
    
    只有团队所有者可以删除团队
    
    路径参数:
        team_id: 团队ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 删除成功消息
    
    错误响应:
        403: 无权限删除
        404: 团队不存在
    """
    current_user_id = get_jwt_identity()
    
    team = Team.query.get(team_id)
    
    if not team:
        return jsonify({'error': '团队不存在'}), 404
    
    # 检查是否是团队所有者
    if team.owner_id != current_user_id:
        return jsonify({'error': '只有团队所有者可以删除团队'}), 403
    
    # 删除团队（级联删除成员和任务关联）
    db.session.delete(team)
    db.session.commit()
    
    return jsonify({
        'message': '团队删除成功'
    }), 200


@teams_bp.route('/<int:team_id>/members', methods=['GET'])
@jwt_required()
def get_team_members(team_id):
    """获取团队成员列表
    
    路径参数:
        team_id: 团队ID
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        members: 成员列表
    """
    current_user_id = get_jwt_identity()
    
    # 检查是否是团队成员
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user_id
    ).first()
    
    if not membership:
        return jsonify({'error': '您不是该团队成员'}), 403
    
    members = TeamMember.query.filter_by(team_id=team_id).all()
    
    return jsonify({
        'members': [m.to_dict() for m in members]
    }), 200


@teams_bp.route('/<int:team_id>/members', methods=['POST'])
@jwt_required()
def add_team_member(team_id):
    """添加团队成员
    
    路径参数:
        team_id: 团队ID
    
    请求体:
        user_id: 要添加的用户ID（必填）
        role: 角色（可选，默认member）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 添加成功消息
        member: 新成员信息
    """
    current_user_id = get_jwt_identity()
    
    team = Team.query.get(team_id)
    
    if not team:
        return jsonify({'error': '团队不存在'}), 404
    
    # 检查权限（只有所有者和管理员可以添加成员）
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user_id
    ).first()
    
    if not membership or membership.role not in ['owner', 'admin']:
        return jsonify({'error': '无权限添加团队成员'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': '用户ID不能为空'}), 400
    
    # 检查用户是否存在
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 检查是否已是团队成员
    existing = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=user_id
    ).first()
    
    if existing:
        return jsonify({'error': '用户已是团队成员'}), 409
    
    # 验证角色
    role = data.get('role', 'member')
    valid_roles = ['admin', 'member']
    if role not in valid_roles:
        return jsonify({'error': f'无效的角色，可选值: {valid_roles}'}), 400
    
    # 创建成员关系
    new_member = TeamMember(
        team_id=team_id,
        user_id=user_id,
        role=role
    )
    db.session.add(new_member)
    
    # 发送通知
    notification = Notification(
        user_id=user_id,
        type='team_invite',
        title=f'您已被邀请加入团队：{team.name}',
        content=f'{current_user_id} 邀请您加入团队 "{team.name}"',
        link=f'/teams/{team_id}'
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({
        'message': '团队成员添加成功',
        'member': new_member.to_dict()
    }), 201


@teams_bp.route('/<int:team_id>/members/<int:member_id>', methods=['DELETE'])
@jwt_required()
def remove_team_member(team_id, member_id):
    """移除团队成员
    
    路径参数:
        team_id: 团队ID
        member_id: 成员ID（TeamMember的ID）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        message: 移除成功消息
    """
    current_user_id = get_jwt_identity()
    
    team = Team.query.get(team_id)
    
    if not team:
        return jsonify({'error': '团队不存在'}), 404
    
    # 查找成员关系
    membership = TeamMember.query.get(member_id)
    
    if not membership or membership.team_id != team_id:
        return jsonify({'error': '成员不存在'}), 404
    
    # 检查权限
    # 所有者不能被移除，成员可以自己退出
    if membership.role == 'owner':
        return jsonify({'error': '不能移除团队所有者'}), 403
    
    # 检查是否是所有者移除成员，或成员自己退出
    if membership.user_id != current_user_id:
        # 检查当前用户权限
        current_membership = TeamMember.query.filter_by(
            team_id=team_id,
            user_id=current_user_id
        ).first()
        
        if not current_membership or current_membership.role not in ['owner', 'admin']:
            return jsonify({'error': '无权限移除此成员'}), 403
    
    db.session.delete(membership)
    db.session.commit()
    
    return jsonify({
        'message': '团队成员移除成功'
    }), 200


@teams_bp.route('/<int:team_id>/tasks', methods=['GET'])
@jwt_required()
def get_team_tasks(team_id):
    """获取团队任务列表
    
    路径参数:
        team_id: 团队ID
    
    查询参数:
        page: 页码（默认1）
        per_page: 每页数量（默认20）
        status: 任务状态筛选
        priority: 优先级筛选
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (200):
        tasks: 任务列表
        pagination: 分页信息
    """
    current_user_id = get_jwt_identity()
    
    # 检查是否是团队成员
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user_id
    ).first()
    
    if not membership:
        return jsonify({'error': '您不是该团队成员'}), 403
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    
    # 构建查询
    query = Task.query.filter_by(team_id=team_id)
    
    if status:
        query = query.filter(Task.status == status)
    
    if priority:
        query = query.filter(Task.priority == priority)
    
    # 按创建时间倒序
    query = query.order_by(Task.created_at.desc())
    
    # 分页
    from app.utils.decorators import paginate
    result = paginate(query, page, per_page)
    
    return jsonify(result), 200


@teams_bp.route('/<int:team_id>/tasks', methods=['POST'])
@jwt_required()
def create_team_task(team_id):
    """在团队中创建任务
    
    路径参数:
        team_id: 团队ID
    
    请求体:
        title: 任务标题（必填）
        description: 任务描述（可选）
        priority: 优先级（可选）
        due_date: 到期日（可选）
        assigned_to: 分配给用户ID（可选）
    
    请求头:
        Authorization: Bearer <access_token>
    
    成功响应 (201):
        message: 创建成功消息
        task: 新建的任务
    """
    current_user_id = get_jwt_identity()
    
    # 检查是否是团队成员
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user_id
    ).first()
    
    if not membership:
        return jsonify({'error': '您不是该团队成员'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400
    
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': '任务标题不能为空'}), 400
    
    from datetime import datetime
    
    # 解析日期
    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': '到期日格式无效'}), 400
    
    # 创建任务
    task = Task(
        title=title,
        description=data.get('description', '').strip() or None,
        priority=data.get('priority', 'medium'),
        due_date=due_date,
        team_id=team_id,
        user_id=current_user_id,
        assigned_to=data.get('assigned_to')
    )
    
    db.session.add(task)
    db.session.commit()
    
    # 如果分配了用户，发送通知
    if task.assigned_to:
        notification = Notification(
            user_id=task.assigned_to,
            type='task_assigned',
            title=f'您被分配了新任务：{task.title}',
            content=f'{current_user_id} 分配给您任务 "{task.title}"',
            link=f'/tasks/{task.id}'
        )
        db.session.add(notification)
        db.session.commit()
    
    return jsonify({
        'message': '团队任务创建成功',
        'task': task.to_dict()
    }), 201

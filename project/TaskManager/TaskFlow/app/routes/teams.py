# TaskFlow 团队路由
# 处理团队创建、成员管理、邀请等功能

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, TeamMember, TeamRole
from app.models.notification import Notification
from app.models.task import Task
from app.utils.decorators import ajax_login_required
from app.utils.validators import validate_team_data
from app.utils.helpers import success_response, error_response

teams_bp = Blueprint('teams', __name__)


@teams_bp.route('/')
@login_required
def list():
    """
    团队列表页面
    显示用户所属的团队
    """
    # 获取用户拥有的团队
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    
    # 获取用户加入的团队
    memberships = current_user.team_memberships.all()
    joined_teams = [m.team for m in memberships]
    
    return render_template(
        'teams/list.html',
        owned_teams=owned_teams,
        joined_teams=joined_teams
    )


@teams_bp.route('/<int:team_id>')
@login_required
def detail(team_id):
    """
    团队详情页面
    """
    team = Team.query.get_or_404(team_id)
    
    # 检查成员资格
    if not team.is_member(current_user.id) and not team.is_owner(current_user.id):
        abort(403)
    
    # 获取团队任务
    tasks = Task.query.filter_by(team_id=team.id).order_by(
        Task.created_at.desc()
    ).limit(10).all()
    
    # 获取成员列表
    members = team.members.all()
    
    return render_template(
        'teams/detail.html',
        team=team,
        tasks=tasks,
        members=members,
        TeamRole=TeamRole
    )


@teams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    创建团队页面/处理
    """
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'description': request.form.get('description', '').strip()
        }
        
        is_valid, error, errors = validate_team_data(data)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('teams.create'))
        
        # 创建团队
        team = Team(
            name=data['name'],
            description=data['description'],
            owner_id=current_user.id
        )
        team.generate_invite_code()
        
        db.session.add(team)
        
        # 创建者自动成为所有者
        member = TeamMember(
            team=team,
            user=current_user,
            role=TeamRole.OWNER.value
        )
        db.session.add(member)
        
        db.session.commit()
        
        flash('团队创建成功', 'success')
        return redirect(url_for('teams.detail', team_id=team.id))
    
    return render_template('teams/form.html', team=None)


@teams_bp.route('/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(team_id):
    """
    编辑团队页面/处理
    """
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.is_owner(current_user.id):
        abort(403)
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'description': request.form.get('description', '').strip()
        }
        
        is_valid, error, errors = validate_team_data(data, is_update=True)
        if not is_valid:
            for field, message in errors.items():
                flash(message, 'danger')
            return redirect(url_for('teams.edit', team_id=team_id))
        
        team.name = data['name']
        team.description = data['description']
        
        # 更新公开状态
        if request.form.get('is_public'):
            team.is_public = True
        else:
            team.is_public = False
        
        db.session.commit()
        
        flash('团队信息已更新', 'success')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    return render_template('teams/form.html', team=team)


@teams_bp.route('/<int:team_id>/delete', methods=['POST'])
@login_required
def delete(team_id):
    """
    删除团队
    """
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.is_owner(current_user.id):
        abort(403)
    
    db.session.delete(team)
    db.session.commit()
    
    flash('团队已删除', 'success')
    return redirect(url_for('teams.list'))


@teams_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join():
    """
    加入团队页面/处理
    """
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip()
        
        if not invite_code:
            flash('请输入邀请码', 'danger')
            return redirect(url_for('teams.join'))
        
        team = Team.query.filter_by(invite_code=invite_code).first()
        
        if not team:
            flash('邀请码无效', 'danger')
            return redirect(url_for('teams.join'))
        
        if team.is_member(current_user.id):
            flash('您已经是该团队成员', 'info')
            return redirect(url_for('teams.detail', team_id=team.id))
        
        # 添加成员
        member = TeamMember(
            team=team,
            user=current_user,
            role=TeamRole.MEMBER.value
        )
        
        db.session.add(member)
        db.session.commit()
        
        flash(f'成功加入团队：{team.name}', 'success')
        return redirect(url_for('teams.detail', team_id=team.id))
    
    return render_template('teams/join.html')


@teams_bp.route('/<int:team_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(team_id, user_id):
    """
    移除团队成员
    """
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.can_manage(current_user.id):
        abort(403)
    
    # 不能移除所有者
    if team.is_owner(user_id):
        flash('不能移除团队所有者', 'danger')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    member = team.get_member(user_id)
    if not member:
        flash('成员不存在', 'danger')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    db.session.delete(member)
    db.session.commit()
    
    flash('成员已移除', 'success')
    return redirect(url_for('teams.detail', team_id=team_id))


@teams_bp.route('/<int:team_id>/members/<int:user_id>/role', methods=['POST'])
@login_required
def update_member_role(team_id, user_id):
    """
    更新成员角色
    """
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.is_owner(current_user.id):
        abort(403)
    
    role = request.form.get('role', TeamRole.MEMBER.value)
    
    if role not in [r.value for r in TeamRole]:
        flash('无效的角色', 'danger')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    member = team.get_member(user_id)
    if not member:
        flash('成员不存在', 'danger')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    # 不能修改所有者角色
    if team.is_owner(user_id):
        flash('不能修改所有者角色', 'danger')
        return redirect(url_for('teams.detail', team_id=team_id))
    
    member.role = role
    db.session.commit()
    
    flash('角色已更新', 'success')
    return redirect(url_for('teams.detail', team_id=team_id))


# API 端点

@teams_bp.route('/api/teams', methods=['GET'])
@ajax_login_required
def api_list():
    """
    获取团队列表（API）
    """
    # 获取用户拥有的团队
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    
    # 获取用户加入的团队
    memberships = current_user.team_memberships.all()
    joined_teams = [m.team for m in memberships]
    
    all_teams = list(set(owned_teams + joined_teams))
    
    return jsonify({
        'success': True,
        'teams': [t.to_dict() for t in all_teams]
    })


@teams_bp.route('/api/teams', methods=['POST'])
@ajax_login_required
def api_create():
    """
    创建团队（API）
    """
    data = request.get_json()
    
    is_valid, error, errors = validate_team_data(data)
    if not is_valid:
        return error_response(error, 'VALIDATION_ERROR', 400, errors=errors)
    
    team = Team(
        name=data['name'],
        description=data.get('description'),
        owner_id=current_user.id
    )
    team.generate_invite_code()
    
    db.session.add(team)
    
    # 创建者自动成为所有者
    member = TeamMember(
        team=team,
        user=current_user,
        role=TeamRole.OWNER.value
    )
    db.session.add(member)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '团队创建成功',
        'team': team.to_dict()
    }), 201


@teams_bp.route('/api/teams/<int:team_id>', methods=['GET'])
@ajax_login_required
def api_detail(team_id):
    """
    获取团队详情（API）
    """
    team = Team.query.get_or_404(team_id)
    
    if not team.is_member(current_user.id) and not team.is_owner(current_user.id):
        return error_response('权限不足', 'FORBIDDEN', 403)
    
    return jsonify({
        'success': True,
        'team': team.to_dict(include_members=True)
    })


@teams_bp.route('/api/teams/join', methods=['POST'])
@ajax_login_required
def api_join():
    """
    加入团队（API）
    """
    data = request.get_json()
    invite_code = data.get('invite_code', '').strip()
    
    if not invite_code:
        return error_response('请输入邀请码', 'MISSING_CODE', 400)
    
    team = Team.query.filter_by(invite_code=invite_code).first()
    
    if not team:
        return error_response('邀请码无效', 'INVALID_CODE', 404)
    
    if team.is_member(current_user.id):
        return error_response('您已经是该团队成员', 'ALREADY_MEMBER', 400)
    
    # 添加成员
    member = TeamMember(
        team=team,
        user=current_user,
        role=TeamRole.MEMBER.value
    )
    
    db.session.add(member)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'成功加入团队：{team.name}',
        'team': team.to_dict()
    })


@teams_bp.route('/api/teams/<int:team_id>/regenerate-code', methods=['POST'])
@ajax_login_required
def api_regenerate_code(team_id):
    """
    重新生成邀请码（API）
    """
    team = Team.query.get_or_404(team_id)
    
    if not team.is_owner(current_user.id):
        return error_response('权限不足', 'FORBIDDEN', 403)
    
    team.generate_invite_code()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '邀请码已重新生成',
        'invite_code': team.invite_code
    })

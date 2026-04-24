# TaskFlow 团队模型
# 定义团队和团队成员数据结构

from datetime import datetime
from enum import Enum
from app import db


class TeamRole(Enum):
    """团队角色枚举"""
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'
    
    @classmethod
    def choices(cls):
        return [(member.value, member.name) for member in cls]
    
    @classmethod
    def get_display_name(cls, value):
        names = {
            'owner': '所有者',
            'admin': '管理员',
            'member': '成员'
        }
        return names.get(value, '成员')


class Team(db.Model):
    """
    团队模型
    用于团队协作功能
    """
    __tablename__ = 'teams'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 团队信息
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    
    # 设置
    is_public = db.Column(db.Boolean, default=False)  # 是否公开团队
    invite_code = db.Column(db.String(20), unique=True)  # 邀请码
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外键（所有者）
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 关联关系
    owner = db.relationship('User', backref='owned_teams')
    members = db.relationship('TeamMember', backref='team', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Team {self.name}>'
    
    def generate_invite_code(self):
        """生成邀请码"""
        import secrets
        self.invite_code = secrets.token_urlsafe(8)
    
    def to_dict(self, include_members=False):
        """
        转换为字典格式
        
        Args:
            include_members: 是否包含成员列表
        
        Returns:
            dict: 团队信息字典
        """
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar_url': self.avatar_url,
            'is_public': self.is_public,
            'invite_code': self.invite_code,
            'owner': {
                'id': self.owner_id,
                'username': self.owner.username,
                'display_name': self.owner.get_display_name()
            } if self.owner else None,
            'member_count': self.members.count(),
            'task_count': self.tasks.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_members:
            data['members'] = [m.to_dict() for m in self.members]
        
        return data
    
    def is_member(self, user_id):
        """检查用户是否为团队成员"""
        return self.members.filter_by(user_id=user_id).first() is not None
    
    def is_owner(self, user_id):
        """检查用户是否为团队所有者"""
        return self.owner_id == user_id
    
    def get_member(self, user_id):
        """获取成员对象"""
        return self.members.filter_by(user_id=user_id).first()
    
    def get_member_role(self, user_id):
        """获取成员角色"""
        if self.is_owner(user_id):
            return TeamRole.OWNER.value
        member = self.get_member(user_id)
        return member.role if member else None
    
    def can_manage(self, user_id):
        """检查用户是否有管理权限"""
        if self.is_owner(user_id):
            return True
        member = self.get_member(user_id)
        return member and member.role in [TeamRole.OWNER.value, TeamRole.ADMIN.value]


class TeamMember(db.Model):
    """
    团队成员模型
    存储团队成员关系和角色
    """
    __tablename__ = 'team_members'
    
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 外键
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # 成员信息
    role = db.Column(db.String(20), default=TeamRole.MEMBER.value)
    nickname = db.Column(db.String(100))  # 在团队中的昵称
    
    # 时间戳
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 唯一约束（同一用户只能加入同一团队一次）
    __table_args__ = (
        db.UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
    )
    
    def __repr__(self):
        return f'<TeamMember user={self.user_id} team={self.team_id}>'
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'team_id': self.team_id,
            'user_id': self.user_id,
            'role': self.role,
            'role_display': TeamRole.get_display_name(self.role),
            'nickname': self.nickname or self.user.get_display_name(),
            'user': self.user.to_dict(),
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }
    
    @property
    def can_manage(self):
        """检查是否有管理权限"""
        return self.role in [TeamRole.OWNER.value, TeamRole.ADMIN.value]

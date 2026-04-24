"""
TaskFlow 任务管理系统 - 错误处理器
定义全局错误处理逻辑
"""
from flask import jsonify
from werkzeug.http import HTTP_STATUS_CODES
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from flask_jwt_extended import NoAuthorizationError, InvalidHeaderError


def register_error_handlers(app):
    """注册错误处理器
    
    Args:
        app: Flask 应用实例
    """
    
    @app.errorhandler(400)
    def bad_request(error):
        """400 - 请求错误"""
        return jsonify({
            'error': '请求错误',
            'message': str(error.description) if hasattr(error, 'description') else '无效的请求参数'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """401 - 未授权"""
        return jsonify({
            'error': '未授权',
            'message': '请先登录'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """403 - 禁止访问"""
        return jsonify({
            'error': '禁止访问',
            'message': '您没有权限访问此资源'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """404 - 资源不存在"""
        return jsonify({
            'error': '未找到',
            'message': '请求的资源不存在'
        }), 404
    
    @app.errorhandler(409)
    def conflict(error):
        """409 - 资源冲突"""
        return jsonify({
            'error': '资源冲突',
            'message': str(error.description) if hasattr(error, 'description') else '资源已存在'
        }), 409
    
    @app.errorhandler(422)
    def unprocessable(error):
        """422 - 无法处理的实体"""
        return jsonify({
            'error': '数据验证失败',
            'message': str(error.description) if hasattr(error, 'description') else '数据格式不正确'
        }), 422
    
    @app.errorhandler(500)
    def internal_error(error):
        """500 - 服务器内部错误"""
        return jsonify({
            'error': '服务器错误',
            'message': '服务器内部错误，请稍后重试'
        }), 500
    
    # SQLAlchemy 错误处理
    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        """处理数据库完整性错误"""
        return jsonify({
            'error': '数据完整性错误',
            'message': '数据已存在或违反约束条件'
        }), 409
    
    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(error):
        """处理数据库错误"""
        return jsonify({
            'error': '数据库错误',
            'message': '数据库操作失败，请稍后重试'
        }), 500
    
    # JWT 错误处理
    @app.errorhandler(NoAuthorizationError)
    def handle_no_auth(error):
        """处理缺少认证信息错误"""
        return jsonify({
            'error': '未授权',
            'message': '请提供认证信息'
        }), 401
    
    @app.errorhandler(InvalidHeaderError)
    def handle_invalid_header(error):
        """处理无效的认证头错误"""
        return jsonify({
            'error': '认证失败',
            'message': '无效的认证头'
        }), 401

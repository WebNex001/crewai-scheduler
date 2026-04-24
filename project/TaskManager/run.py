"""
TaskFlow 任务管理系统 - 应用入口
启动 Flask 应用的入口文件
"""
import os
from app import create_app

# 创建应用实例
app = create_app(os.environ.get('FLASK_ENV', 'development'))


if __name__ == '__main__':
    # 获取配置
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # 启动应用
    print(f"🚀 TaskFlow 任务管理系统启动中...")
    print(f"📍 访问地址: http://{host}:{port}")
    print(f"🔧 调试模式: {'开启' if debug else '关闭'}")
    
    app.run(host=host, port=port, debug=debug)

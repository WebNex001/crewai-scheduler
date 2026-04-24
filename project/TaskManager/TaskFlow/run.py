# TaskFlow 应用程序入口文件
# 用于启动Flask应用服务器

import os
import sys

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 创建应用实例
app = create_app(os.getenv('FLASK_ENV', 'development'))


def main():
    """
    主函数：启动应用程序
    """
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    TaskFlow 任务管理系统                       ║
║                                                              ║
║  应用已启动: http://{host}:{port}                            ║
║  调试模式: {'开启' if debug else '关闭'}                                          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
CrewAI调度系统配置测试脚本
"""

import os
import sys
import json

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config():
    """测试配置"""
    print("=== CrewAI调度系统配置测试 ===\n")
    
    # 1. 检查配置文件
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        print("❌ 配置文件不存在")
        return False
    
    print("✅ 配置文件存在")
    
    # 2. 加载配置
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ 配置文件加载成功")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return False
    
    # 3. 验证配置结构
    required_sections = ['api', 'system']
    for section in required_sections:
        if section not in config:
            print(f"❌ 缺少配置节: {section}")
            return False
        print(f"✅ 配置节存在: {section}")
    
    # 4. 验证API配置
    api_config = config.get('api', {})
    required_api_keys = ['openai_api_key']
    
    for key in required_api_keys:
        if key not in api_config:
            print(f"❌ 缺少API配置: {key}")
            return False
        print(f"✅ API配置存在: {key}")
    
    # 5. 验证模型配置
    model = api_config.get('model', 'gpt-4')
    temperature = api_config.get('temperature', 0.7)
    max_tokens = api_config.get('max_tokens', 4000)
    
    print(f"✅ 模型配置: {model}")
    print(f"✅ 温度配置: {temperature}")
    print(f"✅ 最大令牌数: {max_tokens}")
    
    # 6. 验证系统配置
    system_config = config.get('system', {})
    log_level = system_config.get('log_level', 'INFO')
    monitoring_interval = system_config.get('monitoring_interval', 30)
    
    print(f"✅ 日志级别: {log_level}")
    print(f"✅ 监控间隔: {monitoring_interval}")
    
    # 7. 测试导入
    try:
        from crewai_scheduler import CrewAIScheduler, validate_config, test_connection
        print("✅ 模块导入成功")
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    
    # 8. 验证配置
    try:
        validation = validate_config()
        print(f"✅ 配置验证完成")
        
        if not validation['valid']:
            print("❌ 配置验证失败:")
            for error in validation['errors']:
                print(f"  - {error}")
            return False
        
        if validation['warnings']:
            print("⚠️ 配置警告:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
        
        print("✅ 配置验证通过")
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False
    
    # 9. 测试连接
    try:
        if test_connection():
            print("✅ API连接测试成功")
        else:
            print("❌ API连接测试失败")
            return False
    except Exception as e:
        print(f"❌ API连接测试失败: {e}")
        return False
    
    print("\n🎉 所有测试通过！配置正确。")
    return True

if __name__ == "__main__":
    success = test_config()
    sys.exit(0 if success else 1)
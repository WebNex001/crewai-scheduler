#!/usr/bin/env python3
"""
测试调度器初始化
"""

import os
import sys
import json

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_init():
    """测试初始化"""
    print("=== 测试调度器初始化 ===\n")
    
    # 1. 测试配置文件路径
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    print(f"配置文件路径: {config_path}")
    
    # 2. 测试配置文件存在性
    if os.path.exists(config_path):
        print("[OK] 配置文件存在")
    else:
        print("[ERROR] 配置文件不存在")
        return False
    
    # 3. 测试配置文件加载
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("[OK] 配置文件加载成功")
        print(f"配置内容: {config}")
    except Exception as e:
        print(f"[ERROR] 配置文件加载失败: {e}")
        return False
    
    # 4. 测试调度器初始化
    try:
        from crewai_scheduler import CrewAIScheduler
        
        # 测试使用指定配置路径
        scheduler = CrewAIScheduler(config_path)
        print("[OK] 调度器初始化成功")
        print(f"调度器配置路径: {scheduler.config_path}")
        print(f"调度器配置: {scheduler.config}")
        
        # 测试配置验证
        validation = scheduler.validate_config()
        print(f"[OK] 配置验证完成")
        print(f"验证结果: {validation}")
        
        return True
    except Exception as e:
        print(f"[ERROR] 调度器初始化失败: {e}")
        return False

if __name__ == "__main__":
    success = test_init()
    print(f"\n测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)
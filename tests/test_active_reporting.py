#!/usr/bin/env python3
"""
测试主动报告功能
"""

import sys
import os
import time
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

from task_monitor import TaskMonitor

def test_active_reporting():
    """测试主动报告功能"""
    print("测试主动报告功能...")
    
    # 创建监控器
    monitor = TaskMonitor()
    
    # 检查配置
    progress_config = monitor.config.get('progress_reports', {})
    print(f"主动报告启用: {progress_config.get('enabled', False)}")
    print(f"报告发送间隔: {progress_config.get('send_interval', 0)}秒")
    print(f"启动时发送报告: {progress_config.get('send_on_startup', False)}")
    print(f"任务完成时发送报告: {progress_config.get('send_on_completion', False)}")
    
    # 模拟检查几次
    for i in range(3):
        print(f"\n第{i+1}次检查...")
        check_record = monitor.check_task_progress()
        
        if check_record:
            # 检查是否应该发送报告
            progress_config = monitor.config.get('progress_reports', {})
            should_send = False
            if progress_config.get('enabled', False):
                should_send = monitor.should_send_report(check_record)
                print(f"应该发送报告: {should_send}")
            
            if should_send:
                report = monitor.generate_progress_report(check_record)
                print("模拟发送报告:")
                print(report)
                
                # 更新最后报告时间
                monitor.last_report_time = datetime.now()
        
        time.sleep(1)  # 等待1秒
    
    print("\n测试完成")

if __name__ == "__main__":
    test_active_reporting()
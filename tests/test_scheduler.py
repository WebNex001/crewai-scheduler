#!/usr/bin/env python3
"""
CrewAI调度系统测试脚本
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_scheduler():
    """测试调度器基本功能"""
    print("🧪 开始测试CrewAI调度系统...")
    
    try:
        from crewai_scheduler import CrewAIScheduler
        
        # 1. 测试初始化
        print("\n1️⃣ 测试初始化...")
        scheduler = CrewAIScheduler()
        print(f"✅ 调度器初始化成功")
        print(f"🏢 部门数量: {len(scheduler.departments)}")
        
        # 2. 测试创建项目
        print("\n2️⃣ 测试创建项目...")
        project_id = scheduler.create_project("测试项目", "这是一个测试项目")
        print(f"✅ 项目创建成功: {project_id}")
        
        # 3. 测试分配任务
        print("\n3️⃣ 测试分配任务...")
        task_id1 = scheduler.assign_task("技术部", "设计系统架构")
        task_id2 = scheduler.assign_task("运营部", "制定运营策略")
        task_id3 = scheduler.assign_task("交付部", "协调项目交付")
        print(f"✅ 任务分配成功: {task_id1}, {task_id2}, {task_id3}")
        
        # 4. 测试查看状态
        print("\n4️⃣ 测试查看状态...")
        status = scheduler.get_status()
        print(f"📊 任务状态:")
        print(f"  - 待处理: {status['tasks']['pending']}")
        print(f"  - 进行中: {status['tasks']['in_progress']}")
        print(f"  - 已完成: {status['tasks']['completed']}")
        
        # 5. 测试执行任务
        print("\n5️⃣ 测试执行任务...")
        results = scheduler.execute_tasks(max_concurrent=2)
        print(f"📊 执行结果:")
        print(f"  - 执行任务数: {results['executed']}")
        print(f"  - 完成任务数: {results['completed']}")
        print(f"  - 失败任务数: {results['failed']}")
        
        # 6. 测试生成报告
        print("\n6️⃣ 测试生成报告...")
        report = scheduler.generate_report()
        print(f"📄 报告生成成功，长度: {len(report)} 字符")
        
        # 7. 测试添加部门
        print("\n7️⃣ 测试添加部门...")
        scheduler.add_department("测试部", ["测试工程师"], 1)
        print(f"✅ 部门添加成功")
        
        print("\n🎉 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli():
    """测试CLI功能"""
    print("\n🧪 测试CLI功能...")
    
    try:
        # 测试帮助命令
        import subprocess
        result = subprocess.run([sys.executable, "cli.py", "--help"], 
                              capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print("✅ CLI帮助命令正常")
            print("可用命令:")
            print(result.stdout)
        else:
            print(f"❌ CLI帮助命令失败: {result.stderr}")
            
    except Exception as e:
        print(f"❌ CLI测试失败: {e}")

if __name__ == "__main__":
    print("🚀 CrewAI调度系统测试")
    print("=" * 50)
    
    # 测试调度器
    success = test_scheduler()
    
    # 测试CLI
    test_cli()
    
    if success:
        print("\n✅ 所有测试完成！")
    else:
        print("\n❌ 测试失败，请检查代码")
        sys.exit(1)
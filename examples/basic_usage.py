"""
CrewAI调度系统基础使用示例
"""

import sys
import os
import time

# 添加技能路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crewai_scheduler import get_scheduler, create_project, assign_task, execute_tasks, get_status, generate_report

def main():
    """基础使用示例"""
    print("🚀 CrewAI调度系统基础使用示例")
    print("=" * 50)
    
    # 1. 初始化调度器
    print("\n1️⃣ 初始化调度器...")
    scheduler = get_scheduler()
    print(f"✅ 调度器初始化完成")
    print(f"🏢 已加载 {len(scheduler.departments)} 个部门")
    
    # 2. 创建项目
    print("\n2️⃣ 创建项目...")
    project_id = create_project("智能客服系统", "开发一个基于AI的智能客服系统")
    print(f"✅ 项目创建成功: {project_id}")
    
    # 3. 分配任务
    print("\n3️⃣ 分配任务...")
    
    # 技术部任务
    assign_task("技术部", "设计系统架构和API接口")
    assign_task("技术部", "实现核心对话功能")
    assign_task("技术部", "编写测试用例和执行测试")
    
    # 运营部任务
    assign_task("运营部", "制定客服运营策略")
    assign_task("运营部", "创建用户培训材料")
    assign_task("运营部", "分析用户行为数据")
    
    # 交付部任务
    assign_task("交付部", "制定交付计划和客户沟通")
    assign_task("交付部", "解决技术问题和优化方案")
    
    print("✅ 任务分配完成")
    
    # 4. 查看状态
    print("\n4️⃣ 查看系统状态...")
    status = get_status()
    print(f"📊 任务状态:")
    print(f"  - 待处理: {status['tasks']['pending']}")
    print(f"  - 进行中: {status['tasks']['in_progress']}")
    print(f"  - 已完成: {status['tasks']['completed']}")
    
    # 5. 执行任务
    print("\n5️⃣ 执行任务...")
    results = execute_tasks(max_concurrent=3)
    print(f"📊 执行结果:")
    print(f"  - 执行任务数: {results['executed']}")
    print(f"  - 完成任务数: {results['completed']}")
    print(f"  - 失败任务数: {results['failed']}")
    
    # 6. 再次查看状态
    print("\n6️⃣ 执行后状态...")
    status = get_status()
    print(f"📊 任务状态:")
    print(f"  - 待处理: {status['tasks']['pending']}")
    print(f"  - 进行中: {status['tasks']['in_progress']}")
    print(f"  - 已完成: {status['tasks']['completed']}")
    
    # 7. 生成报告
    print("\n7️⃣ 生成报告...")
    report = generate_report()
    print("📄 系统报告:")
    print(report)
    
    # 8. 演示添加新部门
    print("\n8️⃣ 添加新部门...")
    scheduler.add_department("市场部", ["市场经理", "营销专员"], 2)
    print("✅ 市场部添加成功")
    
    # 9. 演示设置优先级
    print("\n9️⃣ 设置任务优先级...")
    success = scheduler.set_task_priority("task_0", "high")
    if success:
        print("✅ 优先级设置成功")
    else:
        print("❌ 任务不存在")
    
    print("\n🎉 基础使用示例完成！")

if __name__ == "__main__":
    main()
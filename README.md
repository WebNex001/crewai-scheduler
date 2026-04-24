# CrewAI Scheduler v3.2

AI 多智能体团队调度系统 — 支持 8 阶段项目工作流流水线、模块化开发、断点续传。

## 项目结构

```
crewai-scheduler/
├── __main__.py           # CLI 入口 & 工作流执行引擎
├── crewai_scheduler.py   # AI 任务执行引擎（API 调用、Prompt 构建、Debug 日志）
├── code_extractor.py     # LLM 输出解析 & 模块提取 & 导出摘要
├── project_writer.py     # 项目文件写入 & README/文档生成
├── db.py                 # 数据库操作（JSON 原子读写、文件锁）
├── retry.py              # API 重试与指数退避策略
├── constants.py          # 共享常量（阶段名称、文件遍历工具）
├── file_lock.py          # 文件锁（原子创建、僵尸锁清理）
├── scheduler_log.py      # 统一日志（控制台+文件双输出）
├── usage_monitor.py      # 使用监控与统计
├── utf8_fix.py           # Windows 终端 UTF-8 编码修复
├── config.json           # 配置文件（API、工作流、系统设置）⚠️ 含密钥，已加入 .gitignore
├── requirements.txt      # Python 依赖
└── tests/                # 单元测试
```

## 快速开始

### 1. 配置 API 密钥

**方式一（推荐）**：设置环境变量
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**方式二**：编辑 `config.json`
```json
{
  "api": {
    "openai_api_key": "your-api-key-here",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4"
  }
}
```

### 2. 安装依赖

```bash
pip install openai>=1.0.0
```

### 3. 使用命令

```bash
# 初始化
python __main__.py init

# 创建项目
python __main__.py create-project --name "我的项目" --description "项目描述" --department 技术部

# 查看项目列表
python __main__.py list-projects

# 执行工作流（8 阶段流水线）
python __main__.py execute-workflow --project "我的项目"

# 执行所有待处理项目
python __main__.py execute-workflow --all

# 从指定阶段开始
python __main__.py execute-workflow --project "我的项目" --stage 4

# 干跑模式（预览不调API）
python __main__.py execute-workflow --project "我的项目" --dry-run

# 断点续传
python __main__.py execute-workflow --project "我的项目" --resume

# 查看工作流进度
python __main__.py workflow-status --project "我的项目"

# 暂停工作流
python __main__.py workflow-pause --project "我的项目"

# 恢复暂停的工作流
python __main__.py workflow-resume --project "我的项目"

# 重置工作流
python __main__.py workflow-reset --project "我的项目"

# 健康检查
python __main__.py workflow-health
python __main__.py workflow-health --fix      # 修复崩溃状态
python __main__.py workflow-health --resume   # 自动恢复

# 查看使用监控
python __main__.py monitor
```

## 8 阶段工作流（技术部）

| 阶段 | ID | 负责人 | 思考模式 | 说明 |
|------|-----|--------|:------:|------|
| 1. 需求分析 | requirements | 架构师 | ✅ | 分析需求，输出需求规格说明书 |
| 2. 架构设计 | architecture | 架构师 | ✅ | 基于需求输出技术架构文档 |
| 3. 详细设计 | detailed_design | 架构师+开发 | ✅ | 输出详细技术设计方案 |
| 4. 编码开发 | development | 开发工程师 | ❌ | 基于设计编写实现代码（Function Calling） |
| 5. 代码审查 | code_review | 架构师 | ✅ | 审查代码质量（不通过→回退到阶段4） |
| 6. 测试 | testing | 测试工程师 | ✅ | 功能/性能测试（不通过→回退到阶段4） |
| 7. 部署上线 | deployment | DevOps | ❌ | 部署方案与上线检查 |
| 8. 项目交付 | delivery | 项目经理 | ❌ | 汇总交付物与验收报告 |

## 关键机制

- **上下文传递**：每个阶段的 AI 输出自动作为下一阶段的输入
- **模块化开发**：大项目自动拆分为多个模块，逐模块开发
- **自动回退**：审查/测试不通过 → 回退到开发阶段（默认最多 3 次，超限强制通过）
- **思考模式**：架构/设计/审查/测试开启，编码/部署/交付关闭
- **断点续传**：进程中断后状态持久化，`--resume` 自动恢复
- **API 限流保护**：阶段间延迟 + 429 指数退避重试
- **Debug 日志**：`config.json` 设 `system.debug=true` → `Debug/` 目录
- **Token 用量追踪**：自动记录 prompt/completion token 到监控数据

## 数据目录

| 路径 | 内容 |
|------|------|
| `data/projects.json` | 项目数据库 |
| `data/workflow.json` | 工作流状态 |
| `data/monitoring.json` | 使用监控数据 |
| `data/logs/` | 运行日志 |
| `Debug/` | Debug 详细日志 |
| `project/<name>/` | 生成的项目代码和文档 |

## 配置说明

详见 `config.json`，主要配置项：

- `api` — LLM API 配置（密钥、模型、超时等）
- `system.debug` — 是否开启 Debug 日志
- `workflow.技术部` — 工作流阶段定义、回退规则、模块化开发配置

## 注意事项

- API 密钥请设置环境变量 `OPENAI_API_KEY`，勿硬编码到 config.json
- 长时间运行建议使用 `--resume` 支持断点续传
- 模块化开发默认为 `auto` 模式，小项目自动走单次开发

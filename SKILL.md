---
version: 3.2.0
description: >
  Use this skill **when** the user wants to manage an AI-powered digital company with
  multi-agent task scheduling, project workflow pipeline (8-stage: requirements →
  architecture → design → development → review → test → deploy → deliver), or automated
  team orchestration with staged AI execution and role-based agents.
  
  **Trigger phrases:** "create a project", "execute workflow", "run pipeline",
  "AI company", "digital team", "crewai", "scheduler", "workflow status",
  "开发状态", "工作流", "项目进度", "流水线", "代码审查", "测试部署", "debug日志",
  "暂停", "恢复", "续传", "健康检查".
  
  **Three departments supported:**
  - 技术部 (Tech) — **has full 8-stage workflow pipeline with role-based AI agents, thinking mode per stage**
  - 运营部 (Operations) — marketing, content, user growth
  - 交付部 (Delivery) — implementation, deployment, QA
  
  **Prefer this skill over generic task managers when** the user mentions AI agents,
  workflows, project pipelines, or wants real AI execution via LLM API.
  
  **Do NOT use for** simple todo lists, personal reminders, or non-AI task tracking.
---

# CrewAI Scheduler Skill (v3.2.0)

CrewAI 多智能体团队调度系统 v3.2，支持**项目工作流流水线**、思考模式按阶段开关、Debug 详细日志、模块化开发、上下文压缩、检查点续传、数据压缩等高级特性。

## Skill 用途与整体流程

### 用途

本 Skill 是一个**AI 驱动的数字公司管理系统**，模拟真实技术团队的协作流程，通过多角色 AI Agent 自动完成从需求分析到项目交付的完整软件开发生命周期。

### 核心工作流（技术部 8 阶段）

```
用户创建项目 → 初始化工作流 → 执行工作流 → 完成交付
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
需求分析 → 架构设计 → 详细设计 → 编码开发 → 代码审查 → 测试 → 部署 → 交付
    ↑                                    ↓
    └──────────── 审查/测试不通过时回退 ──┘
```

1. **需求分析** (requirements): 架构师分析需求，输出需求规格说明书
2. **架构设计** (architecture): 架构师设计系统整体技术架构
3. **详细设计** (detailed_design): 架构师+开发输出详细技术方案（含模块拆分 JSON）
4. **编码开发** (development): 开发工程师通过 Function Calling 实时写入代码文件
5. **代码审查** (code_review): 架构师审查代码质量（不通过→回退到开发阶段）
6. **测试** (testing): 测试工程师执行测试（不通过→回退到开发阶段）
7. **部署上线** (deployment): DevOps 输出部署方案
8. **项目交付** (delivery): 项目经理汇总交付物

### 上下文传递机制

每个阶段的 AI 输出自动作为下一阶段的输入，形成**流水线式上下文传递**：
- 需求分析输出 → 架构设计输入
- 架构设计输出 → 详细设计输入
- 详细设计输出 → 开发阶段输入（含模块拆分 JSON）
- 开发阶段代码 → 代码审查/测试阶段注入实际代码文件

### 数据流向

```
用户输入 → CLI 命令 → __main__.py
                ↓
        crewai_scheduler.py (AI 引擎)
                ↓
        API 调用 (OpenAI/MiniMax)
                ↓
        阶段输出 → 代码提取 → project/<name>/
                ↓
        工作流状态 → SQLite/JSON 持久化
```

## 核心特性

### 工作流模式（技术部）

| 阶段 | ID | 负责人 | 思考 | 说明 |
|------|-----|--------|:----:|------|
| 1. 需求分析 | requirements | 架构师 | ✅ | 分析需求，输出需求规格说明书 |
| 2. 架构设计 | architecture | 架构师 | ✅ | 基于需求输出技术架构文档 |
| 3. 详细设计 | detailed_design | 架构师+开发 | ✅ | 输出详细技术设计方案（含模块拆分 JSON） |
| 4. 编码开发 | development | 开发工程师 | ❌ | 基于设计编写实现代码（Function Calling 实时写入） |
| 5. 代码审查 | code_review | 架构师 | ✅ | 审查代码质量（不通过→回退到阶段4） |
| 6. 测试 | testing | 测试工程师 | ✅ | 功能/性能测试（不通过→回退到阶段4） |
| 7. 部署上线 | deployment | DevOps | ❌ | 部署方案与上线检查 |
| 8. 项目交付 | delivery | 项目经理 | ❌ | 汇总交付物与验收报告 |

### 关键机制

- 🔄 **上下文传递**：每个阶段的 AI 输出自动作为下一阶段的输入
- ↺ **自动回退 + 最大次数限制**：审查/测试不通过 → 回退到 development（默认最多 3 次，超限强制通过）
- 🧠 **思考模式按阶段开关**：架构/设计/审查/测试开启（提质量），编码/部署/交付关闭（省时间）
- 📦 **串行执行**：多项目 FIFO 逐个完成
- 💾 **断点续跑**：进程中断后状态持久化，支持 `--resume` 恢复
- 🔒 **API 限流保护**：阶段间延迟 + 429 自动重试（指数退避 + 抖动）
- 🐛 **Debug 日志**：`config.json` 设 `debug:true` → `Debug/debug_时间戳.log`
- 📝 **自动代码提取**：development 阶段通过 Function Calling 实时写入文件到 `project/<name>/`
- 📁 **项目文档生成**：工作流完成后自动生成 README、目录结构、manifest.json、各阶段文档
- 🗜️ **上下文超限自动压缩**：Token 超预算时自动提取结构化摘要，保留文件列表/API/数据库Schema等关键信息（3 级压缩策略）
- 🔖 **全阶段检查点**：开发阶段文件级检查点 + 其他阶段结果级检查点，失败重试可从中断处继续
- 🗑️ **自动数据压缩**：阶段完成后自动压缩 history/sub_tasks，工作流完成后压缩 result，防止数据库膨胀
- 🏗️ **模块化开发**：大项目自动拆分为多个模块，支持串行/并行开发，可配置模块上限和文件上限
- 🛡️ **优雅中断**：SIGINT/SIGTERM 标记为 `interrupted`（可恢复），而非 `failed`
- 📊 **健康检查**：扫描崩溃/中断工作流，支持自动修复、恢复、数据压缩

## Route Table

| 用户意图 | 路由 | 命令 | 触发词示例 |
|---------|------|------|-----------|
| Initialize system | **INIT** | `init` | "初始化" / "初始化系统" |
| Create new project | **CREATE** | `create-project` | "创建项目" / "新建项目" |
| List all projects | **LIST** | `list-projects` | "查看项目" / "项目列表" |
| System status | **STATUS** | `status` | "状态" / "系统状态" |
| Generate report | **REPORT** | `report` | "生成报告" / "查看报告" |
| Usage monitoring | **MONITOR** | `monitor` | "监控" / "使用情况" |
| Clear all data | **CLEAR** | `clear` | "清空所有数据" |
| Delete single project | **DELETE** | `delete-project` | "删除项目" / "删掉项目" |
| **Execute project workflow** | **WORKFLOW-RUN** | `execute-workflow` | "执行工作流" / "开始开发" / "跑流水线" |
| **View workflow progress** | **WORKFLOW-STATUS** | `workflow-status` | "开发状态" / "工作流进度" / "项目进展" |
| **Reset workflow** | **WORKFLOW-RESET** | `workflow-reset` | "重置工作流" / "重新开始" |
| **View stage definitions** | **WORKFLOW-STAGES** | `workflow-stages` | "查看工作流阶段" / "有哪些阶段" |
| **Health check** | **WORKFLOW-HEALTH** | `workflow-health` | "健康检查" / "崩溃恢复" |
| **Pause workflow** | **WORKFLOW-PAUSE** | `workflow-pause` | "暂停工作流" / "暂停开发" |
| **Resume workflow** | **WORKFLOW-RESUME** | `workflow-resume` | "恢复工作流" / "继续开发" |

## Route Instructions

### Route INIT — Initialize

```bash
python __main__.py init
```

初始化调度系统，创建 SQLite 数据库和 JSON 文件，显示已配置的工作流部门。

### Route CREATE — Create Project

```bash
python __main__.py create-project --name "<name>" --description "<desc>" --department 技术部
```

创建项目并自动初始化工作流状态（如果部门启用了工作流）。

- `--name` / `-n`: 项目名称（必填）
- `--description` / `-d`: 项目描述（可选）
- `--department` / `-dept`: 部门，可选 `技术部`/`运营部`/`交付部`（默认：技术部）

### Route LIST — List Projects

```bash
python __main__.py list-projects
```

列出所有项目，显示状态、部门、工作流进度。

### Route STATUS — System Status

```bash
python __main__.py status
```

显示项目总数、工作流状态分布、Debug 模式状态。

### Route REPORT — Generate Report

```bash
python __main__.py report                    # 系统总报告
python __main__.py report --project TestWorkflow  # 单项目详细报告
```

生成文本报告并保存到 `data/reports/`。

### Route MONITOR — Usage Monitoring

```bash
python __main__.py monitor
```

查看使用监控报告：总调用次数、成功率、平均耗时、命令使用分布、错误统计。

### Route CLEAR — Clear Data

```bash
python __main__.py clear --confirm
```

⚠️ 清空所有项目和工作流数据。执行前必须确认。

### Route DELETE — Delete Single Project

```bash
python __main__.py delete-project --name "<name>" --confirm
```

删除单个项目的所有数据：
1. 工作流记录（SQLite + JSON）
2. 项目记录（SQLite + JSON）
3. 生成的项目文件目录（`project/<name>/`）

⚠️ 执行前必须确认。

---

## Workflow Routes (工作流路由)

### Route WORKFLOW-RUN — Execute Project Workflow

```bash
# 执行指定项目
python __main__.py execute-workflow --project "<name>"

# 执行所有待处理项目
python __main__.py execute-workflow --all

# 从指定阶段开始（1-8）
python __main__.py execute-workflow --project "<name>" --stage 4

# 干跑模式：预览将执行的阶段/模块，不实际调 API
python __main__.py execute-workflow --project "<name>" --dry-run

# 断点续传：自动检测并恢复中断的工作流
python __main__.py execute-workflow --resume

# 指定项目断点续传
python __main__.py execute-workflow --project "<name>" --resume
```

**参数说明：**
- `--project` / `-p`: 项目名称（可选，不指定则自动选择第一个待处理项目）
- `--all` / `-a`: 执行所有待处理项目
- `--stage` / `-s`: 从指定阶段开始（1-8）
- `--dry-run`: 干跑模式，预览执行计划但不调用 API
- `--resume`: 断点续传，自动恢复 `interrupted`/`paused`/`in_progress` 状态的工作流

**执行特性：**
- 后台执行（timeout=7200s），用户可随时通过 `workflow-status` 查看进度
- 自动进度估算：基于已完成阶段的平均耗时预测剩余时间
- 开发阶段支持模块化开发（根据 `config.json` 中的 `modular_development` 配置）
- 代码审查/测试阶段自动注入项目实际代码文件到上下文

### Route WORKFLOW-STATUS — View Workflow Progress

```bash
python __main__.py workflow-status --project "<name>"
```

查看工作流详细进度：
- 当前阶段、状态图标（`[DONE]`/`[PASS!]`/`[TODO]`/`[REJECTED]`/`[PAUSED]`）
- 各阶段耗时、输出预览
- 回退历史记录
- 强制通过标记

### Route WORKFLOW-RESET — Reset Workflow

```bash
python __main__.py workflow-reset --project "<name>"
```

重置工作流所有阶段为 `pending`，保留项目记录。用于从头重新开始。

### Route WORKFLOW-STAGES — View Stage Definitions

```bash
python __main__.py workflow-stages --department 技术部
```

查看部门工作流阶段定义：阶段名称、Agent、思考模式、角色 Prompt、回退规则、最大重试次数、超时时间。

### Route WORKFLOW-HEALTH — Health Check

```bash
# 扫描异常工作流
python __main__.py workflow-health

# 自动修复崩溃的工作流（标记为 interrupted）
python __main__.py workflow-health --fix

# 自动恢复中断的工作流
python __main__.py workflow-health --resume

# 压缩已完成工作流的数据（清理 result/history，防止 DB 膨胀）
python __main__.py workflow-health --compact

# 组合使用
python __main__.py workflow-health --fix --resume --compact
```

**检测类型：**
- `interrupted`: 进程被中断（可恢复）
- `paused`: 用户手动暂停（可恢复）
- `crashed`: `in_progress` 超过 1 小时无心跳更新（疑似崩溃）
- `failed`: 执行失败

### Route WORKFLOW-PAUSE — Pause Workflow

```bash
python __main__.py workflow-pause --project "<name>"
```

暂停正在执行（`in_progress`）的工作流。将状态标记为 `paused`，当前阶段标记为 `interrupted`，保存当前进度。区别于崩溃中断，这是用户主动暂停。

### Route WORKFLOW-RESUME — Resume Workflow

```bash
python __main__.py workflow-resume --project "<name>"
```

恢复 `paused` 或 `interrupted` 状态的工作流。自动调用 `execute-workflow --resume` 从中断处继续执行。

## Directories Written

| Path | Content |
|------|---------|
| `data/scheduler.db` | SQLite 主数据库（WAL 模式） |
| `data/projects.json` | 项目数据库（JSON 向后兼容） |
| `data/workflow.json` | 工作流状态（JSON 向后兼容） |
| `data/reports/` | 生成的报告（`.txt`） |
| `data/logs/` | 运行时日志（按天） |
| `data/monitoring.json` | 性能监控数据 |
| `Debug/` | Debug 详细日志（`debug_时间戳.log`，需 `system.debug=true`） |
| `project/<name>/` | 自动提取的代码文件、README、docs/ |
| `project/<name>/src/` | 源代码文件（Function Calling 实时写入） |
| `project/<name>/docs/stages/` | 阶段输出文档（`01_需求分析.md` ~ `08_项目交付.md`） |
| `project/<name>/manifest.json` | 文件清单与统计（数量、语言、行数） |

## Configuration (config.json)

### API 配置

```json
{
  "api": {
    "openai_api_key": "...",
    "base_url": "https://api.minimaxi.com/v1",
    "model": "minimax-m2",
    "temperature": 0.7,
    "max_tokens": 128000,
    "context_window": 200000,
    "timeout": 300
  }
}
```

- `context_window`: 模型上下文窗口大小（token），用于自动压缩计算的基准
- `timeout`: API 调用超时时间（秒）

### 系统配置

```json
{
  "system": {
    "debug": false,
    "log_level": "INFO",
    "monitoring_interval": 30,
    "debug_log_max_mb": 50
  }
}
```

- `debug`: 开启 Debug 日志（写入 `Debug/` 目录）
- `debug_log_max_mb`: Debug 日志文件大小上限（MB），超过自动清理

### 工作流配置

```json
{
  "workflow": {
    "技术部": {
      "enabled": true,
      "max_retries": 3,
      "stages": [...],
      "retry_on_reject": {
        "code_review": "development",
        "testing": "development"
      },
      "modular_development": {
        "mode": "auto",
        "max_files_per_module": 8,
        "max_modules": 10,
        "min_files_to_split": 10,
        "parallel": false,
        "context_limits": {
          "architecture_overview_chars": 2000,
          "module_design_chars": 3000,
          "code_review_code_chars": 30000
        }
      }
    }
  }
}
```

**模块化开发配置说明：**
- `mode`: `auto`（自动判断）/`always`（强制拆模块）/`never`（从不拆模块）
- `max_files_per_module`: 每个模块最多包含的文件数
- `max_modules`: 项目最多允许的模块数，超出时自动合并相邻模块
- `min_files_to_split`: `auto` 模式下，总文件数 ≤ 此值时不拆模块
- `parallel`: `true` = 模块并行执行（更快但更耗 API 并发量）/`false` = 串行执行（更稳定）
- `context_limits`: 控制各阶段传入 LLM 的上下文大小
  - `architecture_overview_chars`: 模块化开发时架构概览的最大字符数
  - `module_design_chars`: 模块设计文档的最大字符数
  - `code_review_code_chars`: 代码审查/测试阶段注入项目代码的最大字符数

## Architecture (v3.2)

```
User Input → __main__.py (CLI 15 commands)
                ├── crewai_scheduler.py (v3.2 AI Engine)
                │     ├── execute_stage() — Single stage (role prompt + context + thinking + debug log)
                │     ├── execute_stage_with_tools() — Function Calling 多轮交互（development 阶段）
                │     ├── _build_prompts() — Prompt 构建 + 上下文自动压缩
                │     ├── _compress_previous_outputs() — 3-tier 上下文压缩（摘要→深度压缩→丢弃）
                │     ├── _extract_structured_summary() — 结构化摘要提取（保留文件列表/API/Schema）
                │     ├── _check_rejection() — 审查/测试打回检测
                │     ├── get_workflow_stages() / is_workflow_enabled() / get_max_retries()
                │     ├── get_retry_target() / get_api_timeout() / is_debug()
                │     └── _setup_debug_log() → Debug/debug_时间戳.log
                ├── code_extractor.py (v3.2 Code Extraction)
                │     ├── extract() — Parse markdown/XML code blocks
                │     ├── parse_modules_from_design() — 从详细设计解析模块拆分 JSON
                │     ├── extract_module_design_section() — 提取模块设计片段
                │     ├── extract_exports_summary() — 提取项目 exports 摘要
                │     └── CodeFile dataclass (path, content, language)
                ├── project_writer.py (v3.2 Project Generation)
                │     ├── write_files() — Write extracted code to project/
                │     ├── write_complete_project() — Generate README + manifest + stage docs
                │     ├── generate_readme() — Create project README with tree structure
                │     └── save_stage_outputs() — Write stage docs to docs/stages/
                ├── workflow_db.py (v3.2 SQLite Database)
                │     ├── ensure_db() — Init schema + auto migration from JSON
                │     ├── load_workflow() / save_workflow() — CRUD
                │     ├── compact_workflow() — Data compaction (truncate results)
                │     ├── query_workflows_by_status() — Query by status
                │     └── record_token_usage() / get_token_usage_summary()
                ├── db.py (JSON Backward Compatibility)
                │     ├── load_db() / save_db() — Atomic JSON I/O with memory cache
                │     └── atomic_update() — Thread-safe updates
                ├── retry.py (Retry & Backoff)
                │     ├── _call_with_retry() — Exponential backoff + jitter for 429
                │     └── _call_with_context_compress() — Retry with context compression on overflow
                ├── constants.py (Shared Constants)
                │     ├── STAGE_NAMES / STAGE_NAMES_NUMBERED
                │     └── _walk_project_files() — Project file scanner
                ├── config.json (v3.2: api + system + workflow stages + modular_development + context_window)
                ├── file_lock.py (Concurrency Safety — O_CREAT|O_EXCL atomic locks)
                ├── scheduler_log.py (Dual Output Logging — console + file with colors)
                ├── usage_monitor.py (Performance Monitoring — calls, duration, errors, token usage)
                └── utf8_fix.py (Windows UTF-8 terminal fix)

Data Store → data/
    ├── scheduler.db     (SQLite primary: workflows, projects, token_usage, WAL mode)
    ├── projects.json    (JSON backward compatibility)
    └── workflow.json    (JSON backward compatibility)

Project Output → project/<name>/
    ├── src/             (extracted source code via Function Calling)
    ├── docs/stages/     (01_需求分析.md ~ 08_项目交付.md)
    ├── README.md        (project overview with tree structure)
    └── manifest.json    (file stats: count, languages, lines)
```

## 上下文压缩机制详解

当累积的上下文接近模型 `context_window` 时，系统自动触发 3 级压缩策略：

1. **结构化摘要**（第一轮）：按 markdown 标题分段，保留代码块/表格/列表/关键章节（文件列表、API、数据库 Schema），压缩描述性段落
2. **深度压缩**（第二轮）：只保留标题行 + 代码块 + 列表项 + 表格行，丢弃所有描述文字
3. **阶段丢弃**（第三轮）：按优先级丢弃最早阶段（requirements → deployment → delivery → testing → code_review → architecture → detailed_design → development）

压缩结果带缓存，避免同一 workflow 内重复压缩。

## 检查点机制详解

- **开发阶段检查点**（文件级）：`checkpoint_files` 记录已成功写入的文件路径。失败重试时跳过已完成的文件，只编写剩余文件
- **非开发阶段检查点**（结果级）：`checkpoint_prev_result` 保存之前失败的尝试结果。重试时注入上下文，让 LLM 基于之前的工作继续完善
- **模块级检查点**：每完成一个模块立即保存 `sub_tasks` 和心跳时间
- **阶段完成后**：自动清除检查点；回退时清除所有相关检查点

# CrewAI Scheduler Skill 全面总结 (v3.2.0)

## 一、系统定位

CrewAI Scheduler 是一个**AI 驱动的数字公司管理系统**，模拟真实技术团队的完整协作流程。它通过多角色 AI Agent（架构师、开发工程师、测试工程师、DevOps、项目经理）自动完成从需求分析到项目交付的 8 阶段软件开发生命周期。

核心设计理念：**让 AI 像真实团队一样协作工作**，而非单次 Prompt 生成全部代码。

---

## 二、功能全景

### 2.1 CLI 命令矩阵（15 个命令）

| 命令 | 功能 | 关键参数 |
|------|------|---------|
| `init` | 初始化系统 | 无 |
| `create-project` | 创建项目 | `--name`, `--description`, `--department` |
| `list-projects` | 列出项目 | 无 |
| `status` | 系统状态 | 无 |
| `report` | 生成报告 | `--project`（可选） |
| `monitor` | 使用监控 | 无 |
| `clear` | 清空所有数据 | `--confirm` |
| `delete-project` | 删除单个项目 | `--name`, `--confirm` |
| `execute-workflow` | 执行工作流 | `--project`, `--all`, `--stage`, `--dry-run`, `--resume` |
| `workflow-status` | 查看进度 | `--project`（可选） |
| `workflow-reset` | 重置工作流 | `--project` |
| `workflow-stages` | 查看阶段定义 | `--department` |
| `workflow-health` | 健康检查 | `--fix`, `--resume`, `--compact` |
| `workflow-pause` | 暂停工作流 | `--project` |
| `workflow-resume` | 恢复工作流 | `--project` |

### 2.2 工作流 8 阶段

```
需求分析 → 架构设计 → 详细设计 → 编码开发 → 代码审查 → 测试 → 部署 → 交付
   ↑                                            ↓
   └──────────── 审查/测试不通过时回退到开发 ────┘
```

每个阶段特点：
- **角色切换**：不同阶段使用不同 AI 角色身份和 System Prompt
- **思考模式开关**：架构/设计/审查/测试开启（提质量），编码/部署/交付关闭（省时间/Token）
- **上下文传递**：前一阶段输出自动注入下一阶段 Prompt
- **自动回退**：代码审查/测试不通过 → 回退到开发阶段（最多 3 次，超限强制通过）

### 2.3 模块化开发

大项目自动拆分为多个模块开发：
- **自动解析**：从 `detailed_design` 阶段的 JSON 代码块提取模块定义
- **智能合并**：模块数超过上限时自动合并相邻模块
- **小项目优化**：总文件数 ≤ 10 时跳过模块化（单次开发更快）
- **串行/并行**：支持串行（稳定）或并行（更快）执行模式
- **上下文控制**：每个模块只接收架构概览 + 本模块设计，避免上下文膨胀

### 2.4 数据存储（双存储架构）

| 存储层 | 技术 | 用途 |
|--------|------|------|
| 主存储 | SQLite (WAL 模式) | 原子事务、按需查询、索引加速、并发安全 |
| 兼容层 | JSON 文件 | 向后兼容、人类可读、便于调试 |

所有写操作同时更新 SQLite + JSON，读操作优先 SQLite。

---

## 三、核心机制详解

### 3.1 Function Calling 实时写入（development 阶段）

不同于传统 AI 代码生成（输出 markdown 代码块后提取），development 阶段使用 OpenAI Function Calling：
- AI 每完成一个文件就立即调用 `write_file(path, content)` 工具
- 文件实时写入 `project/<name>/src/`
- 支持多轮工具调用（最多 30 轮）
- 路径遍历安全检查（禁止 `..` 和绝对路径）

### 3.2 上下文压缩（3 级策略）

当累积上下文接近模型上限时自动触发：

| 级别 | 策略 | 保留内容 |
|------|------|---------|
| L1 结构化摘要 | 按标题分段，保留结构化内容 | 代码块、表格、列表、关键章节 |
| L2 深度压缩 | 只保留标题 + 代码 + 列表 + 表格 | 丢弃所有描述文字 |
| L3 阶段丢弃 | 按优先级丢弃整个阶段 | requirements → deployment → ... → development |

压缩结果带缓存，避免同一 workflow 内重复压缩。

### 3.3 检查点续传

- **开发阶段**：文件级检查点 `checkpoint_files`，失败重试时跳过已完成文件
- **非开发阶段**：结果级检查点 `checkpoint_prev_result`，重试时基于之前结果继续
- **模块级**：每完成一个模块立即保存进度
- **优雅中断**：SIGINT/SIGTERM 标记为 `interrupted`（可恢复），不是 `failed`

### 3.4 数据压缩（防止 DB 膨胀）

- **阶段完成后**：自动压缩 `history` 和 `sub_tasks`（只保留元数据）
- **工作流完成后**：自动截断 `result`（保留 2000 字符 + 原长度提示）
- **手动压缩**：`workflow-health --compact` 批量压缩所有已完成工作流

### 3.5 API 限流保护

- **阶段间延迟**：默认 15 秒，避免触发速率限制
- **模块间延迟**：默认 5 秒
- **429 自动重试**：指数退避 + 随机抖动（base * 2^n + jitter）
- **上下文超限**：不重试，直接返回并触发压缩后重试

---

## 四、模块职责

| 模块 | 职责 | 关键类/函数 |
|------|------|-----------|
| `__main__.py` | CLI 入口、命令路由、工作流执行编排 | `main()`, `cmd_execute_workflow()`, `cmd_workflow_health()` |
| `crewai_scheduler.py` | AI 引擎：Prompt 构建、API 调用、上下文压缩、打回检测 | `CrewAIScheduler`, `execute_stage()`, `execute_stage_with_tools()` |
| `code_extractor.py` | 代码提取、模块解析、exports 摘要 | `CodeExtractor`, `parse_modules_from_design()` |
| `project_writer.py` | 项目文件写入、README 生成、manifest 生成 | `ProjectWriter`, `write_complete_project()` |
| `workflow_db.py` | SQLite 数据库操作 | `ensure_db()`, `save_workflow()`, `compact_workflow()` |
| `db.py` | JSON 文件读写（原子更新 + 内存缓存） | `load_db()`, `save_db()`, `atomic_update()` |
| `retry.py` | API 重试与退避策略 | `_call_with_retry()`, `_call_with_context_compress()` |
| `constants.py` | 共享常量与工具函数 | `STAGE_NAMES`, `_walk_project_files()` |
| `file_lock.py` | 文件锁并发控制 | `FileLock` |
| `scheduler_log.py` | 统一日志（控制台 + 文件 + 颜色） | `SchedulerLogger` |
| `usage_monitor.py` | 使用监控与统计 | `UsageMonitor` |
| `utf8_fix.py` | Windows UTF-8 终端修复 | `ensure_utf8()` |

---

## 五、配置要点

### 5.1 关键配置项

```json
{
  "api": {
    "base_url": "API 地址",
    "model": "模型名称",
    "max_tokens": 128000,
    "context_window": 200000,  // 上下文压缩计算的基准
    "timeout": 300
  },
  "workflow.技术部.modular_development": {
    "mode": "auto",           // auto/always/never
    "max_files_per_module": 8,
    "max_modules": 10,
    "min_files_to_split": 10,
    "parallel": false,        // true=并行（快但不稳）
    "context_limits": {
      "code_review_code_chars": 30000  // 审查时代码注入上限
    }
  }
}
```

### 5.2 环境变量

- `CREWAI_DATA_DIR`: 自定义数据目录路径
- `OPENAI_API_KEY`: API Key（优先级低于 config.json）

---

## 六、当前状态（截至扫描时）

- **已开发项目数**: 2 个（经删除测试后）
- **Skill 版本**: v3.2.0
- **CLI 命令数**: 15 个
- **工作流阶段**: 8 阶段（技术部）
- **支持部门**: 3 个（技术部、运营部、交付部）
- **核心模块数**: 12 个 Python 模块
- **数据存储**: SQLite (主) + JSON (兼容)

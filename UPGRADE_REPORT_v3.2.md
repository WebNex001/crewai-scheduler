# CrewAI Scheduler 升级报告

**日期**: 2026-04-25  
**版本**: v3.1 → v3.2  
**目标**: 确保大项目稳定运行，上下文超限可恢复

---

## 一、已实施的修改

### A1: 修复 JSON 膨胀 ✅

**问题**: `workflow.json` 膨胀至 3.7GB，`scheduler.db` 膨胀至 21.5GB（524万条 history 记录）

**修复**:
1. `_save_workflow()` 不再全量重写 JSON，改为只更新单个项目条目
2. 新增 `_compact_completed_stages()` — 阶段完成后自动压缩 history 和 sub_tasks
3. 工作流完成后自动压缩所有 result（保留 2000 字符）
4. 修复 `save_workflow()` 中 history 只追加不覆盖的 BUG → 改为先删除再插入

**效果**: 数据库从 **21.5GB → 84KB**，JSON 从 **3.7GB → 14.5KB**

**修改文件**: `__main__.py`, `workflow_db.py`

---

### A2: 修复主循环 `wf` 引用过期 ✅

**问题**: `_on_tool_call` 更新检查点到 DB 后，主循环中的 `wf` 变量还是旧数据，后续读取检查点丢失

**修复**:
1. 模块级检查点保存后重新加载 `wf`
2. 阶段结果保存前重新加载 `wf`
3. 清除重复的 `_load_workflows()` 调用

**修改文件**: `__main__.py`

---

### A3: 移除 `[:3000]` 硬截断 ✅

**问题**: `_build_prompts()` 中 `prev_result[:3000]` 硬截断与 `_compress_previous_outputs` 压缩逻辑冲突，可能破坏压缩结果

**修复**: 移除硬截断，由 `_compress_previous_outputs` 统一控制上下文长度

**修改文件**: `crewai_scheduler.py`

---

### B1: 改进 Token 估算 ✅

**问题**: 之前用 `chars/2.5` 粗略估算，中文场景偏差大（中文1字≈1.5-2 token）

**修复**: 区分中文和英文字符，中文按 `chars/1.5` 估算，英文按 `chars/4` 估算，混合文本加权计算

**修改文件**: `crewai_scheduler.py`

---

### B2: 压缩结果缓存 ✅

**问题**: 每次 API 调用都重新压缩 `previous_outputs`，浪费计算

**修复**: 添加 `_compress_cache` 字典，基于输入的哈希值缓存压缩结果

**修改文件**: `crewai_scheduler.py`

---

### B3: 结构化摘要压缩 ✅

**问题**: `_do_compress` 和 `_do_dev_compress` 用粗暴截断 `text[:len(text)//2]`，可能丢失关键信息

**修复**: 改用 `_extract_structured_summary()` 进行结构化压缩，保留文件列表、API定义、数据库 Schema 等关键信息

**修改文件**: `__main__.py`

---

### C1: 检查点扩展到所有阶段 ✅

**问题**: 检查点只在开发阶段生效，设计/测试阶段超限无恢复手段

**修复**:
1. 非开发阶段：失败时保存 `checkpoint_prev_result`（之前尝试的结果摘要）
2. 重试时将之前失败的结果注入 `stage_context`，告知 LLM 基于之前工作继续
3. 新增 `extra_json` 字段存储检查点数据（`workflow_stages` 表）
4. 阶段成功后自动清除检查点，回退时也清除检查点

**修改文件**: `__main__.py`, `workflow_db.py`

---

### 额外修复

1. **`SchedulerLogger.warning()` 方法缺失** — `db.py` 调用了 `warning()` 但只有 `warn()`，已添加别名
2. **`cmd_workflow_reset` 双重 JSON 写入** — `_save_workflow` 已包含 JSON 写入，移除重复调用
3. **`ensure_db()` 每次执行 schema 初始化** — 确保 ALTER TABLE 迁移在旧数据库上也能执行

**修改文件**: `scheduler_log.py`, `__main__.py`, `workflow_db.py`

---

## 二、测试结果

### TaskManager 项目完整工作流测试

| 阶段 | 状态 | 耗时 | 备注 |
|------|------|------|------|
| 需求分析 | ✅ 通过 | 38.9s | |
| 架构设计 | ✅ 通过 | 66.4s | 上下文传递正常 |
| 详细设计 | ✅ 通过 | 71.0s | 模块化JSON正确 |
| 编码开发 | ✅ 通过 | 309.5s | Function Calling 文件写入正常，回退重开后第2次通过 |
| 代码审查 | ✅ 通过 | 25.4s | 首次打回→触发回退，第2次通过 |
| 测试 | ✅ 通过 | 57.5s | |
| 部署上线 | ✅ 通过 | 50.2s | |
| 项目交付 | ✅ 通过 | 30.3s | |

**总耗时**: ~18分钟  
**回退次数**: 1次（代码审查打回→开发重开→审查通过）  
**数据库大小**: 84KB（修复前 21.5GB）

---

## 三、修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `__main__.py` | A1压缩+A2引用修复+C1检查点扩展+B3结构化压缩+BUG修复 |
| `crewai_scheduler.py` | A3移除硬截断+B1 Token估算+B2压缩缓存 |
| `workflow_db.py` | C1 extra_json字段+history去重+ensure_db迁移修复 |
| `scheduler_log.py` | 添加 warning() 方法别名 |
| `db.py` | 无修改 |
| `retry.py` | 无修改 |
| `constants.py` | 无修改 |
| `config.json` | 无修改 |

---

## 四、大项目稳定性保障链

```
大项目稳定运行保障 = 压缩(防超限) + 检查点(可恢复) + 数据一致性(不丢数据)
                         ↑                    ↑               ↑
                      方案B                方案C1         方案A1+A2+A3
```

三个环节已全部就位：

1. **压缩防超限**: Token 估算→预算计算→结构化摘要→渐进压缩→缓存，4层保障
2. **检查点可恢复**: 开发阶段文件级检查点 + 其他阶段结果级检查点，双机制保障
3. **数据一致性**: SQLite 为主存储 + wf 引用刷新 + history 去重 + 自动压缩

---

## 五、已知遗留项（风险低，可后续处理）

1. **中文 Token 估算仍有偏差** — 没有引入 tiktoken，混合文本的估算不够精确，但偏差在可接受范围
2. **workflow.json 仍双写** — 保留向后兼容，建议未来版本移除 JSON 双写，SQLite 单一数据源
3. **429 限流策略** — 当前指数退避+抖动够用，但可优化为智能队列+多 Key 轮换
4. **代码审查误打回** — LLM 可能对截断的代码误判为"不完整"而打回，已有 system_prompt 提示但仍可能发生

---

## 六、结论

本次升级核心解决了**大项目开发中上下文超限导致失败且无法恢复**的问题。通过 5 项修改（A1+A2+A3+B+C1）建立了完整的"压缩-检查点-一致性"保障链。经 TaskManager 项目完整 8 阶段工作流验证，所有功能正常运行，包括回退机制、Function Calling 文件写入、自动压缩等。数据库从 21.5GB 压缩到 84KB，彻底解决了数据膨胀问题。

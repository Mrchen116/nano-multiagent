# refactor-395: 消除 Copy-paste 重复 + 修复吞异常

## Relations

- Depends on: 无
- Blocks: 无
- Related: 代码审查报告（全仓库 99 个代码坏味道扫描）

## 原始诉求

> 新建一个unit，把报告写进一个md中。然后我决定先优化Copy-paste，吞异常的问题

（来源：全仓库代码审查工作流，7 维度并行扫描，发现 99 个代码坏味道。用户选择优先处理 Copy-paste 和吞异常两类。）

## 澄清记录

（见上方 Q1-Q5）

- Q1: Copy-paste（9处）和吞异常（9处）是全做完还是挑最严重的先做？
  A(原话): 好
  Agent 解读: 用户同意全部做完，一个 unit 搞定。

- Q2: 吞异常的修复策略——fire-and-forget 的也要修吗？
  A(原话): 有意为之的就不用修啊
  Agent 解读: fire-and-forget 的保持原样不动。

- Q3: 那只修真正有问题的 5 处，逐个定策略（有的 raise、有的 log、有的返回 sentinel）？
  A(原话): 对。。fire-and-forget 的保持原样不动，只修真正隐藏了问题的地方解决。不一定是加日志，有的可能是需要直接报错？
  Agent 解读: 用户确认只修 5 处真正有问题的吞异常，策略因情况而异（raise / log / sentinel），不一刀切。

- Q4: 测试文件重复（3处，~1200行）包不包括在"优化 Copy-paste"里？
  A(原话): 包括
  Agent 解读: 测试重复也纳入范围。

- Q5: "Duplicated code"分类（_TERMINAL_STATUSES 7处重复、atomic-write 2处重复）也一起做吗？
  A(原话): 一起。方案你先别急，spec阶段不定方案
  Agent 解读: 全部纳入。用户明确提醒 spec 阶段不讨论实现方案。

- Q6（design 阶段补充对齐）: 范围"有点少"，报告里哪些是毫无疑问、无需讨论的问题也一起做？
  A(原话): 就做这点有点少。再去看看报告，看有哪些是不需要讨论，毫无疑问是问题的 → 选定"第二类 废弃API, 第三类 死代码删除"
  Agent 解读: 本 unit 从"Copy-paste + 吞异常"扩为"机械型坏味道清扫"。新增三块：①吞异常补全（同主题，报告里漏掉的同类非 fire-and-forget 静默 except，5→10 处）；②废弃 API（logger.warn→warning）；③死代码删除（未使用 facade / 孤立模块）。明确排除一切需架构讨论的项（God function/class 拆分、dataclass 打包、加锁/连接池、安全 token、超时/事务、前端组件、/tmp 测试 sweep、worktree_runtime 非死、safety.py TODO 待查）——这些仍各自独立 unit。第四类 print→logger 未纳入。

## 现状痛点

全仓库代码审查发现 99 个代码坏味道，其中 Copy-paste 重复和吞异常两类问题影响面最广：

**Copy-paste 重复（14 处）：**
- 9 处生产代码工具函数重复（`_log_hook_diagnostics` 4文件、`_utc_now_iso` 5文件、`_require_text` 5文件等），每次 bugfix 必须同步改多处，遗漏即引入不一致 bug（如 `_require_text` 已出现 RuntimeError/ValueError 不一致）
- 3 处测试文件重复（~1200 行），维护成本翻倍，掩盖 source of truth
- 2 处常量/模式重复（`_TERMINAL_STATUSES` 7文件、atomic-write 2文件）

**吞异常（10 处真正有问题的，非 fire-and-forget）：**

原始 5 处：
- 配置解析 `except Exception: pass`：配置坏了用户完全不知道
- REPL `traceback.print_exc()` 混入 broad except：stderr 打乱结构化输出
- compaction summarizer fallback：调用方分不清真摘要和 fallback
- web search 两个 provider：网络错误、auth 失败全不可见
- `_consume_task_exception`：后台任务失败零可观测

design 阶段补全的同类 5 处（报告里被首版遗漏的同性质静默 except）：
- `runtime.py:1152` permission_resolved 发布器 `except: pass`：权限投递失败完全不可见
- `main.py` IM 流式 observer **5 个** `except: pass`：一次瞬时 IM 断连完全不可见
- `main.py:972` gateway shutdown `suppress(Exception)`：清理失败（句柄泄漏/状态损坏）被吞
- `background_session_events.py:89` subscriber stop 吞异常：停止时关键事件失败不可见
- `commands.py:374` 权限请求 JSON 序列化失败 `except: pass`：用户看到截断的权限请求

**废弃 API（11 处）：**
- `logger.warn()`（Python 3.3 起废弃）散布在 5 个 agent 文件 11 处，正确写法 `logger.warning()`

**死代码（4 项）：**
- `IM/models.py`（23 行未使用 facade）、`IM/repositories.py`（25 行未使用 facade）：生产代码零引用，仅测试 import
- `smoke_runtime.py`：全仓零引用的孤立模块
- `IM/domain/__init__.py` 死 re-export：无任何 `from IM.domain import X` 用法

## 目标状态

- 所有重复的工具函数/常量/模式只定义一处（跨包不可共享处收敛到每包一份），其他位置统一 import
- 测试文件零重复，共享逻辑提取到公共 helper
- 10 处吞异常各自按恰当策略处理（raise / log / fallback），不再静默丢失错误信息
- `logger.warn()` 全部改 `logger.warning()`，无废弃 API 调用
- 未使用 facade / 孤立模块全部删除，测试 import 重定向到真源
- 全部已有正常路径行为不变——这是纯重构 + 失败路径可观测性增强，用户正常使用无感知

## 用户侧验收标准（不变性）

本 unit 是面向内部的变更，无用户可观察的新功能。以下用回归基线镜头写既有行为快照。

### Requirement: IM 聊天功能不受影响

#### Scenario: 发送和接收消息
- **WHEN** 用户在 IM 中发送消息
- **THEN** 消息正常投递，与变更前一致

#### Scenario: 群聊功能
- **WHEN** 用户在群聊中使用 @mention 和发送消息
- **THEN** 群聊功能正常，与变更前一致

### Requirement: Agent 对话功能不受影响

#### Scenario: 通过 Gateway 发起 agent 对话
- **WHEN** 用户通过 IM 向 agent 发送消息
- **THEN** agent 正常响应，与变更前一致

#### Scenario: Agent 工具调用
- **WHEN** agent 执行工具调用（bash、read、write 等）
- **THEN** 工具调用正常完成，与变更前一致

### Requirement: Coding CLI 功能不受影响

#### Scenario: REPL 交互
- **WHEN** 用户在 Coding CLI 中输入命令
- **THEN** REPL 正常响应，与变更前一致

#### Scenario: 权限请求展示
- **WHEN** 工具调用触发权限请求
- **THEN** 权限请求正常展示，用户可批准/拒绝，与变更前一致

### Requirement: Gateway 启停和配置不受影响

#### Scenario: Gateway 正常启动
- **WHEN** 启动 Gateway 进程
- **THEN** Gateway 正常连接 IM、加载配置、开始服务，与变更前一致

#### Scenario: 配置解析
- **WHEN** Gateway 读取配置文件
- **THEN** 配置正确解析，与变更前一致（但配置损坏时应有错误反馈，不再静默忽略）

### Requirement: 测试套件全部通过

#### Scenario: 单元测试
- **WHEN** 运行 `pytest -m "not e2e"`
- **THEN** 所有测试通过，无回归

## 影响范围

涉及 4 个包的以下文件（按审查报告）：

**Copy-paste 修复涉及：**
- `src/agent/core/` — runtime.py, loop.py, events/hub.py, runs/registry.py, tools/registry.py, session/jsonl_store.py, session/entries.py, ids.py, skills/writer.py, memory/store.py, types.py
- `src/agent/platform/llm/providers/` — anthropic/, openai_compat/ 下的 mapper.py, client.py
- `src/agent/platform/tools/builtins/` — write.py, edit.py, read.py, bash.py, task_stop.py, agent.py, task.py
- `src/personal_assistant/` — main.py, ws/im_connection.py, channels/web_relay_adapter.py, config/sync_client.py, products/personal_assistant/tools/send_message.py
- `src/IM/infra/` — db.py, repositories.py
- `src/IM/ws/gateway_handler.py`, `src/IM/application/event_service.py`
- 新增共享模块（具体位置由 design 阶段决定）

**吞异常修复涉及（10 处）：**
- `src/coding_cli/commands.py` — _read_section, REPL send loop, 权限请求 JSON 序列化(line 374)
- `src/agent/core/agent/compaction/summarizer.py`
- `src/agent/products/personal_assistant/tools/web_search.py`
- `src/agent/core/agent/runtime.py` — permission_resolved 发布器(line 1152)
- `src/personal_assistant/main.py` — _consume_task_exception, IM observer ×5, gateway shutdown suppress
- `src/personal_assistant/gateway/background_session_events.py` — subscriber stop

**废弃 API 修复涉及：**
- `src/agent/core/tools/registry.py`、`src/agent/core/agent/runtime.py`、`src/agent/core/agent/loop.py`、`src/agent/core/runs/registry.py`、`src/agent/platform/hooks/builtins/default_status.py`

**死代码删除涉及：**
- 删 `src/IM/models.py`、`src/IM/repositories.py`、`src/personal_assistant/smoke_runtime.py`
- 清理 `src/IM/domain/__init__.py` 死 re-export
- ~28 个 `tests/im_service/` 及 `tests/unit/IM/` 测试文件的 import 重定向到 `IM.domain.models` / `IM.infra.repositories`

**测试去重涉及：**
- `tests/unit/personal_assistant/test_inbound_pipeline_session.py`
- `tests/unit/personal_assistant/test_inbound_pipeline_dispatch.py`
- `tests/unit/personal_assistant/test_gateway_im_connection.py`
- `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`
- `tests/unit/test_background_hook_fork.py`
- `tests/unit/test_background_hook_fork_conversation.py`

## 范围与非目标

**本期做（design 阶段扩范围后）：**
- 14 处 Copy-paste 重复消除（生产代码 9 + 测试 3 + 常量/模式 2）
- 10 处真正有问题的吞异常修复（非 fire-and-forget）
- 废弃 API 修复（`logger.warn()` → `logger.warning()` 11 处）
- 死代码删除（2 个未使用 facade + 1 个孤立模块 + 1 处死 re-export，含测试 import 重定向）
- 确保全测试套件通过

**本期不做：**
- God function / God class 拆分（runtime.py, main.py, gateway_handler.py 等——独立 unit）
- Mega file 拆分（main.py 2558行, repositories.py 2700行——独立 unit）
- 构造函数/参数爆炸 dataclass 打包、深层嵌套 dispatch table 重构（有设计权衡——独立 unit）
- 资源泄漏（日志句柄、SQLite 连接池）、竞态/全局可变状态加锁（需设计——独立 unit）
- 硬编码 token 安全策略、URL scheme 校验、缺超时/事务（需决策——独立 unit）
- 前端代码坏味道（超大组件、useEffect 问题、缺少 error boundary、v1 死代码删除等——独立 unit）
- 测试质量问题（flaky 测试、setup 过大、/tmp 硬编码路径 sweep 需逐一判断——独立 unit）
- print() → logger（第四类，本期未纳入）
- `worktree_runtime.py`（经核实非死，有 3 个活测试）、`safety.py` TODO(bugfix-355)（需先查迁移完成与否）
- 架构违规（本次审查发现 0 个，无需处理）
- Fire-and-forget 类吞异常（有意为之，保持原样）

## 迁移与回滚策略

**行为不变保证：**
- 所有修改只涉及提取共享模块 + 统一 import，不改变任何业务逻辑
- 吞异常修复只改错误处理路径（加日志 / 改 raise / 改 sentinel），正常路径不变
- 每个修改点对应的现有测试必须继续通过

**回滚：**
- 每个重复工具函数的提取可独立回滚——恢复本地副本即可
- 吞异常修复可独立回滚——恢复 `except Exception: pass`
- 建议按模块分批提交，不搞一个巨型 commit

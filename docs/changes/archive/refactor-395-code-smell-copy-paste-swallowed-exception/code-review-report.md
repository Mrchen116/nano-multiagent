# 代码审查报告 — 代码坏味道全面扫描

> 生成时间：2026-06-02
> 扫描方式：7 维度并行 agent 工作流扫描
> 扫描范围：src/agent/ (165 files), src/IM/ (41 files), src/coding_cli/ (24 files), src/personal_assistant/ (25 files), src/IM/frontend/src/ (~82 tsx files)

共发现 **99** 个代码坏味道：
- 🔴 Critical: 6
- 🟠 High: 44
- 🟡 Medium: 44
- 🟢 Low: 5

## 按维度分布

| 维度 | 发现数 |
|---|---|
| Python 复杂度与长度 | 20 |
| Python 反模式与代码质量 | 19 |
| **架构违规与依赖问题** | **0** ✅ |
| 错误处理与健壮性 | 15 |
| 前端代码坏味道 | 15 |
| 测试质量问题 | 15 |
| 死代码与重复 | 15 |

---

## 上帝函数（7 个）

### 🔴 CRITICAL

**_run_locked：399 行，CC=44**
- 📁 `src/agent/core/agent/runtime.py` (253-651)
- 一个方法承担了所有职责：session 加载、history 构建、权限检查、loop 执行、compaction、内存快照管理、错误恢复。9 个参数，嵌套 5 层，圈复杂度 44。
- 💡 拆分为独立私有方法：session 准备、history 组装、compaction 处理、错误恢复。每个方法控制在 80 行以内。

**observer：253 行嵌套函数，CC=72，嵌套 8 层**
- 📁 `src/personal_assistant/main.py` (1909-2188)
- `_build_kernel_event_observer` 内部的 observer 闭包是整个代码库圈复杂度最高的函数（CC=72），嵌套 8 层。一个巨型 if/elif 链按 event_name 分发，每个分支内嵌深层 async 闭包。
- 💡 提取每个 event handler 为独立 async 方法，用 dispatch dict 替代 if/elif 链，用带依赖注入的类替代闭包模式。

**AgentLoop.run：322 行，14 个参数，CC=37**
- 📁 `src/agent/core/agent/loop.py` (106-427)
- 管理整个 LLM 调用 + 工具执行循环，322 行，14 个参数（多数是 override），嵌套 7 层。
- 💡 拆分为：prompt 准备、LLM 调用编排、工具执行迭代、结果最终化。将 override 参数打包为 Options/Config dataclass。

### 🟠 HIGH

**_run_repl：183 行，CC=27**
- 📁 `src/coding_cli/commands.py` (492-674)
- REPL 主循环函数，负责输入读取、命令解析、session 管理、流式输出、错误展示、历史管理、后台事件排空——全在一个函数里。
- 💡 提取输入处理、session 管理、错误展示为独立函数。将嵌套函数迁移到 REPLSession 类的方法上。

**_handle_repl_command_async：179 行，CC=26**
- 📁 `src/coding_cli/commands.py` (834-1012)
- REPL 命令分发函数，每个命令分支都是内联实现而非委托。
- 💡 使用命令分发表，每个 handler 独立为 < 40 行的函数。

**MessageRepository.create_message：181 行，10 个参数**
- 📁 `src/IM/infra/repositories.py` (777-957)
- 负责验证、附件处理、工具调用持久化、token 用量追踪、投递状态、通知分发、事务管理——181 行 10 个参数。
- 💡 提取附件处理、工具调用持久化、通知分发为独立 helper 方法。使用 CreateMessageCommand dataclass。

### 🟡 MEDIUM

**handle_inbound / _run：179 行，CC=31**
- 📁 `src/personal_assistant/gateway/inbound_pipeline.py` (139-317)
- 入站消息管道，179 行，内含 141 行的嵌套函数 _run。
- 💡 提取 session 解析、kernel 分发、错误/状态处理为独立管道阶段。内嵌 _run 应改为方法而非嵌套函数。

---

## 上帝类（3 个）

### 🔴 CRITICAL

**GatewayHandler：53 个方法，1683 行**
- 📁 `src/IM/ws/gateway_handler.py` (52-1735)
- 53 个方法横跨 1683 行，承担至少 6 个不同职责：WebSocket 连接管理、消息路由、流式 delta 处理、agent 消息处理、群聊广播、回执持久化、事件桥接。
- 💡 拆分为聚焦的类：GatewayConnectionManager、GatewayMessageRouter、GatewayStreamHandler、GatewayReceiptService，用组合方式组装。

### 🟠 HIGH

**AgentRuntime：32 个方法，1665 行**
- 📁 `src/agent/core/agent/runtime.py` (77)
- `__init__` 本身 116 行、16 个参数，构造 10+ 内部协作者。
- 💡 提取 SessionRuntimeState 类管理 per-session dict，提取 CompactionManager 管理 compaction 逻辑。可将方法数降到 ~15。

### 🟡 MEDIUM

**RunsRegistry：22 个方法，619 行**
- 📁 `src/agent/core/runs/registry.py` (76)
- 管理 run 生命周期、状态转换、任务追踪、事件发布。`_set_status` 方法有 13 个参数。
- 💡 拆分 run 生命周期管理和事件发布。将状态转换验证提取为状态机。将 `_set_status` 参数打包为 StatusUpdate dataclass。

---

## 测试文件重复（3 个）

### 🔴 CRITICAL

**15 个测试函数在 session 和 dispatch 测试文件间 100% 重复**
- 📁 `tests/unit/personal_assistant/test_inbound_pipeline_session.py` vs `test_inbound_pipeline_dispatch.py`
- 843 行 vs 701 行，15 个测试函数实现 99.9-100% 相同，~700 行纯重复。维护成本翻倍，且掩盖了哪个文件才是 source of truth。
- 💡 提取 15 个共享测试到公共 helper 模块或参数化 fixture。每个文件只保留各自关注点独有的测试。

**9 个测试函数在 gateway IM connection 文件间 91-100% 重复**
- 📁 `tests/unit/personal_assistant/test_gateway_im_connection.py` vs `test_gateway_im_connection_behavior.py`
- 536 行 vs 554 行，几乎是克隆。`_behavior` 文件只多了少量额外测试。
- 💡 合并为单个文件，或提取共享测试逻辑到 helper。`_behavior` 文件只保留真正不同的测试。

### 🟠 HIGH

**6 个测试函数在 fork 和 fork_conversation 文件间 97-100% 重复**
- 📁 `tests/unit/test_background_hook_fork.py` vs `test_background_hook_fork_conversation.py`
- 915 行 vs 292 行，6 个测试函数高度重复，包括 117 行的 `test_fork_executor_denies_unlisted_tool_at_execution_layer`。
- 💡 合并 conversation 测试到主 fork 测试文件，或使用共享 fixture 模块。

---

## Copy-paste 重复（9 个）

### 🟠 HIGH

**_log_hook_diagnostics 在 4 个文件中完全相同**
- 📁 `src/agent/core/agent/runtime.py`, `loop.py`, `runs/registry.py`, `tools/registry.py`
- 同一个 ~15 行的静态方法在 4 个文件中逐字节相同：runtime.py:1079, loop.py:596, runs/registry.py:500, tools/registry.py:342。
- 💡 提取到 `agent/core/hooks/` 或公共模块中统一 import。

**_utc_now_iso 在 5 个 agent/core 文件中重复**
- 📁 `src/agent/core/agent/runtime.py`, `events/hub.py`, `runs/registry.py`, `session/jsonl_store.py`, `session/entries.py`
- 同一个 2 行 helper（`datetime.now(timezone.utc).isoformat()`）在 5 个文件中各自定义为私有函数。
- 💡 提取到 `agent/core/ids.py` 或与现有 ID helper 并列的共享 utils 模块。

**_extract_non_negative_int 在 LLM provider 中重复 4 次**
- 📁 `src/agent/platform/llm/providers/` 下 4 个文件
- 相同的 6 行 helper 分别定义在 anthropic/mapper.py:296, anthropic/client.py:301, openai_compat/mapper.py:293, openai_compat/client.py:279。每个 provider 有两份副本（mapper 和 client 各一份）。
- 💡 提取到 `agent/platform/llm/providers/` 下的共享模块（如 common.py）。

**_require_text 在 personal_assistant 中重复 5 次**
- 📁 `src/personal_assistant/` 下 5 个文件：main.py, im_connection.py, web_relay_adapter.py, sync_client.py, send_message.py
- 同一个验证 helper 在 5 个文件中重复。注意 main.py 抛 RuntimeError 而其他 4 个抛 ValueError——不一致可能掩盖了 bug。
- 💡 提取到 `personal_assistant/_utils.py`。修复 RuntimeError/ValueError 不一致问题。

### 🟡 MEDIUM

**_display_path 在 3 个 builtin tool 文件中完全相同**
- 📁 `src/agent/platform/tools/builtins/write.py`, `edit.py`, `read.py`
- 同一个 4 行 helper（try relative_to, except return str(path)）逐字节重复。
- 💡 提取到 `agent/platform/tools/` 下的共享工具模块。

**3 个 helper 函数在 db.py 和 repositories.py 间重复**
- 📁 `src/IM/infra/db.py` + `src/IM/infra/repositories.py`
- `_is_no_reply_protocol_token`、`_optional_text`、`_preview_from_event` 在两个文件间重复，实现相同或近似。
- 💡 移到公共模块（如 `IM/infra/_helpers.py`），两个文件统一 import。

**_optional_text 在 IM 和 personal_assistant 中重复 5 次**
- 📁 `src/personal_assistant/channels/web_relay_adapter.py`, `IM/ws/gateway_handler.py`, `IM/infra/db.py`, `IM/infra/repositories.py`, `IM/application/event_service.py`
- 同一个可选文本验证 helper 出现在 5 个文件中，有细微差异（有的对非字符串抛 ValueError，有的静默返回 None）。
- 💡 提取到共享工具模块，统一错误处理行为。

**bind_wiring 和 _require_wiring 样板代码在 3 个 tool 文件中重复**
- 📁 `src/agent/platform/tools/builtins/bash.py`, `task_stop.py`, `agent.py`
- 相同的 wiring 模式（bind_wiring 存 self._wiring, _require_wiring 检查并抛 ToolError）在 3 个文件中重复。
- 💡 提取到基类 mixin 或 `agent/platform/tools/base.py` 中的共享 helper。

**_normalize_optional_text 在 task.py 和 agent.py 间重复**
- 📁 `src/agent/platform/tools/builtins/task.py`, `agent.py`
- 相同的 6 行 helper 分别定义在 task.py:548 和 agent.py:679。
- 💡 提取到 `agent/platform/tools/builtins/` 下的共享模块。

---

## 宽泛异常捕获（5 个）

### 🟠 HIGH

**permission_resolved 发布器静默吞异常**
- 📁 `src/agent/core/agent/runtime.py` (1152)
- `except Exception: pass` 静默吞掉 `future.result()` 发送 permission_resolved SSE 事件时的所有错误。无日志、无指标——失败完全不可见。
- 💡 至少加 debug/warning 级别日志，让权限投递失败可诊断。

**IM 流式 observer 中 5 个 `except Exception: pass`**
- 📁 `src/personal_assistant/main.py` (1931, 1973, 2024, 2068)
- kernel_event_observer 中有 5 个独立的 try/except Exception: pass 块，静默丢弃向 IM 发送 WebSocket 消息时的所有错误。一次瞬时 IM 断连完全不可见。
- 💡 至少加 warning 级别日志。考虑短重试或至少发指标，让静默消息丢失可被观测。

**REPL 发送循环中 traceback.print_exc() 混入 broad except**
- 📁 `src/coding_cli/commands.py` (655-657)
- REPL 发送循环中 broad except 捕获所有异常后直接调 `traceback.print_exc()`——stderr 输出混入结构化 REPL 输出，绕过了错误展示层。
- 💡 使用已有的 `_print_repl_turn_error_block` helper（line 663 已在用），或走 logging 通道。

### 🟡 MEDIUM

**compaction 摘要器静默 fallback 隐藏 LLM 失败**
- 📁 `src/agent/core/agent/compaction/summarizer.py` (69)
- `except Exception: return _fallback_summary()` 将任何 LLM 或网络错误静默转为通用模板摘要。调用方无法区分是真摘要还是 fallback。
- 💡 记录异常日志，或返回 sentinel 让调用方区分真摘要和 fallback。

**两个搜索 provider 静默吞掉所有异常**
- 📁 `src/agent/products/personal_assistant/tools/web_search.py` (29, 65)
- `_search_duckduckgo` 和 `_search_brave` 都捕获裸 Exception 并返回空列表或 fall through。网络错误、auth 失败、限流——全部不可见。
- 💡 至少加 warning 级别日志，让搜索失败可诊断。

---

## 吞异常（4 个）

### 🟠 HIGH

**配置解析裸 except: pass 吞掉所有错误**
- 📁 `src/coding_cli/commands.py` (_read_section, line 1066)
- YAML 配置文件解析时 `except Exception: pass` 静默吞掉权限错误、磁盘满、损坏 YAML 等所有异常，返回空 dict 好像文件不存在。用户完全不知道配置坏了。
- 💡 **直接报错**：在返回 fallback 前记录 warning 并包含异常详情。或直接 raise 让调用方处理。

**gateway shutdown 中 suppress(Exception) 隐藏清理失败**
- 📁 `src/personal_assistant/main.py` (run_gateway finally block, line 972)
- finally 块用 `with suppress(Exception): await dispatch_runner.cleanup()`。如果清理失败（如文件句柄泄漏、状态损坏），错误被静默丢弃，可能掩盖导致下次启动出问题的资源泄漏。
- 💡 在 suppress 前记录 WARNING 级别日志。

### 🟡 MEDIUM

**_consume_task_exception 静默丢弃所有后台任务错误**
- 📁 `src/personal_assistant/main.py` (_consume_task_exception, line 2538)
- `task.result()` 在 `suppress(CancelledError)` 内调用——非取消异常被重新抛出后立即 suppress。后台任务失败完全不可见，零可观测性。
- 💡 记录异常：`try: task.result() except asyncio.CancelledError: pass except Exception: logger.exception('background task failed')`。

**后台 subscriber stop 静默吞掉所有异常**
- 📁 `src/personal_assistant/gateway/background_session_events.py` (stop 方法, line 89)
- stop() 捕获 `(asyncio.CancelledError, Exception)` 后 pass。如果 subscriber 停止时正在处理关键事件，失败不可见。
- 💡 对非 CancelledError 异常记录 DEBUG 或 WARNING 级别日志。

---

## 构造函数爆炸（3 个）

### 🟠 HIGH

**AgentRuntime.__init__：116 行，16 个参数**
- 📁 `src/agent/core/agent/runtime.py` (80-195)
- 16 个 keyword-only 参数，构造 10+ 内部协作者。这不是构造函数，是 DI 组装函数伪装成的构造函数。
- 💡 引入 RuntimeConfig 或 RuntimeBuilder dataclass。将协作者构造移到工厂函数（如 `build_agent_runtime`）。

**AgentLoop.__init__：16 个参数**
- 📁 `src/agent/core/agent/loop.py` (55-89)
- compaction 相关参数（compaction_planner, compaction_summarizer, compaction_settings, on_compaction）是内聚的一组。
- 💡 将 compaction 参数打包为 CompactionConfig，tool 参数打包为 ToolConfig。降到 ~8 个参数。

### 🟡 MEDIUM

**InboundPipeline.__init__：13 个参数**
- 📁 `src/personal_assistant/gateway/inbound_pipeline.py` (101)
- 💡 将相关协作者打包为 PipelineDependencies 或 PipelineConfig dataclass。

---

## 巨型文件（3 个）

### 🟠 HIGH

**personal_assistant/main.py：2558 行，113 个函数**
- 📁 `src/personal_assistant/main.py`
- 最大的 Python 文件。既是 CLI 入口又是整个 Gateway 组装层。
- 💡 提取 Gateway 构造/组装到专用模块（如 `gateway/builder.py`）。提取 kernel event observer 和 IM 连接工厂到独立模块。

**IM/infra/repositories.py：2700 行，102 个函数**
- 📁 `src/IM/infra/repositories.py`
- 代码库最大文件。包含多个 repository 类，每个 10-15 个方法，加上 schema 和 migration 逻辑。
- 💡 按 repository 拆分为独立文件：conversation_repo.py, message_repo.py, node_repo.py, profile_repo.py, event_repo.py。

### 🟡 MEDIUM

**auto_mode_gate.py：835 行，单个 hook 模块**
- 📁 `src/agent/platform/hooks/builtins/auto_mode_gate.py`
- setup 函数本身 193 行（CC=38），`_classify_action` 115 行（CC=27）。
- 💡 提取 `_classify_action` 和 transcript/XML 工具到独立模块。setup 保持为薄编排层。

---

## 深层嵌套（3 个）

### 🟠 HIGH

**_handle_streaming_delta：嵌套 8 层，CC=35**
- 📁 `src/IM/ws/gateway_handler.py` (732-845)
- 处理流式 delta 消息，不同 delta kind 的条件逻辑嵌套极深。
- 💡 提取每种 delta kind 的处理为独立方法，使用策略/分发模式。

**_listen_once：179 行，CC=35，嵌套 5 层**
- 📁 `src/personal_assistant/ws/im_connection.py` (288-466)
- WebSocket 消息监听器，不同消息类型的 if/elif 链深层嵌套。
- 💡 提取每种消息类型的处理为独立方法，使用消息类型分发表。

**_apply_input_key：141 行，CC=27，嵌套 7 层**
- 📁 `src/coding_cli/input/repl_input.py` (386-526)
- REPL 键盘输入处理，不同按键类型的 switch-like 逻辑深层嵌套。
- 💡 使用按键处理分发表。提取光标移动、历史导航、补全为独立函数。

---

## 上帝文件 / 高复杂度（3 个）

### 🟠 HIGH

**2558 行上帝文件，113 个函数，16 个类**
- 📁 `src/personal_assistant/main.py`
- 包含 gateway 启停、IM 连接管理、配置同步、kernel 生命周期、事件观测、WebSocket 消息处理、CLI 参数解析——全在一个模块。
- 💡 拆分为聚焦模块：gateway 生命周期、IM 事件观察器、配置同步客户端、CLI 入口。`_IMConfigSyncClient` 和 `_IMBootstrapClient` 类已是天然的提取边界。

**2700 行文件，14 个类，51 个 public 方法**
- 📁 `src/IM/infra/repositories.py`
- 包含所有 repository 类（User, SettingsPolicy, Conversation, Message, AgentProfile, Node, DeviceBind 等），每个类有自己的 SQL。
- 💡 按 repository 拆分为独立文件，每个可独立测试。

### 🟡 MEDIUM

**1195 行 commands 模块，文件末尾有过时 import**
- 📁 `src/coding_cli/commands.py`
- 16 个别名 import（从 coding_cli.render.*），line 1195 有一个放在最后一个函数定义之后的过时 import。
- 💡 将所有 import 移到文件顶部。考虑将 REPL 命令、权限流程、text-mode runner 拆分为独立模块。

---

## 超大组件（3 个）

### 🟠 HIGH

**AgentDetailPage：936 行巨型组件**
- 📁 `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
- 包含表单状态管理、验证逻辑、API mutation、模型/能力解析、预览渲染、完整编辑表单 UI。与 agent-create-page.tsx 重复了 normalizeAllowlist、validateDraft、resolveEffectiveFeatures。
- 💡 提取共享 agent-config-utils.ts。拆分为 AgentDetailHeader、AgentConfigForm、AgentBehaviorCard 子组件。将 mutation 逻辑移到 useAgentConfigMutation hook。

### 🟡 MEDIUM

**AgentCreatePage：725 行，工具函数重复**
- 📁 `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
- 与 agent-detail-page 重复了 normalizeAllowlist (line 21)、validateDraft (line 47)、resolveEffectiveFeatures (line 59)。
- 💡 提取共享工具到 agent-config-utils.ts。拆分为 CreateAgentFormHeader、CreateAgentNodeSelector、CreateAgentCapabilityToggles 子组件。

**v2 MessagePane：622 行，零 useCallback**
- 📁 `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`
- 管理草稿文本、待上传附件、mention 状态、自动滚动、composer 缩放、markdown 渲染——全在一个 622 行组件中。handler 直接定义在函数体中，未用 useCallback。13+ props 从 chat-workspace-page 透传。
- 💡 提取 MessageList、ChatComposer、MentionOverlay 子组件。handler 用 useCallback 包裹。考虑用 ChatContext 传递 agent 元数据 props。

---

## 重复代码（2 个）

### 🟠 HIGH

**_TERMINAL_STATUSES / _TERMINAL_RUN_STATUSES 在 7 个文件中重复**
- 📁 跨 3 个包的 7 个文件：`coding_cli/text_runner.py`, `coding_cli/commands.py`, `coding_cli/events/repl_events.py`, `agent/core/background_tasks/registry.py`, `agent/core/runs/registry.py`, `agent/platform/background_tasks/task_store.py`, `personal_assistant/gateway/inbound_pipeline.py`
- `{'completed', 'failed', 'cancelled'}` 集合在至少 7 个文件中各自定义为模块级常量。每份副本独立维护。
- 💡 在 `agent.core.types` 中定义一次（与 RunStatus enum 并列），统一 import。

### 🟡 MEDIUM

**原子写入模式在两个文件中完全相同**
- 📁 `src/agent/core/skills/writer.py` (340-354) 和 `src/agent/core/memory/store.py` (448-462)
- fdopen + fsync + replace，加上 except Exception 清理 tmp_path。两个文件，同一段 15 行代码。
- 💡 提取到共享工具（如 `agent.core.utils.fileio.atomic_write`）。

---

## 资源泄漏（2 个）

### 🟠 HIGH

**_spawn_process 日志文件句柄泄漏**
- 📁 `src/personal_assistant/main.py` (_spawn_process, line 2553)
- 通过 `_kernel_log.open('ab')` 打开日志文件传给 subprocess.Popen 作 stdout/stderr，但文件句柄从未关闭。`_log_file` 是局部变量，出作用域即丢失。Popen 对象不会关闭该句柄。
- 💡 将文件句柄存到 Popen 包装器或资源追踪器上，进程终止时关闭。

**SQLite 连接反复开关，无连接池**
- 📁 `src/personal_assistant/channels/web_relay_adapter.py` (RelayDeduplicationStore._connect, line 111)
- 每次调用 add()、`_purge_expired_locked()`、`_init_db()` 都新建 `sqlite3.connect()` 再 close。高负载下连接抖动。GroupContextStore._connect (line 119) 也有同样问题。并发访问同一 SQLite 文件可能触发 SQLITE_BUSY。
- 💡 使用单个长生命周期连接（`check_same_thread=False`）或连接池，类似 IM 服务使用的单 app-scoped 连接。

---

## fire-and-forget 任务（2 个）

### 🟠 HIGH

**add_tool 中 fire-and-forget create_task 无异常处理**
- 📁 `src/agent/core/agent/tool_executor.py` (add_tool, line 94)
- `asyncio.create_task(self._process_queue())` 未存任务引用也未加异常回调。如果 `_process_queue()` 抛异常，只在事件循环异常处理器中以 warning 形式出现——生产环境容易漏掉。
- 💡 存储任务引用或加 done callback 记录异常。

### 🟡 MEDIUM

**后台 hook create_task 无异常回调**
- 📁 `src/agent/core/hooks/runner.py` (background hook, line 200)
- 后台 hook 通过 `asyncio.create_task(_run(), ...)` 启动，内部 `_run()` 捕获 Exception，但外层 create_task 没有 done callback。如果 `_run()` 抛出逃脱其 handler 的 BaseException 子类，会成为未处理任务异常。
- 💡 给创建的任务加 done callback 捕获并记录逃脱内部 handler 的异常。

---

## 输入验证缺失（2 个）

### 🟠 HIGH

**Gateway WebSocket handler 只捕获 ValueError**
- 📁 `src/IM/app.py` (gateway_websocket, line 348)
- 只捕获 ValueError 发送错误帧并关闭（code 1003），其他异常类型（如 JSON 格式错误的 TypeError、内部状态的 RuntimeError）会作为未处理 500 传播，可能让 WebSocket 处于半开状态。
- 💡 捕获更宽的异常集（至少 Exception），或使用 FastAPI 异常处理中间件。

### 🟡 MEDIUM

**配置解析不验证 URL scheme**
- 📁 `src/personal_assistant/config/local_store.py` (_parse_im_service, line 692)
- 验证 url 是非空字符串，但不检查是否以 http:// 或 https:// 开头。`ftp://...` 或裸主机会通过验证但在 httpx 连接时才失败。
- 💡 加 URL scheme 验证：确认 URL 以 http:// 或 https:// 开头。

---

## 死代码（2 个）

### 🟠 HIGH

**已废弃的 v1 message-pane（1109 行）仍附带完整测试套件**
- 📁 `src/IM/frontend/src/features/chat/components/message-pane.tsx`
- 标记 `@deprecated`，有 `TODO(feat-340-v2-cleanup)` 待删除，但仍保留 1109 行源码和 946 行测试。生产路由已只挂载 v2 路径。死代码增加 CI 时间、bundle 分析噪音，且混淆了哪个 surface 是正式版。
- 💡 删除 message-pane.tsx 及其测试套件。删除前将真正共享的工具（toErrorMessage, getFailureAppearance）移到共享模块。

### 🟡 MEDIUM

**已废弃的 v1 conversation-list 仍存在**
- 📁 `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- 与 v1 message-pane 一起标记 @deprecated。如果 v2 chat surface 是唯一生产路径，这 304 行及关联测试是死重。
- 💡 随 v1 message-pane 一起清理。

---

## useEffect 中的过时闭包（2 个）

### 🟠 HIGH

**useEffect 读取 streamState 但未放入依赖数组**
- 📁 `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx` (272-290)
- useEffect 体内访问 `streamState.conversation_id` 和 `streamState.messages`，但依赖数组只有 `[conversationId, messagesQuery.data]`。这是过时闭包：effect 触发时读到的是过时的 streamState，可能导致切换会话时 token_usage 合并逻辑错误。
- 💡 将 streamState 加入依赖数组，或重构为从 ref 读取 streamState（类似 line 296 的 sendersByIdRef 模式）避免 effect 在每次 reducer dispatch 时重新触发。

### 🟡 MEDIUM

**空依赖的 useEffect 捕获模块作用域的 openChatStream**
- 📁 `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx` (298-303)
- useEffect 依赖 `[]` 但从组件/模块作用域捕获 dispatch 和 openChatStream。虽然 dispatch 稳定（来自 useReducer）且 openChatStream 是模块作用域的，但模式脆弱——如果任一变为动态，effect 会静默使用过时引用。
- 💡 注释说明 `[]` 为何安全。或将 stream handle 初始化移到 useStreamConnection 自定义 hook 中。

---

## Flaky 测试（2 个）

### 🟠 HIGH

**时间相关断言容差过窄，负载下会 flake**
- 📁 `tests/unit/test_streaming_tool_executor.py` (146, 174, 197)
- 3 个断言比较挂钟时间戳，容差仅 80ms 和 100ms（如 `abs(t2 - t1) < 0.08`）。依赖 asyncio 调度和 CPU 负载。文件还有 14 个 `asyncio.sleep()` 用于同步而非使用正确的 async 协调原语。
- 💡 将时间断言改为顺序断言（started before/after）。将 asyncio.sleep 同步改为 asyncio.Event 或条件变量。

**硬编码 time.sleep(2.5) 等待 token 过期**
- 📁 `tests/im_service/unit/test_auth_service.py` (line 103)
- `test_verify_access_token_rejects_expired` 用 `time.sleep(2.5)` 等待 access_ttl_seconds=2 的 token 过期。每次测试增加 2.5 秒，系统慢时会失败。
- 💡 用 freezegun 或 time_machine 快进时间。设小的 access_ttl_seconds 并 mock 时间流逝。

---

## 测试文件过大（2 个）

### 🟠 HIGH

**测试文件超 1000 行（1027 行）**
- 📁 `tests/unit/personal_assistant/test_local_store.py`
- 最大的 Python 测试文件。可能覆盖了多个关注点，可以分离。
- 💡 按关注点拆分为聚焦的测试文件（如 config 加载、config 验证、config 持久化）。

**测试文件 915 行，24 个测试函数**
- 📁 `tests/unit/test_background_hook_fork.py`
- 结合 test_background_hook_fork_conversation.py 中的 6 个重复测试，有效测试面 1207 行。多个测试有 78-117 行 setup 才到第一个断言。
- 💡 将复杂 mock setup 提取为可复用的 fixture 或 helper factory。

---

## 测试 setup 过大（2 个）

### 🟠 HIGH

**单个测试 117 行 setup 才到第一个断言**
- 📁 `tests/unit/test_background_hook_fork.py` (test_fork_executor_denies_unlisted_tool_at_execution_layer)
- 117 行 mock 组装才到第一个 assert。测试意图不透明，改 setup 风险大。
- 💡 提取 mock setup 为专用工厂函数或 fixture。测试应读起来：setup（简短）→ action → assertions。

### 🟡 MEDIUM

**77 行 setup 才到第一个断言**
- 📁 `tests/unit/test_idle_callback.py` (test_idle_callback_renders_background_events)
- 💡 创建可复用的 render helper 或 fixture 封装通用 setup 模式。

---

## 参数爆炸（1 个）

### 🟠 HIGH

**_execute_loop：17 个参数**
- 📁 `src/agent/core/agent/runtime.py` (1232-1274)
- 大多数参数直接透传给 AgentLoop.run，是参数穿透问题。
- 💡 创建 TurnConfig dataclass 打包所有 per-turn 参数。

---

## 全局可变状态（1 个）

### 🟠 HIGH

**模块级可变 dict run_context_store 被多个 async 任务共享**
- 📁 `src/personal_assistant/main.py` (1433)
- `_run_context_store: dict[str, dict[str, str]] = {}` 是模块级可变 dict，被多个 async 协程（observer, _make_run_update_processor）无锁修改。并发 run 生命周期事件可能存在竞态。
- 💡 封装到带 asyncio.Lock 的类中，或使用 asyncio 安全数据结构。至少文档化单线程事件循环假设。

---

## 硬编码密钥（1 个）

### 🟠 HIGH

**硬编码默认 auth token DEFAULT_LOCAL_KERNEL_TOKEN**
- 📁 `src/personal_assistant/config/local_store.py` (21)
- `DEFAULT_LOCAL_KERNEL_TOKEN = "nano-local-gateway"` 作为 fallback auth token（line 502）使用。在非 localhost 部署中是凭证泄漏风险。
- 💡 首次启动时生成随机 token 并持久化，或强制要求设置环境变量。

---

## 竞态条件（1 个）

### 🟠 HIGH

**accept_relay 中 contains/remember key 检查非原子**
- 📁 `src/personal_assistant/channels/web_relay_adapter.py` (WebRelayAdapter.accept_relay, line 186)
- `accept_relay()` 先调 `_contains_seen_key()` 再调 `_remember_seen_key()`，两个操作非原子。虽然 dedup store 内部有锁，但 WebRelayAdapter 自身对 check-then-act 序列无锁。并发调用时两个都可能通过 contains 检查才执行 remember，导致重复处理。
- 💡 将 check-and-add 合并为 dedup store 上的单原子操作，或给 accept_relay 方法加锁。

---

## 超大前端文件（1 个）

### 🟠 HIGH

**im-chat-api.ts：2190 行，110 个函数，42 个 export**
- 📁 `src/IM/frontend/src/features/chat/im-chat-api.ts`
- 所有 IM chat API 逻辑在一个文件中：认证、会话 CRUD、消息 CRUD、WebSocket 管理、上传处理、mention 解析、用量指标。
- 💡 拆分为聚焦模块：chat-conversation-api.ts, chat-message-api.ts, chat-stream.ts, chat-upload.ts, chat-mention-api.ts。用 barrel index.ts re-export 保持现有 import 路径。

---

## 重复逻辑（1 个）

### 🟠 HIGH

**normalizeAllowlist/validateDraft/resolveEffectiveFeatures 在 3 个文件中重复**
- 📁 `agent-detail-page.tsx` (line 25), `agent-create-page.tsx` (line 21), `allowlist-selector.tsx` (line 24)
- 任何 bugfix 都必须在多处同时修改。
- 💡 提取到共享 agent-config-utils.ts 模块。

---

## 缺少 Error Boundary（1 个）

### 🟠 HIGH

**路由树中无任何 error boundary**
- 📁 `src/IM/frontend/src/app/router.tsx`
- 所有路由未设置 errorElement 或 React error boundary。任何页面的未捕获渲染错误会导致整个应用白屏，无恢复路径。React Router v6 原生支持 errorElement。
- 💡 给根路由加 errorElement 包裹 ErrorFallback 组件。考虑为 /chat 和 /settings 加分区 error boundary 隔离故障。

---

## 巨型模块（1 个）

### 🟠 HIGH

**personal_assistant/main.py 是 2558 行巨型模块，113 个函数**
- 📁 `src/personal_assistant/main.py`
- 包含整个 gateway 启停、WebSocket 处理、配置管理、heartbeat 调度、agent 生命周期、channel 路由等。113 个函数定义，极难独立测试、维护或理解。
- 💡 分解为聚焦模块。gateway/ 子包已存在但 main.py 绕过了它。

---

## 死代码 / 未使用的 facade（3 个）

### 🟡 MEDIUM

**IM/models.py 是未使用的遗留 facade**
- 📁 `src/IM/models.py` (23 行)
- re-export IM/domain/models.py 的模型，但 src/ 中无任何生产代码 import 它。所有生产 import 直接指向 IM.domain.models。只有测试引用。
- 💡 删除此文件，更新测试 import 为 IM.domain.models。

**IM/repositories.py 是未使用的遗留 facade**
- 📁 `src/IM/repositories.py` (32 行)
- re-export IM/infra/repositories.py，但 src/ 中无任何生产代码 import。只有测试引用。
- 💡 删除此文件，更新测试 import 为 IM.infra.repositories。

### 🟢 LOW

**IM/domain/__init__.py re-export 与直接 import 重复**
- 📁 `src/IM/domain/__init__.py`
- 无生产代码使用 `from IM.domain import X`——所有 import 直接走 `from IM.domain.models import X`。`__init__.py` 是死重。
- 💡 要么移除 re-export，要么统一 import 使用包级 surface。

---

## 硬编码 URL（2 个）

### 🟡 MEDIUM

**core dataclass 默认值硬编码 localhost URL**
- 📁 `src/agent/core/llm/factory.py` (27)
- `LLMFactoryConfig` 的 `base_url: str = "http://127.0.0.1:4000"` 作为字段默认值。core 库耦合了特定本地代理配置。
- 💡 默认值用 None，运行时从 env/config 解析。默认值放在产品层（coding_cli 或 personal_assistant），不在 agent.core。

**硬编码 localhost dispatch URL 注入 session 元数据**
- 📁 `src/personal_assistant/gateway/inbound_pipeline.py` (406)
- `gateway_dispatch_url` 构造为 `f"http://127.0.0.1:{port}/internal/dispatch"` 注入每个 session。如果 gateway 绑定非 loopback 接口则失效。
- 💡 从实际绑定地址或配置字段派生 URL，不要假设 127.0.0.1。

---

## print() 代替 logging（2 个）

### 🟡 MEDIUM

**print() 用于错误报告而非 logging**
- 📁 `src/coding_cli/render/context_budget.py` (32, 37)
- `context_budget_hint_for_ratio` 在 LLM 客户端不可用或返回无效数据时用 print() 输出错误到 stdout。
- 💡 使用项目结构化 logger 或已有的 error presenter 模式。

### 🟢 LOW

**Gateway 启动消息用 print() 而非 logging**
- 📁 `src/personal_assistant/main.py` (116-137)
- 多个 print() 直接输出启动状态、health URL、错误诊断到 stdout/stderr。CLI UX 可接受，但结构化 logging 更一致。
- 💡 运维消息用 logger；print() 只用于面向用户的 CLI 输出。

---

## 前端测试过大（2 个）

### 🟡 MEDIUM

**前端测试文件 946 行，31 个测试用例**
- 📁 `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
- 最大前端测试文件。renderMessagePane helper 抽取得不错，但仍在一个 describe 块中覆盖了太多关注点。
- 💡 按功能区域拆分为聚焦的 describe 块或独立文件。

**前端测试文件 679 行**
- 📁 `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
- 结合 agent-edit.test.tsx (455 行) 和 agent-create.test.tsx (364 行)，agents 设置功能有 1498 行测试代码。
- 💡 审查是否有共享测试 setup 可提取到公共 agents 测试 helper 模块。

---

## 废弃 API（1 个）

### 🟡 MEDIUM

**用 logger.warn() 而非 logger.warning()**
- 📁 `src/agent/core/agent/runtime.py`, `tools/registry.py`, `agent/loop.py` (1054, 315, 519)
- agent.core 中 10+ 处使用 `logger.warn()`，该方法自 Python 3.3 起已废弃。正确方法是 `logger.warning()`。
- 💡 全局替换 `.warn()` 为 `.warning()`。

---

## 技术债 TODO（1 个）

### 🟡 MEDIUM

**TODO(bugfix-355) 标记未完成的迁移**
- 📁 `src/agent/platform/tools/safety.py` (110)
- `TODO(bugfix-355): After write/edit tools fully migrate to tool-level check_permissions, this method is only used by test code.`
- 💡 跟踪并完成 bugfix-355 迁移。迁移完成后删除死代码路径。

---

## 静默错误处理（1 个）

### 🟡 MEDIUM

**权限请求头 JSON 序列化失败静默 pass**
- 📁 `src/coding_cli/commands.py` (374)
- `except Exception: pass` 在 `json.dumps` 失败时静默丢弃 tool_input。用户看到截断的权限请求，不知道信息丢失了。
- 💡 fallback 到 `repr(tool_input)` 或 `str(tool_input)`，确保用户总能看到内容。

---

## 缺少超时（1 个）

### 🟡 MEDIUM

**Heartbeat scheduler 调 kernel 无超时**
- 📁 `src/personal_assistant/scheduler/heartbeat_scheduler.py` (_submit_run, line 192)
- `_submit_run` 调用 `await self._kernel_client.create_session(...)` 和 `self._kernel_client.submit_message(...)` 无超时。如果 kernel 挂起（如 LLM provider 宕机、session 文件损坏），heartbeat tick 会永久阻塞，阻止后续 heartbeat 评估。
- 💡 用 `asyncio.wait_for()` 包裹 kernel 调用，设可配置超时。

---

## 缺少错误处理（1 个）

### 🟡 MEDIUM

**send_json_await_ack 的 future 在连接断开时可能永久挂起**
- 📁 `src/personal_assistant/ws/im_connection.py` (send_json_await_ack, line 256)
- 创建 Future 后 `return await ack_future`。如果 WebSocket 在 ack 到达前断开，且断开发生在 `_flush_pending_frames` 和 await 之间，或 `_mark_disconnected` 在 future 创建前运行，await 会永久挂起。
- 💡 给 await 加 `asyncio.wait_for` 超时，确保断开时 future 总被 resolve。

---

## 缺少事务（1 个）

### 🟡 MEDIUM

**Schema migration 多条 DDL 语句无显式事务**
- 📁 `src/IM/infra/db.py` (initialize_schema, line 180)
- 通过 executescript 运行 `_SCHEMA_SQL`（自动 commit），然后运行各 migration 函数执行 ALTER TABLE。如果 migration 中途失败（如磁盘满），schema 处于部分迁移状态。
- 💡 将所有 migration 调用包在单个显式事务中，或确保每个 migration 幂等可安全重试。

---

## 共享可变状态（1 个）

### 🟡 MEDIUM

**sent 列表公开可变且无同步**
- 📁 `src/personal_assistant/channels/web_relay_adapter.py` (WebRelayAdapter.sent, line 163)
- `sent` 是普通 list，在 send() 中 append，可能被测试代码或诊断读取。并发 async 上下文中并发 append 可能出问题。列表还是 public 属性，外部代码可无协调修改。
- 💡 改为私有（`_sent`）并提供只读访问器，或使用线程安全集合。

---

## JSX 中内联对象（1 个）

### 🟡 MEDIUM

**UserMenu 有 15+ 个内联 style={{}} 对象**
- 📁 `src/IM/frontend/src/app/shell/user-menu.tsx` (74-185)
- 每次渲染为 15+ 元素创建新的 style 对象引用。
- 💡 将重复的 style 模式提取为 CSS 类或模块级 style 常量。动态部分用 className + CSS 变量。

---

## 未使用 React.memo（1 个）

### 🟡 MEDIUM

**整个前端代码库零 React.memo 使用**
- 📁 `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`（全代码库范围）
- grep 所有非测试 .tsx/.ts 文件，React.memo 或 memo() 使用为零。聊天应用消息列表频繁重渲染（新消息、输入状态、状态更新），memo 化消息气泡组件、头像组件和侧边栏可显著减少不必要渲染。
- 💡 优先 memo 化消息列表项组件（内部渲染循环）、Avatar、ConversationSidebar。消息列表项用 React.memo + 精确比较函数。

---

## Props 透传（1 个）

### 🟡 MEDIUM

**MessagePane 接收 13+ props，零 React context 使用**
- 📁 `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` (117-133)
- 解构 13 个 props。其中 nodeName, nodeStatus, agentColor, agentInitials 都从父组件的同一 agent context 派生。整个前端无 useContext/createContext 使用（零结果）。
- 💡 创建 ChatContext 提供 agent 元数据（name, status, color, initials）和会话状态。MessagePane props 可从 13 降到 ~7。

---

## 测试 preamble 过大（1 个）

### 🟡 MEDIUM

**第一个测试函数前有 159 行 preamble**
- 📁 `tests/unit/test_cli_repl_input.py` (1-159)
- 类定义、mock setup、helper 函数占了 159 行。说明测试基础设施过于复杂，可能掩盖了实际测试逻辑。
- 💡 将 mock 类和 helper 移到专用 `_helpers.py` 或 `conftest.py`。测试文件聚焦测试函数。

---

## 测试桩文件过大（1 个）

### 🟡 MEDIUM

**测试桩文件 546 行**
- 📁 `tests/unit/_cli_kernel_stubs.py`
- `_cli_kernel_stubs.py` (546 行) 和 `_cli_async_stubs.py` (532 行) 共 1078 行。大桩文件是过度 mock 或测试面过度耦合内部实现的信号。
- 💡 审查是否可用依赖注入的真实实现简化，或拆分为更小的聚焦桩模块。

---

## 硬编码路径（1 个）

### 🟡 MEDIUM

**测试中硬编码 /tmp 路径而非 tmp_path fixture**
- 📁 `tests/unit/test_auto_mode_gate_hook.py` (89, 158, 167, 190, 210, 240)
- 6 个测试用硬编码的 `/tmp/f`, `/tmp/x` 路径而非 pytest 的 tmp_path fixture。test_gateway_handler.py 和 test_owner_scoped_repositories.py 也有类似模式。硬编码 /tmp 路径有并行测试冲突风险且不清理。
- 💡 所有文件系统操作使用 pytest 的 `tmp_path` 或 `tmp_path_factory` fixture。

---

## 硬编码端口（1 个）

### 🟡 MEDIUM

**6 个测试函数硬编码 localhost:8011 URL**
- 📁 `tests/unit/personal_assistant/test_im_auth_client.py` (41, 55, 70, 84, 100, 121)
- 全部 6 个测试硬编码 `http://localhost:8011` 作为 base URL。虽然用 mock transport 不真正连接，但硬编码端口造成网络依赖假象。
- 💡 用常量或 fixture 定义测试 URL，或用明显假 URL 如 `http://im-test.invalid` 明确 mock 性质。

---

## 死代码 / 孤立模块（1 个）

### 🟡 MEDIUM

**smoke_runtime.py 从未被 import 或引用**
- 📁 `src/personal_assistant/smoke_runtime.py`
- 定义了 gateway smoke-test 的 main() 入口，但整个仓库无任何 Python 文件、测试、脚本或 CI 配置引用它。已废弃。
- 💡 删除此文件，或如果仍需要则接入 CI/脚本入口。

---

## JSX 中内联箭头函数（1 个）

### 🟢 LOW

**20+ 处 onClick 使用内联箭头函数**
- 📁 多个前端文件
- `onClick={() => ...}` 模式在 20+ 处出现。列表项 handler 意味着每次渲染为 N 个项创建 N 个新函数引用。
- 💡 列表项点击 handler 提取为独立组件，用 useCallback 稳定引用。简单一次性 toggle 的性能影响可忽略。

---

## 不一致的模式（1 个）

### 🟢 LOW

**React import 风格不一致：default import vs named import**
- 📁 `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` (line 1)
- 用 `import React, { useEffect, useRef, ... } from "react"` 并引用 `React.ReactNode` 和 `React.Fragment`。其他所有文件只用 named import。
- 💡 `React.ReactNode` 改为 `type ReactNode` named import。`React.Fragment` 改为 `<>` 简写。移除 default React import 保持一致。

---

## 死代码 / 近乎未使用的模块（1 个）

### 🟢 LOW

**worktree_runtime.py 零生产 import，仅 1 个测试引用**
- 📁 `src/agent/platform/worktree_runtime.py` (69 行)
- 定义 `prepare_shared_runtime_files()` 用于 worktree symlink 管理，但 src/ 中无任何生产代码 import。唯一引用是单个测试文件。
- 💡 确认是否仍需要。如果只被仓库外脚本使用，文档化说明。否则考虑移除。

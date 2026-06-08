# feat-394 源码 review

> Reviewer: change-reviewer (source code pass)
> 审查范围：`git diff --stat origin/main...HEAD -- 'src/**'`（src/ 净增约 4750 行实现）
> 对照：design.md、docs/specs/、openclaw 参考实现

---

## CRITICAL（必修才能 merge）

### C1 — cron-state.json 全局共用，多 agent 调度状态互相污染

**文件:** `src/personal_assistant/main.py:2180`

```python
_cron_state_path = runtime_dir / "cron-state.json"
# ... 下方每个 agent tick 都共用同一个 state_store
state_store = CronSchedulerStateStore(state_path=_cron_state_path)
```

`_cron_state_path` 是 `runtime_dir / "cron-state.json"`，所有 agent 的 `CronSchedulerStateStore` 都指向同一个文件。`CronSchedulerStateStore` 以 `job_id` 为 key 存储 last_due；多 agent 时若不同 agent 恰好有 job_id 碰撞（均为 UUID，概率极低但非零），会造成静默跳过。更严重的是：这与 `CronJobStore` 按 agent workspace 隔离的设计矛盾——文档明确说「持久化落 per-agent workspace」，但运行态文件（last_due）却是全局的。

**建议修法:** `_cron_tick_for_agent` 内为每个 agent 单独构建 `state_path`：
```python
state_store = CronSchedulerStateStore(
    state_path=ws_root / ".nanoassistant" / "cron" / "state.json"
)
```
这与 `CronJobStore` 的 `<workspace>/.nanoassistant/cron/jobs.json` 路径规范完全一致，且天然隔离。估算：1 行修改。

---

### C2 — `_HeartbeatSpec` 在 tasks 模式下注入 1s sentinel schedule，tick 对该 spec 仍可能走 `spec.schedule` 分支

**文件:** `src/personal_assistant/scheduler/heartbeat_scheduler.py:718-723` / `344-402`

```python
_SENTINEL_SCHEDULE = _IntervalSchedule(interval=timedelta(seconds=1))
return _HeartbeatSpec(
    schedule=_SENTINEL_SCHEDULE,  # <-- sentinel，不是 None
    instructions=aggregated_instructions,
    tasks=tuple(tasks),
)
```

`tick()` 的执行路径：`if spec.tasks:` → 走 task loop；`else:` 走 `spec.schedule`。sentinel 只有当 `tasks` 非空时才不被访问。但当 `_parse_heartbeat_tasks` 解析失败（全部 task 格式错误被跳过）时，`tasks=()` 为空，`spec.tasks` 为 falsy，代码退到 `else` 分支，此时 `spec.schedule = _SENTINEL_SCHEDULE`（1s interval），会以 1 秒间隔持续触发 heartbeat——不是预期行为，也不是 silently skip。

**建议修法:** tasks 模式下明确 `schedule=None`，tick 对 `spec.schedule is None and not spec.tasks` 时直接 skip：
```python
return _HeartbeatSpec(schedule=None, instructions=aggregated_instructions, tasks=tuple(tasks))
```
tick 中 tasks 路径已正确处理空 due；else 分支已有 `spec.schedule is None` → 读 config.every，不需要额外判断，但需要确保 `tasks=()` 时不错误触发 1s sentinel。估算：1 行修改。

---

### C3 — `_cron_tick_for_agent` 在 main 中重复实现投递闭环，与 `_consume_heartbeat_run` 形成代码分叉

**文件:** `src/personal_assistant/main.py:2182-2315`

这个函数（约 135 行）内联了一套几乎与 `_consume_heartbeat_run` 相同的投递链：`seed run_context_store → consume kernel.stream → drive observer → C-awareness inject`。两者逻辑平行，任何一方 bug fix 都需要同步另一侧，而 code review 非常容易遗漏。

这不是轻微重复，而是双倍维护面。设计上两者本应共享同一 `_consume_run(record, ...)` 形式的函数（heartbeat 和 cron 都是"submitted run → stream → deliver"）。

**建议修法:** 提取 `_consume_submitted_run(run_id, kernel_session_id, agent_id, owner_user_id, ...)` 通用函数，heartbeat 和 cron 都调用它。估算可省 ~80 行，并消除分叉维护风险。（此项可降为 WARNING 但考虑到后续 bug 传播风险建议保持 CRITICAL）

---

## WARNING（应修）

### W1 — schedule 解析工具函数在 heartbeat_scheduler / cron_scheduler 中完全重复

**文件:** `src/personal_assistant/scheduler/heartbeat_scheduler.py:15-28,483-572,795-944`
`src/personal_assistant/scheduler/cron_scheduler.py:233-243,245-490`

以下代码在两个文件中**一字不差或细微差异地重复**：
- `_INTERVAL_PATTERN` 正则
- `_WEEKDAY_NAME_TO_CRON` 字典
- `_Schedule` Protocol
- `_AtSchedule` / `_IntervalSchedule` / `_CronSchedule` 三个 dataclass（含 `due_times_up_to` 逻辑）
- `_parse_cron` / `_parse_cron_field` / `_parse_cron_number`
- `_normalize_datetime` / `_floor_datetime` / `_parse_optional_datetime`

两者有细微差别（heartbeat 的 `_parse_cron_field` 对 step range 的 `(number - start) % step` 写法 vs cron 的 `range(start, end+1, step)` 写法），说明是独立编写而非 copy，后续会出现行为分叉。openclaw 只有一套 schedule 实现（`src/cron/schedule.ts`）供 heartbeat 和 cron 共用。

**建议修法:** 新建 `src/personal_assistant/scheduler/_schedule_primitives.py`，共享 `_Schedule`/`_AtSchedule`/`_IntervalSchedule`/`_CronSchedule` 以及所有解析工具函数，两个 scheduler import 它。估算可省约 200-250 行重复代码。

---

### W2 — `_append_awareness` 声明为 `async def` 但无任何 await，误导性

**文件:** `src/personal_assistant/scheduler/cron_runner.py:168-216`

```python
async def _append_awareness(self, ...) -> None:
    ...
    self._kernel_client.append_message(...)  # 同步调用
```

`append_message` 是同步的（`_KernelClientShim.append_message` 无 async），该方法声明为 async 没有必要，且调用方（`main.py:2299`）用 `await _cron_runner._append_awareness(...)` 调用，虽然功能上正确（await 一个 async def 不会出错），但造成误解——读者会以为里面有真正的 async 等待。

**建议修法:** 改为 `def _append_awareness(...)` 同步函数，相应调用方去掉 await。估算：2 处修改。

---

### W3 — `_HeartbeatSpec.schedule` 字段在 tasks 模式下承载语义模糊的 sentinel，docstring 误导

**文件:** `src/personal_assistant/scheduler/heartbeat_scheduler.py:177-187`

`_HeartbeatSpec.schedule` 的 docstring 写 `schedule: "_Schedule | None"`，注释说「schedule is None when no explicit at:/cron: is present」。但 tasks 模式返回时写入的是 `_SENTINEL_SCHEDULE`（1s interval），不是 None——文档与实现不符。加之 C2 描述的潜在危害，该字段的 None/sentinel 语义需澄清。

**建议修法:** tasks 路径改为 `schedule=None`（见 C2），并更新 docstring。

---

### W4 — `_cron_tick_for_agent` 每次 tick 重新构造 `CronRunner` 和 `CronJobStore`

**文件:** `src/personal_assistant/main.py:2200-2205`

```python
job_store = CronJobStore(workspace_root=ws_root)
state_store = CronSchedulerStateStore(state_path=_cron_state_path)
_cron_runner = CronRunner(
    agent_id=agent_id,
    workspace_root=ws_root,
    kernel_client=kernel_shim,
    session_binding_store=session_store,
)
```

每个 tick 每个 agent 都重建这三个对象，而 `CronRunner` 除了持有 `workspace_root`、`kernel_client`、`session_binding_store` 之外无可变状态。对于 N 个 agent、频繁 tick 的场景，每次分配+初始化是无意义开销。openclaw 的 cron scheduler 是 singleton，不按 tick 重建。

**建议修法:** 将 `_cron_runner` 和 `CronJobStore` 提升到 tick 外（如 dict[agent_id → CronRunner]），只在 agent 注册/变化时重建。轻微性能优化，也减少理解难度。

---

### W5 — `main.py` 中大量 `# noqa: SLF001` 通过私有属性 `._agents`、`._cron_tick_fn` 等为 PollingHeartbeatRunner 注入依赖

**文件:** `src/personal_assistant/main.py:2165-2336`（多处）

```python
heartbeat_runner._kernel_event_observer = _kernel_event_observer  # noqa: SLF001
heartbeat_runner._cron_tick_fn = _cron_tick_for_agent  # noqa: SLF001
heartbeat_runner._agents = pipeline._agents  # noqa: SLF001
_heartbeat_scheduler._agents_getter = lambda: pipeline._agents.values()  # noqa: SLF001
_heartbeat_scheduler._run_queue = pipeline._run_queue  # noqa: SLF001
```

共 7+ 处 `SLF001` noqa。这说明构造器设计不全——依赖在构造时应当注入，而非在 `build_runtime` 函数尾部通过私有属性 patch。每次补一个依赖就加一行 noqa，逐渐难以追踪哪些依赖是"可选"的哪些是"必须"的。

**建议修法:** 将 `kernel_event_observer`、`cron_tick_fn`、`agents` 等作为正式构造器参数（或 setters）。不是紧急修改，但是明确的设计改进信号。估算：整理后可消除 6-8 处 SLF001。

---

### W6 — `_cron_tick_for_agent` 内部重新定义 `_log` 遮蔽模块级 `_log`

**文件:** `src/personal_assistant/main.py:2190-2192`

```python
import logging as _cron_log  # noqa: PLC0415
_log = _cron_log.getLogger(__name__)
```

在函数作用域内重新绑定 `_log`，遮蔽了模块级 `_log = logging.getLogger("personal_assistant.main")`。虽功能上等价（`__name__` 相同），但每次 tick 调用时都重复 `getLogger` 调用，且有名字遮蔽风险（函数内其他地方如果引用模块级 `_log` 的期望行为会被改变）。

**建议修法:** 删去函数内的两行，直接使用模块级 `_log`。

---

### W7 — `cron_scheduler.py` 中 `_CronSchedule` 忽略 schedule dict 中的 `tz` 字段

**文件:** `src/personal_assistant/scheduler/cron_scheduler.py:400-404`

cron tool description 的 SCHEDULE TYPES 中写了 `"tz": "<optional-timezone>"`，cron tool 的 `_INPUT_SCHEMA` 也包含 `tz` 字段，但 `_parse_schedule_dict` 解析 `kind=cron` 时只用了 `expr`，忽略了 `tz`——导致 agent 写入的 `"tz": "Asia/Shanghai"` 完全无效，实际总以 UTC 执行。

设计文档里明确提到 `_CronSchedule` 包含 `tz` 参数（并引用 openclaw），但实现里 `_CronSchedule` 没有 `tz` 字段，`_matches` 总在 UTC 判断。

**建议修法:** `_CronSchedule` 增加 `tz: str | None = None`，`_matches` 在有 `tz` 时将 `now` 转换到对应时区后再判断 minute/hour。这是功能正确性问题，用户设置了时区就期望按本地时间触发。估算：约 15 行改动。

---

### W8 — `_parse_heartbeat_tasks` 用手写行扫描解析 YAML-like 格式，健壮性差

**文件:** `src/personal_assistant/scheduler/heartbeat_scheduler.py:604-697`

该函数约 93 行，用手工行扫描解析 HEARTBEAT.md 中的 `tasks:` 块。格式看似 YAML 但实际上是自定义逻辑（靠缩进判定 block 归属），有多个边界 case（嵌套、混合大小写、多 `-` 等）难以覆盖全面。openclaw 用 `yaml.parse` 直接解析。

此处不是 bug 但是潜在的解析失败点，且 93 行手写解析器比 `import yaml; yaml.safe_load(...)` 成本高很多。

**建议修法:** 用 `yaml.safe_load` 提取 `tasks:` 块，把解析工作交给成熟库。估算可将 93 行缩减到约 30 行，同时健壮性提升。

---

## SUGGESTION

### S1 — `trim_silent_tick` 直接读写 session JSONL，绕过 kernel 缓存

**文件:** `src/personal_assistant/main.py:1136-1192`

heartbeat 静默 tick 的 transcript trim 通过直接操作 session JSONL 文件实现（`read_text → write_text via os.replace`）。这与 cron `_append_awareness` M9 修复（不要绕过 kernel 缓存，用 `append_message`）形成对比——trim 这里还是在绕 cache。

从正确性角度，trim 之后的下一次 heartbeat run 会重新加载 session，kernel 的 `cache-first load` 如果还缓存了 trim 前的行数，会有不一致。实践中这可能不触发（trim 后很快有新 run 时 cache 可能被 evict），但这是同类问题的另一面。

**建议:** 补 `Kernel.truncate_session` SDK 方法，或用 `kernel.reload_session()` 使缓存失效。当前实现 functional 但有潜在缓存不一致风险。

---

### S2 — `reconcile_all_agents` 中 profile 解析代码与 `sync_agent` 完全重复（约 60 行）

**文件:** `src/personal_assistant/main.py:551-630` vs `src/personal_assistant/main.py:312-398`

两处都做「从 IM payload 构造 `AgentWorkspaceConfig`」，代码几乎一致（heartbeat_json 解析、features 解析、tool_allowlist 清理等）。抽取为 `_agent_config_from_im_payload(payload, ...)` 函数可消除约 60 行重复。

---

### S3 — `_is_heartbeat_content_effectively_empty` 函数中 local import 注释说「避免 top-level dep」但 `re` 模块已在顶部导入

**文件:** `src/personal_assistant/scheduler/heartbeat_scheduler.py:585`

```python
import re as _re  # noqa: PLC0415 — local import: this function is called rarely, avoids top-level dep
```

但 `re` 已在文件顶部以 `import re` 的形式导入（第 6 行），这个 local import 和注释都是多余的。

**建议:** 删去 local `import re as _re`，直接用模块级 `re`（或用内置 `_HEADER_RE` 等重用已有正则对象）。

---

### S4 — `CronRunner` 类中 `_append_awareness` 和 `_resolve_canonical_session_id` 方法未被外部调用，可设为内部实现

**文件:** `src/personal_assistant/scheduler/cron_runner.py:100,168,218`

`_submit_cron_job`、`_append_awareness`、`_resolve_canonical_session_id` 均以单下划线标记为私有，但 `main.py` 中通过 `_cron_runner._submit_cron_job`、`_cron_runner._append_awareness`、`_cron_runner._resolve_canonical_session_id` 直接访问（带 `# noqa: SLF001`）。说明 `CronRunner` 的接口设计不完整——公开方法（如 `run_job(job)`）应封装这些私有调用。

**建议:** `CronRunner` 增加一个 `async def run_job(self, *, job: CronJob, run_context_store: ..., owner_user_id: ..., observer: ...) -> None` 公开方法，把 `main.py` 的 `_submit_and_deliver_fn` 内联逻辑迁移进来，消除外部对私有方法的访问。

---

## 体量评估

4750 行里**可删/可简约估算 ~480-600 行**，分项如下：

| 条目 | 可省行数 | 说明 |
|---|---|---|
| W1 schedule 原语重复 | ~230 行 | heartbeat/cron 两份完整重复，抽共享模块 |
| C3 投递闭环重复 | ~80 行 | `_cron_tick_for_agent` 内联投递逻辑与 `_consume_heartbeat_run` 高度重复 |
| S2 profile 解析重复 | ~60 行 | `sync_agent` vs `reconcile_all_agents` |
| W8 tasks 手写解析器 | ~60 行 | 替换为 yaml.safe_load |
| C1 fix（1行） + C2 fix（1行） | ~2 行 | 但消除 bug，不是体量优化 |
| W5 SLF001 noqa 重构 | ~10 行直接消除，设计改进 | 构造器整理后消除 noqa |
| W6 / S3 小项 | ~5 行 | _log 遮蔽 + 多余 re import |
| W4 每 tick 重建对象 | 0 行删除，仅重构 | 性能改善 |
| W7 tz 支持 | +15 行（功能添加非体量削减） | 不算可省 |

**结论：** 功能的核心实现是必要的（heartbeat 调度重设计 + cron 子系统从无到有是真实需求），但约 10-13% 的实现量（480-600 行）来自跨文件重复（schedule 原语、投递链、profile 解析）和迭代过程中累积的冗余（sentinel schedule、多余 import 等）。体量增大的主要原因是 cron 子系统从零搭建（CronJobStore + CronScheduler + CronRunner + gateway WS RPC + IM 路由 + 前端），以及多轮 fix 迭代累积的 comments 与向后兼容层，而非过度设计。

---

*文件生成于 feat-394 source review pass，2026-06-08*

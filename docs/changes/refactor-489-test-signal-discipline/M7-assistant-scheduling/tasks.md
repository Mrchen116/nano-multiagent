# refactor-489-M7: assistant-scheduling — Tasks

> 对齐: ../design.md 的 refactor-489-M7 行与决策 1/2

## 目标

保留 schedule / heartbeat 用户或运维风险的最低层自动保护，消除迁移措辞、源码布局、私有步骤、自我复制的假链路和跨层重复；时序与并发风险保留或改成条件驱动验证。

## 退出标准

- [ ] schedule / heartbeat 开关、节律、active hours、静默结果、canonical session、cron 隔离执行/历史/关机收拢仍有直接保护。
- [ ] 迁移时的 OpenClaw 逐字基线、provenance/source scan、已退役符号不存在、仅 importable/interface 和重写生产逻辑的假链路测试已删除。
- [ ] cron / heartbeat / liveness 的重复覆盖收敛到最低合适 seam；真实异步时序不因可能不稳而被删除。
- [ ] M7 最窄切片门禁全绿，且无产品代码或 spec delta。

## 测试策略

- 被测行为（来自退出标准）：heartbeat/cron 独立开关与节律；不补跑、单次任务和多任务时序；heartbeat 静默或主动冒泡前的调度决策；cron 工具、隔离 session、手动执行、历史、awareness 和收拢；background/liveness 的启停与不丢事件。
- 已有测试在：本 milestone 派发 glob 命中的 32 个文件（基线 229 passed）；不新建超出 `test_{generic,idle,liveness,ticker}_*.py` / `personal_assistant/test_{background,cron,heartbeat,schedule}_*.py` 的文件。
- 落层/目录/marker：`tests/unit/`，marker：无；真进程与用户冒泡由已有 `tests/integration/` / `tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py` 拥有，M7 不复制。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；以处置前后 pytest collect/结果、路径审计和 diff 作为证据。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| heartbeat / cron 时序、无补跑与 timezone | `test_schedule_primitives.py` | keep | 共享 schedule primitive 是最低逻辑 seam；保留真实时序风险。`test_heartbeat_mode_fires_even_when_expired` 与 current spec 冲突已暂停，保留现状且不在 M7 修产品/spec，后续跟踪 [#224](https://github.com/Mrchen116/nano-multiagent/issues/224) | 文件 pytest + spec→source→test 证据 |
| heartbeat 开关、config cadence、active hours、live config 及 canonical session | `test_heartbeat_scheduler*.py`, `test_heartbeat_revision_ownership.py`, `test_heartbeat_session_binding.py` | rewrite-merge | 风险仍在；合并正/反重复和私有 parser/签名断言，保留 scheduler tick 可观察结果 | heartbeat scheduler 切片 pytest |
| HEARTBEAT_OK 不打扰用户 | `test_heartbeat_prompt_openclaw.py::TestHeartbeatOkSilenceToken`, `test_heartbeat_im_delivery.py` | rewrite-merge | 保留 current 协议 token 的最低 reply-visibility 断言；删除 OpenClaw 逐字提示基线与重复 IM DB 链路，真冒泡由 critical-path E2E 拥有 | 重写后单文件 + E2E 可收集性 |
| prompt 迁移逐字与 provenance 历史基线 | `test_cron_prompt_sections.py`, `test_heartbeat_prompt_openclaw.py::{TestHeartbeatPromptOpenclawParity,TestHeartbeatMessageOpenclawVerbatim}` | delete | 只保护历史措辞、来源注释与私有 builder，current spec 未锁字节 | 精准文本/source scan 归零 |
| 已退役 prompt vars/函数参数不存在 | `test_heartbeat_cron_vars_injection.py` | delete | 明确的 M9 迁移终态，且文件自述与其他 gate/golden 重复 | 文件删除 + M7 pytest |
| cron 工具公开 action/schema、权限与 per-agent 手动路由 | `test_cron_tool_openclaw.py`, `test_cron_tool_permissions.py`, `test_cron_tool_closure.py`, `test_cron_file_tools.py` | rewrite-merge | 保留 action/schema、读写权限、add/list/remove/run 和 per-agent isolation；删除 description 措辞、source/provenance/retired URL 扫描、interface 存在和与 contract 重复的 coding_cli isolation | cron tool 切片 pytest |
| cron job/store/scheduler 的持久化、多任务与一次任务 | `test_cron_scheduler.py`, `test_cron_scheduler_tick.py` | rewrite-merge | 用 store roundtrip 和公开 `tick()` 保护风险；删除 dataclass getter、固定文件布局、空 store、私有 `_compute_due_jobs` 重复 smoke | cron scheduler 切片 pytest |
| cron 隔离 session、awareness、run history、terminal 和 shutdown drain | `test_cron_{runner_awareness,runner_kernel_append,run_history,delivery_chain,execution_owner_chain,scheduler_tick}.py` | rewrite-merge | 保留用户追问、结构化历史、失败归因与关机不丢投递；删除 importable/class exists、raw-file 反向扫描、读取次数与测试自己重写 stream/context seeding 的假链路 | cron execution 切片 pytest |
| polling 环真实启停、单次 tick 故障后继续 | `test_cron_polling_runner.py` | rewrite-merge | 风险仍在；用 Event/条件等待取代任意 sleep，删除私有 task callback 和未调产品逻辑的 path-construction 假测试 | polling runner 单文件 pytest |
| heartbeat 静默成功清理与失败转终态 | `test_heartbeat_session_trim.py` | rewrite-merge | 保留按 run identity 清理和失败不丢 transcript；删除“旧私有方法不存在”的迁移反向断言 | 单文件 pytest |
| background subscriber/manager 重连、seal/close 和事件不丢 | `test_background_*.py` | rewrite-merge | 保留异步生命周期；删除 module/interface exists 语言级断言 | background 切片 pytest |
| CLI idle 输入、kernel/tool liveness ticker | root `test_{generic,idle,liveness,ticker}_*.py` | rewrite-merge | 保留真实输入与 await-bound 时序；删除完全复制 formatter 的 idle 假测试、重复 no-op 及重写 permission 内部线程的假 wiring | root M7 切片 pytest |

## Roadpoints

### R1 — 删除迁移基线与假链路

- 状态: DONE
- 步骤: 删除 prompt/provenance/source-scan、retired-symbol、module/interface exists、重写生产逻辑的假链路与跨层 heartbeat IM DB 重复，先确认每项真实风险的保留 owner。
- 验证: 受影响单文件/替代保护 pytest + 结构搜索。

### R2 — 收敛 cron 工具、调度与执行保护

- 状态: DONE
- 步骤: 将 public tool/store/tick/history/terminal/drain 收敛到最低行为 seam，合并正反重复与私有步骤断言。
- 验证: cron 文件切片 pytest。

### R3 — 收敛 heartbeat 节律、开关与 session 保护

- 状态: DONE
- 步骤: 保留 config cadence/live update/active hours/canonical session/silent cleanup，合并重复，保留并冻结与 current spec 冲突的 expired-at 时序簇。
- 验证: heartbeat + schedule 文件切片 pytest。

### R4 — 稳定 background / polling / liveness 时序保护

- 状态: TODO
- 步骤: 保留异步生命周期和 await-bound 风险，将可收敛的任意 sleep 改为条件驱动，删除自我复制的 idle/permission 假 wiring。
- 验证: background + root liveness/idle 文件切片 pytest。

### R5 — M7 边界与全切片收尾

- 状态: TODO
- 步骤: 对账 32 个原始文件的 keep/rewrite-merge/delete，确认无产品/spec/其他 milestone 路径变更，记录限制和后续候选。
- 验证: 全 M7 pytest、`git diff --check`、changed-path scope audit、pytest collect-only。

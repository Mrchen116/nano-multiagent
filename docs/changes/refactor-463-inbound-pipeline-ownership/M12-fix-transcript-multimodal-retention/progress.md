# M12 Progress

## Context

- Round 5 acceptance：20/20 用户场景通过，0 issue。
- Round 5 verification：FAIL，1 CRITICAL（silent heartbeat prefix trim 可删除后继用户历史）、3 WARNING（steer 图片降级、public SDK 契约缺口、format gate）。
- Round 5 code review：另确认 CronRunsStore materialized terminal history 随运行次数线性增长；critical background e2e 默认 Agent 未启用 bash，首次等待不构成有效产品证据。
- 用户约束：本轮现有 agent 结束后不再派发任何 subagent；M12 的实现、测试、复验、审查与发布由 orchestrator 本人完成。

## Decisions

- 数据修复必须发生在 Kernel conversation/transcript owner 内，以 run 的 terminal turn identity 选择性删除；不接受产品层 prefix truncate 或仅重置文件行数。
- 多模态 pending message 的 source of truth 是 `LLMMessage.content` 的 structured blocks；所有 steer/held/continuation 路径共用无损反投影。
- Cron durable JSONL 继续 append-only；只限制进程内 materialized terminal index，不删除审计历史。

## Evidence

### R1 — selective transcript cleanup

- C1 `ac8a91228` 先证明旧实现会按 JSONL 前缀截断，导致更晚用户 turn/reply 从 provider context 消失；同时证明 Kernel 当时没有中立清理 seam。
- C2 `ce8eb3773` 将清理下沉到 transcript/conversation owner：正常 turn 的全部消息持久化同一 `turn_id`，删除在 writer barrier + transcript mutex + conversation turn gate 内执行，并原子替换文件、修复后继 parent、重建 tail、失效已加载 state。
- public `Kernel.discard_run_messages()` 只接受 terminal run 的 canonical session/turn identity；运行中、未知及重复清理均返回 `False`，由 `7ddd172a0` 锁定。
- 静默 heartbeat 只委托 run identity；产品层 raw JSONL 扫描、行数 baseline 与 prefix truncate 已全部删除。failed/cancelled heartbeat 不触发清理。

### R2 — multimodal retention and bounded cron index

- active steer 与普通 turn 共用 `parse_input_parts()` + `render_user_content_parts()`；有可用图片时保留结构化 text/image blocks，纯文本仍保持 string path。
- held `/stop` 与非用户 terminal continuation 从 `LLMMessage.content` 反投影 canonical parts；聚焦回归覆盖图片在 pending、held 与 continuation 三条路径不降级。
- `CronRunsStore` 的 durable `runs.jsonl` 继续 append-only；live append 与 restart replay 都只在内存中保留每 job 最新 100 条 terminal 记录，accepted/running 全部保留且两种 materialization 结果相同。

### R3 — contracts and release gates

- unit delta 已归并到 canonical `docs/specs/kernel/sdk-boundary.md` 与 `runs.md`，记录 `try_steer()` inject-only/expected-run 语义和 `discard_run_messages()` selective cleanup 语义。
- 聚焦后端回归：`47 passed`。
- Python CI 同命令：`3443 passed, 1 skipped`；`ruff check .`、`ruff format --check .`、test naming/size contract 与 `git diff --check` 全绿。
- Frontend CI 同命令：`64 files / 604 tests passed`。
- 真实 proxy critical path：后台 bash 完成后同会话跟进消息 `1 passed`；测试栈退出后无残留 IM/Gateway 进程或 pid/config/state 文件。
- orchestrator 亲自执行 patch review（`539d5e965..HEAD`），逐项复核 transcript 删除边界、跨 loop 所有权、多模态反投影、cron active/terminal 保留与调用方，结果 `[]`；Round 5 的 1 CRITICAL + 3 WARNING 全部关闭。

## Commits

- `290076fa3` — M12 closure plan
- `ac8a91228` — C1 regression evidence
- `ce8eb3773` — transcript/multimodal/cron implementation
- `7ddd172a0` — no-op cleanup contract coverage
- `f8e2e04fd` — repository format gate closure

## Rollback

M12 独立提交；可按上面的 C1/C2/R3 commit 逐项回退，不影响已通过的 M1-M11 产品主链路。若只回退 public cleanup seam，必须同时恢复 heartbeat 的旧产品层实现，否则 silent tick 会重新残留在用户历史中。

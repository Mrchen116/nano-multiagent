# perf-650 — 产品验收报告

> 对齐 motivation.md；Round 1；mode=full；revalidation_mode=full。
> Validation snapshot: `40deea7f19794b73614e56c339fd02a88dd1ae7c → cc091e4b9a396e87a659fedadb296c5a924d80e4`。
> 验收时间：2026-10-23 23:39–23:44 Asia/Shanghai。

## Verdict

**pass**。Highest Required Action: pass；blocking/major/minor = 0/0/0；needs_re_review=false。

普通工作、真实 Workflow child、ACK 丢失重试、断线及 Node 重启之后的实际 IM 用量与原生已完成轮次完全一致。无 token 重计或漏计。本报告只裁决产品计量不变性，不替代性能基准或实现验证。

## 用户旅程体验

在专用隔离身份创建会话 `c_h52jcblt`，通过真实 `POST /im/v1/conversations/{id}/messages` 发起工作，通过消息历史和 `GET /im/v1/metrics/usage?agent_id=e2e` 独立观察结果。仅比较返回的 agent scope，从初始空统计开始，不累加 owner/conversation scope。

普通任务得到 completed 回复 `PERF650_ORDINARY_OK`。后台任务真实调用 Workflow，run `wf_4d38a596`，启动工具完成与后台完成分别可辨；后台返回 status=completed、result=`{"child":"PERF650_CHILD_OK:323"}`、duration_ms=11407，主 Agent 也将结果转述到聊天。没有将工具 launch 成功当作 child 完成。

后台 child 原生 session 为 `099e40ff-f66e-4cd6-9e81-2513974c616b`，parentSession 指向根 `44c2873d-16c1-4b61-ac55-41589ee6b765`，isSeeded=true。导出中包含继承的根 turn 1；按原生 assistant message ID 辨认该继承事实，不再次计入，只计 child 自己的 turn 2。后台完成后，metrics 为 4 turns / 64086 prompt / 524 completion / 64610 total，精确包含根三轮与 child 一轮。

透明 relay 测试夹具 arm 后，发送 `PERF650_ACK_LOSS_OK`。夹具显示 dropped=1，根 run `:4` 同一 run_id attempts=2；IM 只增加一轮 11564 tokens，累计 5 turns / 76174 total。之后显式断开测试 WS，再停止和启动该专用 Node；服务恢复 online，并处理离线期间排队的确认消息，实际回复 `PERF650_RESTART_OK`。最终统计只增加本轮 11621，累计 87795；重复读取稳定。

无客户端界面改动，按 design Runbook 选择真实 IM HTTP API；未评价浏览器/iOS 视觉，没有以 API 证据声称视觉验收。

## 版本与环境证据

- 验收开始核对 branch=`unit/perf-650`，HEAD 等于 validated_at；tracked tree 无修改，仅其他独立报告 untracked。
- 使用 caller 集中准备且声明来自 validated_at 的构建；独立核对构建文件时间：PA usage 23:33:33、DSH usage 23:33:38、Node CLI 23:33:46，均早于本次运行。
- IM `http://127.0.0.1:57982`；Node `wt-nano-multiagent-97373`，worktree 内 `.gateway-config.yaml`、`.dsh-runtime`、workspace；relay fixture `http://127.0.0.1:58479` 指向该 IM。
- 重启仅执行交接命令 `node apps/node/lib/cli.js stop/start --config .gateway-config.yaml`，未重初始化数据。重启输出 PID=5557；进程路径为 Node 24.22.1，配置及 DSH 子进程均来自受审 worktree。启动约 40 秒后恢复 online；没有将启动等待视作计量失败。
- 未读取受审实现定位根因；仅为 HTTP 批准请求字段查阅现有前端 permission-card 调用。未用内部 usage.read 作为产品入口，也未复用 worker 成功叙述。

## 实际对账

| 原生 own completed run | prompt | completion | total |
|---|---:|---:|---:|
| root `44c2873d…:1` 普通任务 | 10361 | 8 | 10369 |
| root `44c2873d…:2` 启动/读取 Workflow | 32514 | 457 | 32971 |
| child `099e40ff…:2` 计算 | 9744 | 16 | 9760 |
| root `44c2873d…:3` 后台通知回复 | 11467 | 43 | 11510 |
| root `44c2873d…:4` ACK 丢失 | 11555 | 9 | 11564 |
| root `44c2873d…:5` 重启后确认 | 11613 | 8 | 11621 |
| 合计，等于最终 IM agent scope | **87254** | **541** | **87795** |

原生对账使用本隔离 runtime 的 history exports：完成 turn 的 assistant/message usage（inputTokens 加已报告 cacheReadTokens，outputTokens、totalTokens），对继承 message ID 去重；未从 usage outbox 或内部 usage RPC 反推预期。普通轮消息气泡也报告 10369 total，与统计一致。

证据均为本 reviewer 实际生成，保留于 `/tmp/nano-perf650-evidence/`：

- `review-api.jsonl`：带时间戳的实际请求与响应（不记录 bearer token）。
- `messages-workflow.json`、`messages-restart.json`：完成回复、真实工具与后台结果。
- `reconcile-ack.json`：5 轮原生/metrics 对账，dropped=1、run :4 attempts=2。
- `reconcile-restarted.json`、`reconcile-final.json`：重启及重复读取后的六轮完整对账。
- `review-reconcile.py`：仅在临时证据目录中的独立对账脚本；原生 exports 位于本 worktree `.dsh-runtime/wt-nano-multiagent-97373/exports/`。

原始运行文件及凭据不提交；关键数值、run 身份与结论已在本报告持久记录。

## Reference Artifacts Reviewed

N/A。motivation/design 无前端原型或 must-match 视觉契约。已读 motivation、design 的 Runbook、current response-metrics、workflows、agent-work、auth-tenancy 相关契约及 worktree-runtime。

## 问题清单

无阻塞验收的问题。

Side finding（环境前置，非本 unit 计量回归）：当前测试模型的自动 reviewer 请求 reasoning low 被返回 UNSUPPORTED_REASONING_EFFORT，Workflow 转为原生通用批准卡。依照已授权的专用测试任务，在现有产品入口为这个无网络/文件访问的计算 Workflow 提交 Allow once 后完成；没有关闭审核、修改模型或配置绕过。自动审核不可用不影响本次用量对账，但该测试环境后续应修正 reviewer/model 配置。Regression Relation=unclear（环境模型能力）；Recommended Action=out-of-unit；Action Rationale=计量变更之外的审核前置，本轮原生批准恢复路径正常；未创建外部 issue。

请求准备时一次缺 sender_user_id 返回 403、一次批准缺 message_id 返回 500；随后按现有客户端字段重发成功。这些是 reviewer 手工 API 请求构造错误，不当作合法产品路径回归。

## 验收标准覆盖

### Requirement: 完成工作按实际用量计量 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 |
|---|---|---|---|---|
| 普通与后台工作 | motivation.md；design Runbook | 走既有真实消息及 Workflow 行为；按未变化的 provider 原生计数口径对账，排除 fork 继承重复事实 | 普通 marker、workflow `wf_4d38a596` completed；4 turns/64610；messages-workflow.json、reconcile-ack.json | pass |

### Requirement: 恢复不重计或漏计 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 |
|---|---|---|---|---|
| 断线与重启恢复 | motivation.md；design Runbook | 实际丢弃一次已送达报告 ACK 并断 WS，观察同 run 重试；再断线及停止/启动测试 Node；读取单 agent scope，与相同已完成原生事实比对 | run :4 attempts=2、dropped=1；5轮76174；重启后只新增 :5，6轮87795，重复读取不变；reconcile-ack/restarted/final.json | pass |

未运行旧二进制 A/B；不变性依据为 current 契约与实际 provider 原生完成事实，未宣称生产性能或旧版耗时比较。

## 上层文档同步

- [x] `SPEC.md`：无需更新，无跨包职责变更。
- [x] `docs/specs/`：无需更新；no spec delta，产品计数、权限和展示契约不变。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本 reviewer 未新增服务。共享隔离栈与 relay fixture 按交接由 caller 最终清理；重启后的 Node PID 已通知 caller，专用测试会话仅在该隔离数据中。

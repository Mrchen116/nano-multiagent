# refactor-672 — 验收报告

> 对齐 motivation.md 用户侧验收标准；Round 1，2026-10-28。
> Validation snapshot: `ff326c351 → 648b5439e914d6cf90f85a5296734c0e77e3c7eb`

## Verdict

**pass**。三项必验 Scenario 均通过，blocking / major / minor 问题均为 0。

## 用户旅程体验

按 design.md Runbook，以客户端相同 HTTP API、真实 IM WebSocket 和 SQLite 驱动专用服务 `http://127.0.0.1:53499`，独立执行读取、保存、刷新、拒绝越权、版本冲突和断连恢复。owner 保存后能看到新名称、Custom Instructions 与递增版本；失败不会显示候选已保存；重连后原操作确认成功，可继续读取。本 unit 无客户端变更，未评价 Web/iOS 视觉，也未运行模型或真实 Node 配置落盘。WS 节点为验收者控制的协议对端，模拟持有应用回执；不把此结果声称为真实 Node 工作区/模型执行验收。

服务由 caller 构建并交接，验收开始核对 checkout HEAD、clean status 与 PID 69336 的独立启动命令；没有重启共享服务。模型上下文基线不适用。专用 alice owner、bob 与 outsider 身份来自隔离环境。初始协议驱动曾缺必填 group_reply_policy、配置依赖和正确回包字段；按 API 错误与协议交接校正后重新执行有效旅程。这些驱动错误不计为产品失败；最终结论仅依赖校正后的独立观察。

## Reference Artifacts Reviewed

N/A。无原型、视觉或 must-match 契约；读取 motivation.md、design.md Runbook，以及 current `agents-nodes.md` 配置操作、`auth-tenancy.md` owner/空间权限和 `gateway-relay.md` 连接契约。

## 问题清单

无产品问题。

## 验收标准覆盖

| Requirement / Scenario | 期望来源 | 验证方式与实际证据 | 结果 |
|---|---|---|---|
| 配置编辑与空间权限保持 / owner 保存与刷新 | motivation.md；current agents-nodes、auth-tenancy | alice PATCH 200，将名称设为 `Reviewer saved`、custom_prompt 设为 `Reviewer preservation 672`；随后 live/mirror GET 200 均保持新值、profile_version=4。bob/outsider GET 与合法 PATCH 均 404。旧 version=1 PATCH 409 `profile_version conflict`，新值未覆盖。证据 A。 | pass |
| 配置未知结果可恢复 / 应用确认丢失或节点不可达 | motivation.md；current agents-nodes 的新离线请求/ACK 丢失契约 | 接到 apply 后不返回 ACK 并关闭节点连接，PATCH 返回 503 `config_apply_pending`；断线期间新 PATCH 同样待确认，未冒充成功。重连 status 请求仍用 `60aa9240ad9d45f98e1893518a9cc743`；返回匹配 fingerprint 的 applied 回执后 GET 200，名称 `Recovered original operation`、version=5；mirror 刷新一致。独立离线新写返回 409 `agent_node_offline`。SQLite 仅四条已接受操作、全部 committed，无 offline/stale/unauthorized 候选。最终旅程恢复期间只有一次 apply、原 ID status 查询，无重复 apply/create。证据 A/B/C。 | pass |
| 节点消息归属不变 / 连接更换与迟到结果 | motivation.md、design.md NodeRpc 契约 | 旧连接收到 get 请求 `df917533-e9e1-41da-8971-c3c9064d8222` 后注册新连接；从新连接冒用该 ID 回包、旧连接迟到回包均未完成原请求（各等待 300 ms，done=false），最终返回原持久配置，未采纳注入名称。新请求 `392c75a1-f4de-4a1c-94a1-458b4f94e830` 等待时再发旧 ID，done=false；只有新请求正确 ID 的当前连接回包获 ACK 并完成。证据 B。 | pass |

以上按现行契约走既有行为检验不变性；没有另启动基线版本做 A/B。连接场景选择替换连接与迟到结果这一必验分支，未扩展为所有 RPC 命令并发矩阵。创建工作区幂等没有真实 Node 文件系统证据；本轮验证更新操作不重发/不新建 operation，不声称实际创建工作区验收。

## 证据与清理

以下为本 worktree 临时验收证据，不提交运行数据：

- A：`.e2e-refactor-672/reviewer-evidence.json`，校正协议后的真实请求/响应；对应驱动 `reviewer.mjs`。
- B：`.e2e-refactor-672/reviewer-connection-evidence.json`，替换连接/迟到 ID/离线拒绝；对应驱动 `reviewer-connections.mjs`。
- C：`.e2e-refactor-672/reviewer-db-evidence.json`，只读 SQLite operation 状态及候选快照。

全部验收者启动的 WebSocket/HTTP 客户端已经关闭，脚本退出。IM 服务由 caller 最终清理；未操作生产、共享主仓或修改源码/测试/受控配置。报告未提交，由 caller 收口。

## 上层文档同步

- [x] `SPEC.md`：无需更新，产品边界未变。
- [x] `docs/specs/im/`：无需更新，no spec delta，验收符合已有契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — 合入并行变更后的 targeted 复验

> Validation snapshot: `b8fc5edef → fc0dca156b3c3cce9602d39e7c47a601ad86b038`，2026-10-28。

**Verdict: pass**，产品问题 0。针对 refactor-671 序列化归属/字节契约集成与 refactor-673 Task 关闭同步后的影响，独立复验配置保存、刷新、原 operation 恢复和附加回执字段；未重新运行所有平台或 RPC 矩阵。开始核对 HEAD 与 clean status，专用新 IM PID 84625、`http://127.0.0.1:58132`，fresh SQLite；构建版本由 caller 交接。第一轮记录及证据保留，没有以最终树覆盖第一轮版本。

| 原必验 Scenario | 本轮覆盖与结论 | 证据 |
|---|---|---|
| owner 保存与刷新 | **pass（重新实测）**。首次读 version=1；保存名称 `Round2 配置 😀` 及含中文、emoji、双引号、换行的 custom_prompt，PATCH 200/version=2；live 与 mirror GET 保持完整值。旧 version=1 写入 409；bob/outsider 合法读写仍 404。 | D |
| 应用确认丢失或节点不可达 | **pass（核心重新实测，其余 retained）**。第二次 apply ID `ebc5834d7bf24fb591d36895298b4d68` 收到后丢 ACK 并关闭连接；原 PATCH 及断线期间新修改均 503 config_apply_pending。重连后仅查原 ID status，匹配回执后 live/mirror GET 200/version=3、名称 `Round2 恢复 😀`，custom_prompt 完整保留。SQLite 仅两条 committed operation，没有为断线新写创建候选；恢复过程中没有重发 apply。无 pending 时独立新离线写 409 agent_node_offline 沿用 Round 1 B/C，相关离线入口本轮无影响。 | D/E；Round 1 B/C retained |
| 连接更换与迟到结果 | **pass（retained）**。沿用 Round 1 B：错连接回包、旧连接迟到回包和旧 request ID 均不完成当前请求；匹配 ID/current socket 才完成。并行合入范围为序列化归属和 Task 关闭，不改变本场景配置 RPC 的 socket/request 关联及门禁。 | Round 1 B retained |

指纹与旧回执字段集成证据：两条 operation 的候选指纹分别为 `bef095720d68b101ad044bfa40da5ae835a9eebb4b79693c26beace88d39027f`、`510fcdb1e1f1b8518d9ab6dac1347b17419b3983c1c8f67403038b8cc0f647b2`；WS apply、恢复 status 回执与持久 operation/gateway_result 中指纹一致。协议回执额外携带 `legacy_extra={"text":"旧字段 😀","order":[2,1],"nullable":null}`，只读 SQLite 检查两条 gateway_result 均完整保留该对象、数组顺序与 null。该证据证明真实边界字段保真与恢复关联；没有单独对旧版本执行字节级 A/B 或声称全面证明序列化算法等价。

本轮证据均在本 worktree `.e2e-refactor-672/`：D 为 `reviewer-round2-evidence.json`（驱动 `reviewer-round2.mjs`）；E 为 `reviewer-round2-db-evidence.json`。Round 1 文件未覆盖。所有本轮 WS/HTTP 客户端已关闭、脚本退出；IM 由 caller 清理。无真实 Node/模型/UI 结论，报告之外未修改受控文件。上层文档仍无需更新，no spec delta。

## Round 3 — M3 Work 完整事件链独立验收

> Validation snapshot: `94b06908d396c8039d820124c4d86cb32a75eaf4 → badc559a1937b9b7b34b75df4d5a3ba0f5137e22`，2026-10-28。

**Verdict: fail**。新增三条 Scenario 中两条 pass、一条 fail；1 个 major 阻塞。M1/M2 retained Round 2，不降低先前标准。

### 范围与真实旅程

本轮读取新增 motivation/design M3 与 current `docs/specs/im/agent-work.md`，开始核对固定 HEAD 与 clean status。通过真实 `GlobalAgent → InboxStore → WorkSync → IM HTTP/SQLite → Work 页面 API` 生成并回看主子执行。只替换 RuntimePort 的原生事件来源为验收者独立构造的确定性 fixture，不使用测试 runner、不声称真实模型执行。隔离新 NodeStore/InboxStore 绑定 `global / review-main`，关联 `review-child`，不存在旧原生上下文；fixture 不发起模型任务。

主轮工具原始参数为含中文、emoji、引号、换行的重复文本（8,000 次），结果为另一文本（9,000 次）；真实生产链经过分段上传，用户从 Work API 展开时内容逐值相同。正文、父子归属及主子统计分别保留。非 owner 有公司空间资格的 bob 可读主/子页，并未因此取得机器同步凭据。刷新返回同样的记录。界面未修改，未做 Web/iOS 视觉评价；该替代入口符合 M3 Runbook。

### Scenario 覆盖

| Requirement / Scenario | 实际入口与观察 | 结论 |
|---|---|---|
| Work 记录从生成到刷新保持真实完整 / 主子执行与工具明细回看 | PA 生成 10 条本地日志并由真实 WorkSync 确认 10；主轮 completed，工具 input/result 全文比较 true、耗时 9 ms；主轮 elapsed 23 ms，context_used=27、output=7、context_window=16384，未补 total_tokens；子轮 completed、usage=null，parent_session_id=review-main。刷新 JSON 一致。合法权限事实使新轮 waiting_permission → running → completed；开始事实单独保持 running，中心重启后 unknown，不虚构完成。证据 F/H/I。 | pass |
| Work 同步与重放保持同一身份 / 中断、重复与中心恢复 | PA stop/recover 后 journalSeq 仍10；已提交小事件重放200/through=10，改变同一身份的 payload 返回409 event_identity_conflict；跳至seq12仍through=10/expected=11。七段事件seq15首段重复仅received_parts=[0]、through=14，最后一段才through=15，重复首段不再投影。另一个七段seq16仅传首段后真实重启中心，pending位置保留且已完成主/子记录逐值不变；补齐后through=16。完整大文本可回看。证据 F/G/I。 | pass |
| Work 契约边界不扩大访问权限 / 畸形事件与无权来源 | tool_end.presentation.summary=8 经HTTP批量返回400 invalid_event、WS返回error；批量含合法前项仍未推进through=10。无权root返回403 scope_not_allowed，真人bob凭据访问同步游标401。旧turn_start/run_completed、null/省略统计及未知plugin扩展保存可读。但permission_request.options=[null]错误地200提交并推进到21，工作轮被置为waiting_permission，违反稳定字段无效不提交的要求。证据 F/H/I。 | **fail** |

### 问题清单

| ID | 严重度 | 真实观察与影响 | 处置 |
|---|---|---|---|
| M3-AC-1 | major / blocking | 真实HTTP POST journals/.../events，seq21、type=permission_request、payload={request_id:"malformed-options",options:[null]} 返回200；GET游标through_seq=21，SQLite保存该畸形payload，原completed轮permission-review变waiting_permission。无法从无效选项得出有效审批选择，且违反本unit接收边界原子拒绝标准。 | 交caller修复稳定权限字段校验，固定新版本后复验；本轮不能pass。 |

审查方提示该候选缺口后，验收者独立提交上述请求并读取API/SQLite复现，没有以审查叙述替代证据。其余通过场景不受此失败抹除，后轮可按影响 retained。

### 证据、环境与清理

证据位于本 worktree `.e2e-refactor-672/m3-acceptance/`，均为临时运行数据不提交：

- F：`reviewer-evidence.json`、`reviewer-journal.json`；驱动 `.e2e-refactor-672/reviewer-m3.mts`。
- G：`reviewer-restart-pending.json`、`reviewer-restart-evidence.json`；真实中心重启及分段续传。
- H：`reviewer-permission-evidence.json`；合法权限状态及M3-AC-1。
- I：`reviewer-db-evidence.json`；10条生产日志payload逐值相同、未知扩展内容与畸形权限落盘记录。

初始服务PID4739/http://127.0.0.1:52831由caller启动，已由验收者按授权停止。为中心恢复验证，验收者直接运行同版source、使用原DB及原runtime绑定启动PID6509/http://127.0.0.1:53159，未重新seed；新环境已写environment.json并交caller最终清理。所有验收WS/HTTP客户端、GlobalAgent、WorkSync及本地store已关闭。未操作生产、共享主仓或更改源码/测试/设计。

本轮未单独测普通聊天并发延迟、真实模型、原生轨迹或客户端视觉；不将fixture的主子记录解释为模型自主委派能力。上层文档仍无需更新，no spec delta；修复前本轮fail保留。

## Round 4 — M3-AC-1 targeted closure

> Validation snapshot: `badc559a1937b9b7b34b75df4d5a3ba0f5137e22 → 197da048e8975677e8e82f7e0f73f511e7f67687`，2026-10-28。

**Verdict: pass**。M3-AC-1 已关闭，未解决产品问题 0；保留 Round 3 的失败记录，不改写其历史裁决。

固定 HEAD 核对后，停止专用旧服务PID6509，以同一DB/runtime绑定启动新源码服务PID7760/http://127.0.0.1:53457。独立通过真实HTTP提交并读取 Work页面API/游标及SQLite，没有以自动测试通过代替产品观察。

| 必验 Scenario / 继承问题 | 本轮证据与保留范围 | 结果 |
|---|---|---|
| 畸形事件与无权来源 / M3-AC-1 | 在through=21处提交flat `options:[null]`和nested `permission_request.options:{id:"allow_once"}`，两次均400；每次重新GET游标仍21、完整Work页面JSON与提交前完全相同。SQLite无round4-invalid记录。合法嵌套option对象含字符串id及动态extra字段的事件随后200，状态waiting_permission → permission_resolved后running → turn_end后completed；SQLite保留中文/emoji、动态对象与null数组值。无权来源、其他畸形字段和合法旧别名沿用Round 3 F/I，修复只收紧权限options形状，不改变身份或事件入口。 | pass，M3-AC-1 closed |
| 主子执行与工具明细回看 | retained Round 3 F/H/I：主子归属、原始工具全文、真实统计、缺失数据null及刷新一致；本轮补验合法权限状态，未影响原生生产链。 | pass |
| 中断、重复与中心恢复 | retained Round 3 F/G/I：重放身份冲突、缺口、七段同步和真实中心重启恢复；本轮修复不改变分段/水位/持久投影职责，且两次非法写均不推进水位。 | pass |
| M1/M2 的三个原Scenario | retained Round 2（其连接隔离引用Round 1）；权限事件decoder修复不触及配置服务、RPC关联或配置指纹。 | pass |

本轮仅选择原问题的真实HTTP接收入口和完整Work回看闭环，不重跑未受影响WS/分段矩阵。证据为 `.e2e-refactor-672/m3-acceptance/reviewer-round4-evidence.json`、`reviewer-round4-db-evidence.json`，驱动 `.e2e-refactor-672/reviewer-m3-round4.mts`。Round 3 的畸形历史记录仍保留用于证据；本轮证明新输入被拒，不声称执行历史数据迁移。

全部本轮客户端已退出。PID7760为验收者重启的专用IM服务，已交caller最终清理，environment.json更新为该地址/PID。报告未提交；未修改产品源码、测试或设计。无UI/模型新增结论，no spec delta，上层文档无需更新。

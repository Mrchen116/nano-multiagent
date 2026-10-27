# feat-668 — 产品验收报告

> 下列Round1–4为原创unit625在旧基线的历史结果。迁至668并集成新main后，产品门禁须full复验；不能将下方PASS当作当前集成树已通过。见 [sync-review.md](sync-review.md)。

> 最新正式结论：**Round 4 full产品验收 pass**，冻结证据树 `86591326fb439a4cc68a651080980df8c1650df8`；实际业务执行树 `1862af639681defdb91651f50cc6e01459e63e0b`。下方保留R1/R2未通过历史及R3补验，最新Scenario覆盖与边界见Round 4。

## Round 1 — 中间报告，门禁尚未通过

- Validation snapshot: `5454f3140f9c92532c690db8dec80b9f77080384 → dfee3df40116757346ef6a7edcaa5d10734c9a61`。
- Branch: `codex/feat-625-ab-e2e`；独立 reviewer 实际核对 HEAD 与 clean worktree。executed_base 是获准独立基线，不声明为最新 main；未 fetch。
- Scope: full 产品验收。只走隔离 IM 的实际公开 API；没有调用 policy.review，没有阅读受审实现定位问题，没有使用静态测试成功替代产品结果。
- **Verdict: fail（当前门禁不可通过；必要场景 inconclusive，非已证明重试实现有缺陷）。** 本轮尚无通过的插件完整旅程，审批逐 attempt 证据亦不可取得。等待环境修复、明确再冻结及取证权限决定，不继续发送任务或采集数据。
- Highest required action: out-of-unit（先恢复验收环境与明确诊断消费权限；实现因果尚未确定）。Needs re-review: yes。

## 环境与实际覆盖

入口为 `http://127.0.0.1:53939`，测试 owner `u_6qmugetg`，node `wt-repository-95829`。独立读取确认 `/health` 200，`/openapi.json` 404；后者是 runbook 与实际入口差异，不以其成功作证明。公开身份、节点、capabilities、Agent config 与 Work 可用。无生产数据或外部 IM。

本基线缺少 current-workflow 的 daily 模板；caller 明确批准使用隔离 default 栈。它保留本轮需要的 IM/Gateway、测试身份、独立工作区、真实模型及公开 Work 路径，但不等同于 daily P/E/Q/PA 阵容、群与 seed 的覆盖。本轮追加独立 CC/Codex Global 合成角色，不声称运行过 daily。

caller 交接新 Node/DSH 进程与 build provenance；reviewer 未自行启停栈。reviewer 路由拟为独立本地代理 `56096` 转发既有服务中的 Luna；共享服务未修改。代理转发自测不是产品审核请求成功证明。所有已经发起的产品任务均在无故障注入状态下运行；尚未开始确定性故障矩阵。

## 用户旅程体验与最小观察结果

采用客户端同一公开 IM API 发业务任务，要求 Agent 自建并正式安装报销计算插件，随后真实调用两次：交通和住宿全额，餐费封顶 60，预期 A=480、B=370。不提供插件实现或准确工具参数，不允许失败后重复工具或绕过审核。以下仅保留必要状态、计数及定位符，不保留原始 Work、请求或会话内容。

| 实际旅程 | Agent / conversation | Work session | 观察结果 |
|---|---|---|---|
| 默认主模型 CC | `review361-cc-prep` / `c_lnuezzk3` | `87250f26-b064-44e1-aaf4-68cbf6f6755c` | DeepSeek Flash/high；turn 1 failed，402 Insufficient Balance / QUOTA，约 1.87 秒；无工具执行。 |
| 默认主模型 Codex | `review361-codex-prep` / `c_jkt1yfnq` | `bbaeb49e-03c7-4a60-9769-678cc3ea8dc9` | DeepSeek Flash/high；turn 1 failed，同类 QUOTA，约 1.83 秒；无工具执行。 |
| 获准替代主模型 CC | `review361-cc-sol` / `c_w5nasd1z` | `5b0058ad-b302-406c-9fc3-0fbd57423ee4` | Sol/high 可读取任务；describe_api 审核技术不可用，未创建/安装插件，业务工具调用 0；最终停止说明已实际发送，Work idle。 |
| 获准替代主模型 Codex | `review361-codex-sol` / `c_tv9149kt` | `e051bfd4-c3b2-4069-8f21-723fcf03310b` | Sol/high 可读取任务；同样在审核技术不可用后未完成插件旅程，业务工具调用 0；最终停止说明已实际发送，Work idle。 |

默认角色保持 profile version 2，替代 Sol 角色 version 1；未在旅程后修改 profile。Sol 是调用目录中已有模型，经 caller 另行批准后新建角色使用；不将其冒充 DeepSeek 默认模型成功。

| 策略 | 失败工具调用定位 | 最小实际结果 |
|---|---|---|
| CC | `call_ed1eabf1b8f74791ad4a5d8fc966deb1`，plugin_manager describe_api | 43ms；classifier_unavailable；Automatic review unknown (PI_AI_ERROR)；return_to_agent。 |
| CC | `call_97cb3e2545114167b67ff375bca0739c`，bash | 56ms；同类审核技术不可用。 |
| Codex | `call_35fdcecd3a084339bd4ff7979d77824a`，plugin_manager describe_api | 131ms；classifier_unavailable；Automatic review unknown (PI_AI_ERROR)；return_to_agent。 |
| Codex | `call_c06a69b77ec54edba9810beb2b128558`，bash | 115ms；同类审核技术不可用。 |

当时公开代理状态显示计划为空、used=0、holds 为空，只有既有自测记录，没有以上产品旅程审核请求的记录。该观察只证明代理 records 中无对应记录，不能推断 HTTP 请求未到达代理，也不据此推断实现根因。工具失败是技术不可用，不应当作有效策略 deny 或已测的服务故障恢复。Work 中轮次 completed 也不等于用户业务目标完成。

本 unit 无 UI 改动且允许 API 驱动；本轮未进行浏览器视觉验收，不声称桌面/iOS 画面通过。实际用户目标尚不可完成。

## Reference Artifacts Reviewed

已读新 unit `spec.md`、`design.md` reviewer runbook；权威 current-workflow AGENTS、change-workflow、change-reviewer 及 handoff、worktree-runtime；当前公开 API 行为规范和既有 E2E 客户端 helper。无 prototype 或 must-match 视觉 artifact，N/A。

## 问题与阻塞

| ID | Severity | Regression Relation | 期望 / 实际 | Recommended Action / rationale |
|---|---|---|---|---|
| R1-E1 | blocking（环境） | unrelated-existing（模型额度） | 默认主模型应能开始任务；实际两者 402 QUOTA，工具 0。 | out-of-unit：已获准以独立 Sol 角色继续，不充值、不改共享服务。保留默认路径未通过事实。 |
| R1-E2 | blocking（环境，待真实复验） | unclear（caller 后续归因为自建代理，见澄清） | 审核应可完成；实际两策略立即技术不可用，代理 records 无对应记录，不证明 HTTP 未到达。 | out-of-unit：caller 报告临时代理修复，等待新冻结 GO 后真实旅程复验；不由 reviewer 读实现猜测。 |
| R1-E3 | blocking（具体取证方法未完成） | unrelated-existing（方法受阻） | 需公开 session.observe 审计与 Work 关联；拟议脚本修改被工具拒绝，尚未执行 RuntimeClient，未取得 live 审计。 | out-of-unit：澄清并落实具体合法诊断方法；原合成回归和必要只读授权存在，不能表述为主人从未授权。不重试被拒方法或换工具、stdout/文件、Agent、私有 DB 绕过。 |

原始 Work 写文件曾被工具拒绝，后续遵守只读观察与最小结论限制，未重试写入或将原始内容复制进报告。caller 最初转述最小化 public observe 方法受阻，后经已持有回执澄清：被拒的是拟议脚本 edit，RuntimeClient 尚未执行；不是一次实际 session.observe 读取被拒，也不意味着所有审计只读均未获授权。reviewer 未取得 live 审计结果。不能用代理 HTTP 次数、合成 native 事件或 worker 测试冒充真实逐 attempt 审计。

## 验收标准覆盖

所有必验 Scenario 来源为本 unit `spec.md`；此表为本轮中间实际覆盖，不把准备好的方案标作已执行。

| Requirement | Scenario | 已执行证据 / 缺口 | 结果 |
|---|---|---|---|
| 临时故障在同一审核内有限恢复 | 服务恢复后继续原操作 | 未进入确定性注入旅程；未观察同一审核恢复后执行恰好一次。 | inconclusive |
| 临时故障在同一审核内有限恢复 | 持续故障耗尽 | 当前立即不可用不能替代三次预算耗尽；90s 独立预算、总 extras≤2、fallback 矩阵尚未实测。 | inconclusive |
| 空白、无效与永久失败采用不同边界 | 空白或非法判定 | invalid≤1 且共享总 extras≤2 尚未实测。 | inconclusive |
| 空白、无效与永久失败采用不同边界 | 明确拒绝或认证配置错误 | 当前 unknown/PI_AI_ERROR 不是有效 deny 或已确认 auth/config；CC 正常两阶段与 Codex 语义尚无产品证据。 | inconclusive |
| 停止优先于恢复和执行 | 请求中或退避时停止 | 活动审核/退避取消、无后续 attempt、无工具执行、迟到结果隔离尚未实测。 | inconclusive |
| 工作结果与审核恢复可核查 | 分清恢复与新调用 | Work 可定位主 session、工具 callId 与失败，但拟议诊断方法尚未执行，缺真实 attempt、分类、耗时与 usage；不等于所有必要只读授权被撤销。 | inconclusive |
| 工作结果与审核恢复可核查 | 全局 Agent 插件真实旅程 | 已真实发起两个模型配置下的 CC/Codex 产品旅程，均未完成安装及两次业务调用；环境阻塞使功能可用性未能成立。 | inconclusive |

## 继续验收所需最小权限与字段

不是申请原始会话导出。拟限定为上述合成 `review361-*` sessions 及后续明确批准的同前缀验收 sessions，在 owning Node/DSH 已由 caller 停止并核实退出后，通过本 checkout 对应公开 RuntimeClient 的 `initialize`、`session.observe` 只读诊断恢复同 profile/bindings。不得执行业务调用、重跑任务、读取私有 DB 或访问任何真实用户资源。

最小输出：sessionId、agentId、工具 callId、reviewId；最终 decision/category/route；真实已发生 attempts 的 ordinal、outcome/category、start/end 或 elapsed、delayAfter、reviewer/provider/model；extraUsed/invalidRecoveryUsed；可得 usage 数值或明确 unknown；必要的 stage/request/context-mode 区分标识；取消终态，以及若已有公开记录则输出资源终止是否确认。只处理选定 callIds，不输出请求/响应正文、prompt、聊天消息、工具完整参数、secret、完整 observation 或 profile 内容。

用途：将一次工具操作与内部恢复关联；检验次数与共享预算、永久错误不重试、时间与退避、取消和 fallback，避免把 CC 第二阶段或主 Agent 新调用算作重试。Work 的既有最小操作计数和结果用于工具执行 0/1 对照。代理请求日志只能辅助，不能代替 attempt 审计。

留存边界：仅报告中保留 case、关联 ID、必要计数/类别/时间及结论；不另存原始 observation 文件、不转发全量内容。诊断执行环境自身可能保留工具调用输出，不能声称绝对无留存。当前缺口是拟议具体消费者的脚本修改被工具拒绝且未执行，需 caller 澄清并落实合法方法；单纯改写输出格式不是绕过拒绝的理由。原合成 E2E 与必要公开只读授权存在，以上最小字段清单用于限定方法，不表示主人从未授权查看本轮合成结果。

## Round 1 追加澄清 — 不改变本轮 verdict

本次只依据已持有回执和 caller 更正修订报告，没有新增数据采集、产品任务或 RuntimeClient 执行。

1. reviewer 的首次拒绝明确承认操作为 bounded synthetic Work read，并明确称 read-only inspection 为合理替代；拒绝的是完整 Work JSON 落 ignored 文件的额外留存。caller 的第二次拒绝发生于消费者脚本 edit，尚未执行 RuntimeClient；caller 澄清这是工具按过宽 stdout 禁令阻断具体方法，不是所有公开必要审计只读授权均不存在。原方法仍停，保留实际审计未取得的 inconclusive。
2. 原报告把代理 records 无对应记录写成 HTTP 请求未到达，是超出观察的推断，现更正。caller 报告：全新临时 profile、工具空集、固定 READY 的纯连接 probe 复现 PI_AI_ERROR，底层为自建代理对带 query 的 `/v1/messages` 在记录前返回 404；仅修 owned ignored proxy 使用 URL pathname 并重启该代理后，同类 probe completed，最小基础设施记录为 path=/v1/messages、hasQuery=true、live200。该根因及修复为 **caller-reported**，并非 reviewer 新增读取或独立产品复验。
3. 连接 probe 不包含 Work/session.observe，不证明本轮自建插件、安装、两次业务调用或重试矩阵通过。等待另行冻结 GO 后真实旅程复验；R1 保持 fail 门禁、七项 Scenario inconclusive。

## 上层文档同步

- `SPEC.md`：当前未观察到需更改跨包架构的产品证据，无需由 reviewer 修改。
- `docs/specs/gateway/agent-capabilities.md`：目标重试契约待后续门禁及最终实现确认后由 owner 归并，当前不声称已验收。
- `AGENTS.md` / `CLAUDE.md`：无需更新。
- `docs/specs/CONTRIBUTING.md`：无需更新。
- runbook 健康入口 `/openapi.json` 与当前栈 404 的差异已报告 caller；本轮实际使用 `/health`，不修改权威文档。

本报告由 caller 统一处理提交；reviewer 不 commit。后续轮次追加，不覆盖本轮未通过事实。

## Round 2 — 真实旅程复验及故障矩阵进行中

- Validation snapshot: `5454f3140f9c92532c690db8dec80b9f77080384 → 1862af639681defdb91651f50cc6e01459e63e0b`。独立核对 HEAD 与 clean 状态后才发送任务；仍为获准 baseline，不声明最新 main。caller 后续声明报告归档提交 `6c535252d434ff4a384c8542d14a48435bab936c` 不改变被测产品/测试代码，本轮 validated_at 保留实际开始验证的 `1862af6`。
- caller 声明本次相对 R1 产品 runtime 源码不变、原编译进程仍适用；仅 owned ignored 代理 URL pathname 处理修复并重启。没有由 reviewer 无条件重启栈。
- 保留原 Sol/high 角色、profile version 1 与 session，在原合成聊天发送明确新业务接续。CC message `84dadba9ba97406dbddc1594edbb01c2`；Codex message `377ab7bf30124123a31e4d0eac2fa74d`。这是新的主人业务请求，不把 R1 已失败调用重命名为内部 retry。
- 本轮最终结论见下方“R2 最终覆盖与 verdict”；下列完整非注入插件旅程已通过，逐 attempt 审计仍未取得，不能宣布 full pass。

### R2 真实服务旅程 — 已通过的具体结果

两个 Global Agent 均自行阅读当前公开插件 API，真实写入自己的插件包、执行检查、使用正式 plugin_manager 安装，并在 Work turn 2 中保留一次安装和两次独立业务工具调用。两者 turn 2 completed、main idle，所读 Work turn 无 next_items_cursor；最终向各自合成聊天的 send_message 均完成。没有用心算结果代替插件工具结果。

| 策略 / 原 session | 一次安装 | 两次真实动态工具及结果 |
|---|---|---|
| CC / `5b0058ad-b302-406c-9fc3-0fbd57423ee4` | `call_c07d33bfae774959a01e3862aec294d3`，application=`applied` | `r2_live361_cc_travel_calculate`：A `call_306d3efd5d4944ffb9083f3314b8914e`，48000 分 / 480 元；B `call_d7470dd00bf94b408f34f04efdfc7768`，37000 分 / 370 元。 |
| Codex / `e051bfd4-c3b2-4069-8f21-723fcf03310b` | `call_a9e52380dba34327937db5329bd691e1`，application=`applied` | `travel_reimbursement_r2_live361`：A `call_3d73c157577a4589b28d0c68f6172699`，48000 分 / 480.00 元；B `call_b20ac99bf67b46739747bbcdd434febd`，37000 分 / 370.00 元。 |

此段为真实 Sol 主模型、真实 Luna reviewer 路径，不是合成 allow：在旅程后公开代理最小状态为 plan 空、hold 0，记录的 19 个 HTTP request 均为 live、19 个 response 均为 200。该计数只说明代理 HTTP 记录，不是审核 attempt 数，也不单独证明逐调用审核模型/usage；后者仍须实际审计。R1 默认 DeepSeek 额度失败不因 Sol 成功被抹除。

R1-E2 的完整产品路径阻塞已由本轮真实安装及两次调用解除；caller-reported 代理修复与独立观察到的成功结果分开记录。R1-E3 的具体审计方法缺口尚未解除，未执行被拒消费者或其替代方法。

### R2 确定性审核故障 — Work 结果与 HTTP 辅助证据

对已装真实业务工具逐个发新的合成请求，以精确工具名和唯一 group marker 双匹配代理注入；非目标请求保持真实路径。每个请求要求最多一次主工具调用、失败即停，不安装或修改插件，不用其他方法计算。以下每行两策略分别执行，均观察到 **1 个主工具 callId**，没有主 Agent 重发。成功行恰有 1 个 completed 业务工具结果 48000 分；失败行为 NanoApprovalDenied、无成功业务执行结果。该事实不等于已取得审核 attempt 审计；表中次数严格是代理 HTTP 请求数量。

| case 后缀（marker=`r2-<case>-<policy>`） | CC callId / ms / HTTP | Codex callId / ms / HTTP | 公开 Work 结果 |
|---|---|---|---|
| 503-live | `call_ef8d1bcc0c0f4241af29c794c9b8d04a` / 3674 / 2 | `call_3fb24e22fdd04e9c8b90c370cf51e039` / 3330 / 2 | 503 后真实 reviewer live；各一次 completed，48000 分。 |
| 503-exhaust | `call_c1dace7d05b2418c98cccff1ad0c2cc3` / 1557 / 3 | `call_aacd322b8cf44469bf666979b8f220b3` / 1781 / 3 | HTTP 503×3 后 classifier_unavailable，service (SERVER)，return_to_agent；成功业务执行 0。 |
| auth401 | `call_6b7584f3a73d48cf870dcaf01b0edf52` / 27 / 1 | `call_32682a338c714dbba2dc0e07dfa75b70` / 115 / 1 | HTTP 401 后 classifier_unavailable，auth (AUTH)，return_to_agent；成功业务执行 0，无第二个目标 HTTP 请求。 |
| deny | `call_a59158c1a7d444e1b342e7bf94aaa3df` / 35 / 2 | `call_a2ddd41af06f4bdda397b2b9d6dff573` / 93 / 1 | 注入有效拒绝后 classifier_block，不误写技术不可用；成功业务执行 0。CC 两个正常判定 HTTP 请求不能标作失败恢复。 |
| invalid | `call_1b253f789e77425e840ad01845206e32` / 549 / 2 | `call_9eb608cd44d6481996969b3009cd6e53` / 643 / 2 | invalid×2 后 classifier_unavailable，invalid，return_to_agent；成功业务执行 0。 |
| invalid-503-live | `call_00fd1f2fd17b47bf96b648ab1836e264` / 7595 / 3 | `call_e3730b177fb64c0cb51bec27af595253` / 4990 / 3 | invalid→503→真实 reviewer live；各一次 completed，48000 分。 |
| 503-invalid-invalid | `call_ef23105b00e74967b3f6103e1e177b1c` / 1554 / 3 | `call_1d7eaeb8df36400ba88cb17b551c5740` / 1751 / 3 | 503→invalid→invalid 后技术不可用 invalid；成功业务执行 0。 |
| 429-transport-live | `call_2c7b758d7c394756bd40661c86624a94` / 3577 / 3 | `call_7f5f780b1b0b475ca7314ff118a9ec0f` / 6004 / 3 | 429→transport connection drop→真实 reviewer live；各一次 completed，48000 分。 |

这些行为支持“短暂故障不要求主 Agent 重发，恢复后只出现一次业务工具成功”“技术故障与有效 deny 区分”“失败后交回 Global Agent”的产品结果。尚不据代理 HTTP 次数宣称精确 extraUsed/invalidRecoveryUsed、每次独立 90s 或审计 usage 已验证。有效 deny/invalid 的合成响应与 live 模型路径明确分开；合成 SSE 的固定 usage 不是可计量的真实模型用量。

### R2 请求中与退避时停止 — 实际 IM `/stop`

每次等待代理明确进入目标阶段后，通过所属合成聊天发送 `/stop`：active 为目标 HTTP 已挂入 hold；backoff 为目标 503 响应已记录，注入头携带 Retry-After=10 秒。**后续获准实际审计纠正：本次 provider 未将该头呈现为 providerRetryAfterMs，实际 delayAfterMs 是500ms，不是10秒。** 发送停止前，Work 中目标工具状态均为 running，而非已执行完成。停止后各 turn interrupted，工具均失败为 `AbortError / ABORTED_BEFORE_DISPATCH`，成功业务执行 0，main idle。公开消息中观察到停止确认。尝试 release 后继续观察12秒（超过实际500ms退避及设计10秒上限），无目标后续 HTTP 请求、无业务成功结果。具体失败结束与取消时间戳见 [最小实际审计](product-audit-metrics.md)，取消发生在实际500ms退避内；尚须独立 reviewer 关联确认。

| marker | callId | 请求后发 stop / 工具总耗时 ms | 目标 HTTP 数 / stop 后新增 | 其他观察 |
|---|---|---|---|---|
| r2-cancel-active-cc | `call_2ba05e1b37df4bc1ba324342848e326f` | 253 / 275 | 1 / 0 | 1 次 client-disconnected。 |
| r2-cancel-backoff-cc | `call_c1883ae2bb4c4b4285bdfccad16eeb9b` | 192 / 210 | 1 / 0 | 在503响应已记录后停止；后续审计确认实际500ms退避内，注入10s头未成为实际hint。 |
| r2-cancel-active-codex | `call_14d56fd1f0184ffe9a46f0b6c5cc3512` | 293 / 362 | 1 / 0 | 1 次 client-disconnected。 |
| r2-cancel-backoff-codex | `call_95ba898d0f9449929843f8100c82e1a8` | 123 / 222 | 1 / 0 | 在503响应已记录后停止；后续审计确认实际500ms退避内，注入10s头未成为实际hint。 |

这证明所测合作型 HTTP 请求及退避的产品停止结果；不声称已测不合作远端计算的物理终止、迟到成功提交竞争或完整取消审计。hold 在客户端断开时删除，后续 release 不等于真实发送一个迟到成功响应。取消后的新独立业务请求是用户重新授权的另一操作，不是复活旧操作。

### R2 空白与正常时限 timeout — 未缩短产品常量

| marker | callId / 工具耗时 | 目标 HTTP 辅助证据 | 公开 Work 结果 |
|---|---|---|---|
| r2-empty-cc | `call_14b57971962a49db92feea750235448d` / 548ms | empty×2，相邻请求间隔515ms。 | 1主调用；invalid技术不可用、return_to_agent；成功业务执行0。 |
| r2-empty-codex | `call_fa53053012cf474cb782d6358faf3fda` / 698ms | empty×2，相邻请求间隔590ms。 | 1主调用；invalid技术不可用、return_to_agent；成功业务执行0。 |
| r2-timeout-live-cc | `call_20194e428b894a5499da01a7d771a17b` / 38203ms | hold→live，相邻请求间隔30506ms；hold有client-disconnected。 | 等待期间工具running；1主调用、最终1次completed，48000分。观察与CC首阶段30秒子上限相容，不称作完整90秒耗尽。 |
| r2-timeout-live-codex | `call_dea834e48ffc42659ed19a4f58e3e6aa` / 93262ms | hold→live，相邻请求间隔90517ms；hold有client-disconnected。 | 等待期间工具running；1主调用、最终1次completed，48000分。初次约90秒后仍能恢复，不被统一90秒总截止截断。 |

四项均最终 idle，holdCount=0；完成后清空注入 responses 并 release。没有改 timeout 常量或用假时钟冒充真实产品时间。仍未证明第二、第三次各自可完整使用90秒，也未以本轮观察代替290秒全预算上界或审计finalCategory。

### R2 最终覆盖与 verdict

**Verdict: fail（full 门禁证据不足；已测产品行为未发现需修改实现的失败）。Highest required action: out-of-unit。Needs re-review: yes。** 真实服务插件旅程和所测故障/停止的外部行为已有积极结果，但真实逐 attempt 审计与部分 fallback/config/完整预算覆盖缺失，不能因多数场景成功宣布完整通过。该结论不降低首文档标准，也不把工具权限限制说成主人从未授权必要只读。

| spec Scenario | 本轮实际支持的结果 | 结论与剩余范围 |
|---|---|---|
| 服务恢复后继续原操作 | CC/Codex 503→live、429→transport→live、invalid→503→live，均同一主工具调用完成一次48000分；未主Agent重发。 | **pass（所测业务工具外部恢复结果）**。恢复注入作用于已安装插件的动态调用，不把它写成“安装步骤的503恢复已测”；安装本身仅在非注入路径测得一次。 |
| 持续故障耗尽 | 503×3后技术不可用、业务执行0；Global return_to_agent可辨；Codex正常90秒timeout后恢复成功。 | **inconclusive**：HTTP数量不替代内部attempt；未独立覆盖每个后续attempt完整90秒、总预算边界、interactive与scheduled fallback矩阵。 |
| 空白或非法判定 | 空白/invalid两HTTP后关闭；混合invalid/service序列结果与共享限额相容。 | **inconclusive**：无实际审批审计，不能确认真实extraUsed/invalidRecoveryUsed及其持久化；不把HTTP计数冒充内部恢复计数。 |
| 明确拒绝或认证配置错误 | 两策略有效deny均classifier_block；401为auth技术不可用，各一HTTP；CC两个正常阶段HTTP后最终block。 | **inconclusive**：所测deny/auth外部行为符合预期，配置错误的真实产品路径与stage/attempt审计尚未覆盖。 |
| 请求中或退避时停止 | 四项真实/stop使目标工具ABORTED_BEFORE_DISPATCH，成功执行0；停止后12秒超过backoff上限窗口，无下一目标HTTP；active请求断开。 | **pass（所测合作型请求与退避停止）**。迟到非合作结果提交竞争及完整取消审计未测，不扩大此结论。 |
| 分清恢复与新调用 | Work可定位同一主session、各新callId、成功/失败/取消；本轮所有新业务请求与R1失败历史保持可区分。 | **inconclusive**：未取得公开session.observe实际审批record；reviewId、attempts、分类/耗时/模型/usage与callId关联未证实。具体被拒方法仍未执行或替换。 |
| 全局 Agent 插件真实旅程 | 两策略自建→一次applied安装→两次真实业务调用480/370，Work完整可检查，真实与注入路径分别报告。 | **pass（Sol/high＋Luna，批准的default替代环境）**。DeepSeek默认额度失败保留；无daily团队与浏览器视觉覆盖声明。 |

### R2 剩余阻塞与接续

- **R1-E1**：默认DeepSeek额度失败事实保留；获准Sol替代已成功，不阻塞上述替代模型结论，不证明默认模型恢复。
- **R1-E2**：所测真实旅程的审核连接阻塞已解除，未发现需要reviewer要求修改产品实现的新失败。
- **R1-E3 / R2-E1（blocking，out-of-unit）**：合法逐attempt审计方法尚未落实；所需最小字段、公开来源及留存限制见R1字段清单。完整raw不是必要条件，但当前允许且成功的Work/代理摘要不含这些字段。维持具体受阻方法停止，不尝试等效导出。
- **R2-E2（blocking，验收覆盖缺口）**：真实配置错误、interactive/scheduled fallback、安装步骤注入恢复/失败/取消、每次完整预算与非合作迟到边界未在此轮产品实测。可由caller按spec/design划分产品必验与独立静态/确定性契约证据后组织补验；reviewer未读取worker/static成功叙述来填补。
- 本轮没有新的blocking/major实现缺陷findings；“无已发现实现缺陷”不等于full通过。未创建GitHub issue，未提交代码或报告，未停止caller拥有的栈或代理。
- 定位符仍为上述两Sol主session及表内callIds。后续补证必须保留R1/R2事实并明确被验版本；不得以新增报告提交冒充重跑。

## Round 3 — design:140 安装步骤补验

本轮沿用 R2 实际产品版本 `1862af639681defdb91651f50cc6e01459e63e0b` 与相同运行进程、Sol/high 和 Luna reviewer；caller 确认后续报告提交不改变被测产品。原 R2 24 项动态业务工具故障测试不重跑，不把动态调用等同安装副作用。

### 暂停与明确接续

caller 首次派发安装补验后，reviewer 已向两个原 Sol 聊天发送准备任务，明确要求先正式列举未安装状态、创建独立包且禁止安装。随后收到暂停指示，立即发送 /stop 并清空注入/hold。实际两 session turn15 均 interrupted、main idle，公开最小计数均为 installCalls=0、listCalls=0、completedWrites=0，控制项0；不能把这次准备取消计作“审核中的安装停止”case。

caller 后续明确恢复原design六项补验，且栈未停止。reviewer 在确认上述终态后发送 **新的明确准备请求**：CC `7adc4ec9122d43c4aa07245ff40182ca`；Codex `45e1f4d25fac4d01b5a1bb00657b5a41`。不是自动续跑或复活取消操作，未更改 profile/session。

### 独立新插件准备及安装前不存在证明

Global Agent 自主准备三个独立完整包，包名/目录名分别为 `r3-361-<cc|codex>-recover`、`r3-361-<cc|codex>-auth`、`r3-361-<cc|codex>-stop`，各工具注册名独立；不修改 R2 原插件。turn16 两者 completed、正式 list_bundles 前后均只有原有1项，六个目标新包均不存在；本准备阶段无 install_bundle。Agent 自主通过公开API资料和 bash 建包/检查，最终真实发送就绪说明，reviewer 没有写入或安装插件。

| 策略 | 准备前正式清单 callId | 准备后正式清单 callId | 实际结果 |
|---|---|---|---|
| CC | `call_32cd0c9d633d460e8bf69c8ef6f11045` | `call_b362985d7aa24f31af0ebafd19004ba4` | entries=1；recover/auth/stop 三个目标包均不在清单。 |
| Codex | `call_201ac7db27394dd680f83078827c9b92` | `call_0b8a4c279c0b42ec85d8f586b42b7510` | entries=1；recover/auth/stop 三个目标包均不在清单。 |

### 证据分层澄清

R2 将安装注入和完整预算/非合作迟到/fallback 合并记作待补范围，需按既有design区分：安装恢复/永久失败/停止是 design:140 明确产品必验，当前实际补跑；每次完整90秒、总预算、非合作资源与路由组合等设计 W2–W5 的确定性/native 边界由独立 static/verifier 核对 worker 证据，不默认要求全部真实慢跑。reviewer 不读实现诊断、不将 worker 成功叙述冒充产品旅程，也不扩大既有只读授权。

caller 通知已取得原主人对本轮选定合成 sessions/callIds 必要审计指标的明确授权，由 caller 集中提交正常工具权限检查并在停own Node/DSH后取证；reviewer 未自行启动 observe、未重试或替换被拒方法。实际审计结果未到达前，相关结论仍待补，不把授权等同取证完成。

### R3 安装步骤实际结果（逐策略追加）

精确匹配 `plugin_manager` 与独立包 target marker；实际 Work 操作均为 `install_bundle`。reviewer 只发业务请求、控制专用代理并读取最小结果，由真实 Global Agent 发起安装。每次安装后另发明确只读请求，要求通过正式 `list_bundles` 核对结果，不重复安装；取消后的核对不复活被取消操作。

| 策略 / case | 安装 callId / 耗时 | 注入及 Work 结果 | 正式安装后清单 callId / 最小状态 |
|---|---|---|---|
| CC recover | `call_cfce86d2722d4733943c223c8e565af9` / 8517ms | 503→live，1主安装调用，application=applied；2目标HTTP，仅作辅助计数。 | `call_c76fca9fe2ff45b8aa0b6100d1b9ccc7`；recover包恰1项，installed=true、enabled=true。 |
| CC auth | `call_34b3749268e04700b24cf8b6e92db2e3` / 48ms | 401，1主安装调用，classifier_unavailable / auth(AUTH)，return_to_agent；1目标HTTP。 | `call_4cc4c6e69afc489990ea84124235916c`；auth包0项，未安装。 |
| CC stop | `call_9d316acee220493997d0de00287607b0` / 298ms | 安装审核hold已确认、Work running后真实/stop；turn21 interrupted，ABORTED_BEFORE_DISPATCH；1目标HTTP、1次连接断开，停止后12s无下一目标请求。 | `call_3c7d5979fbf9430b9a1a1f05e28e007f`；stop包0项，未安装。 |
| Codex recover | `call_7d1047d76a104a178894e522f72c217c` / 4712ms | 503→live，1主安装调用，application=applied；2目标HTTP，仅作辅助计数。 | `call_9b99cd64c8b44089bb6bdea05f6ced1c`；recover包恰1项，installed=true、enabled=true。 |
| Codex auth | `call_6f97cf451a1e48e2a48a228c98456146` / 85ms | 401，1主安装调用，classifier_unavailable / auth(AUTH)，return_to_agent；1目标HTTP。 | `call_fb03dd397bde4b178f29099af876dc25`；auth包0项，未安装。 |
| Codex stop | `call_4a39e773c7964a1b86e458e0b2fa9db6` / 223ms | 安装审核hold已确认、Work running后真实/stop；turn21 interrupted，ABORTED_BEFORE_DISPATCH；1目标HTTP、1次连接断开，停止后12s无下一目标请求。 | `call_3735c8842b664231a0d00a002ab54a7d`；stop包0项，未安装。 |

**design:140 六项安装外部结果均 pass**：新包安装前不存在；恢复后仅一次applied并在正式清单中恰1项；永久认证失败与活动请求停止后均正式清单0项，没有安装副作用。两策略全部真实安装/核对由产品Global Agent执行，reviewer未直接安装。该结论不以HTTP请求数替代审批attempt审计。

最终公开核对：两Sol主session均idle，最新turn22 completed，control_items=0；代理responses=[]、holds=0。R3 probe后台工作已结束，未自行停caller的Node/DSH/IM/proxy。caller可在确认ownership后执行集中停栈及获准最小审计消费；本报告收到实际结果前仍保留审计场景inconclusive，未宣告full pass。

## Round 4 — 独立产品验收证据闭合

### 本轮正式结论

**Verdict: pass。Highest required action: pass。当前未关闭的产品验收问题：0 blocking / 0 major / 0 minor；needs_re_review=false（仅限本轮冻结产品及已批准环境范围）。**

本轮闭合 R1/R2 历史 fail/inconclusive，不覆盖或改写当时事实。真实服务旅程、确定性产品故障、六项安装副作用及获准公开消费面的实际逐 attempt 审计现可相互核对，已足以完成本 unit 的 full 产品验收。独立 verifier 的最终闭合、final sync、canonical 归并、archive、PR 均不由本 verdict 代为宣布。

- `review_round`: 4；模式：在原 full 范围上的 evidence closure，不重新发业务任务。
- `validated_at`: `86591326fb439a4cc68a651080980df8c1650df8`（本轮独立核对的证据冻结 HEAD，核对时 clean）。
- `executed_base`: `5454f3140f9c92532c690db8dec80b9f77080384`，仍为授权 baseline，不称最新 main。
- 实际 R2/R3 产品执行树：`1862af639681defdb91651f50cc6e01459e63e0b`；runtime 产品代码沿用 `dfee3df40116757346ef6a7edcaa5d10734c9a61`。本轮独立执行 git diff --quiet，仅核实版本等同性，不读取实现定位问题：从1862到8659的 packages/apps/tests/src/config 无差异，exit0。因此保留原真实旅程，不将报告提交冒充重跑。
- 本轮新增读取仅为 [product-audit-metrics.md](product-audit-metrics.md) 的获准最小派生指标、独立 [verification.md](verification.md) 的证据分层结论和本报告；没有读取 raw observation、重新运行 consumer、启动服务或采集其他会话。

### 实际审计来源及独立关联

最小指标由 executor 在新的明确 owner 授权且正常工具权限检查通过后，于 `2026-10-27T11:38:23.258Z` 使用公开 RuntimeClient initialize/session.observe 从原 profiles/bindings 取得；product.call 全拒绝、原始 observation 仅内存处理后丢弃、仅输出选定字段，consumer shutdown/exit0。该采集不是 reviewer 亲自执行；reviewer 的独立工作是将其选定 session/callId、分类、时间和结果与先前亲自观察的真实 Work、/stop 和正式插件清单逐项关联。未以 synthetic native 数据冒充真实产品审计，也未重试原 raw 落盘方法。

选定集合为两策略各18项：真实安装及A/B三项、R2故障/停止十二项、R3安装三项，共36个已在本报告记录的主工具 callId。逐项匹配最小指标中的 callId，缺失0；每个恰1个含 retry 的审批聚合、各有不同 reviewId，合计 **36 reviews / 62 actual attempts**，每策略18 reviews / 31 attempts。独立按表中 ordinal 序列重新计算31+31=62；additional return_to_agent 行是同一调用的最终路由，不算额外模型 attempt 或主工具调用。

| 独立交叉核对项 | 实际审批证据 | 与已观察产品结果的关联 |
|---|---|---|
| 原操作恢复而非主Agent重发 | 两策略503-live均 service→allow、E/I=1/0；429/transport/live均 service→transport→allow、E/I=2/0。 | 各仅1主call、1次业务成功48000分，reviewId与其他新业务请求不同。 |
| 持续服务故障 | 两策略503-exhaust均3个service attempts、E/I=2/0、finalCategory=service，no_verdict后同call return_to_agent。 | Work技术不可用、成功业务执行0；不把故障计作有效deny。 |
| invalid共享额度 | invalid/empty均2 attempts、E/I=1/1；invalid→service→allow和service→invalid→invalid均3 attempts、E/I=2/1。 | 与R2真实操作成功/失败结果相符；现在由实际审批字段而非HTTP数确认恢复额度。 |
| deny/auth与CC阶段 | auth和安装auth均1 attempt、E/I=0/0；valid deny亦1 attempt、0/0。CC有效deny包含stage1和stage2，仍是同一attempt。 | Work分别classifier_unavailable/auth与classifier_block；R3 auth正式清单0项。CC两次HTTP不是失败重试。 |
| 安装恢复 | CC `call_cfce86d2722d4733943c223c8e565af9` 对应review `7f973bba-3620-44be-92a0-05372d0d601f`；Codex `call_7d1047d76a104a178894e522f72c217c` 对应 `d162f3b1-0758-431a-a391-01d05ea0dd1c`。均service→allow、E/I=1/0。 | 原来未安装的新包，仅1次主install/applied，正式清单各恰1项；不是主Agent重新安装恢复。 |
| 活动请求与安装取消 | 四个active/installation stop对应实际cancel attempt，E/I=0/0、classifier_cancel/cancel。 | 与Work ABORTED_BEFORE_DISPATCH、连接断开、业务执行0或正式清单未安装一致；无fallback放行。 |
| 退避取消 | 两个backoff取消各仅1个service attempt，随后finalCategory=cancel，E/I=0/0。 | 与Work interrupted、stop后无下一目标HTTP和工具执行一致；实际退避时间独立计算见下。 |
| 超时后恢复 | CC timeout:30006ms→allow:7678ms，E/I=1/0；Codex timeout:90042ms→allow:2703ms，E/I=1/0；均final allow。 | 与工具总耗时38203ms/93262ms及单次48000分业务结果一致；明确timeout归因，不混为invalid。 |

全部选定attempt实际记录 reviewer provider=`issue361-review-proxy`、model=`codexOAuth:gpt-6-luna`，并保留实际耗时及可得usage，不从配置或HTTP数量猜测。失败/取消所输出的cleanupConfirmed均true；仅用于确认本地已记录清理，不扩张为远端物理计算终止证明。

### 退避与超时的独立复核及更正

R2原先以注入 Retry-After=10秒推断实际等待10秒不成立；本轮已独立核对并确认当前报告138/143/145的更正：实际审计未呈现providerRetryAfterMs，delayAfterMs=500ms。注入的HTTP头不能直接作为策略实际消费hint的证明。

- CC backoff call `call_c1883ae2bb4c4b4285bdfccad16eeb9b`，review `f2062a07-c7fd-424b-87ca-88260752db15`：失败结束1793099548817，取消审计1793099549013，差 **196ms < 500ms**；下一次计划边界1793099549317尚未到达。唯一service attempt，extraUsed=0。
- Codex backoff call `call_95ba898d0f9449929843f8100c82e1a8`，review `d2fbc167-8c97-4a91-93af-7279c0bc5b9f`：失败结束1793099612629，取消审计1793099612739，差 **110ms < 500ms**；计划边界1793099613129尚未到达。唯一service attempt，extraUsed=0。
- 与原先亲自观察的Work调用耗时210/222ms、running后/stop、12秒无后续请求相容，足以证明确实在本次实际退避中取消，而不是仅收到错误后某个不明阶段停止。12秒观察仍有效，但不再称实际退避10秒。
- CC timeout起止1793099713422→1793099743428，下一attempt起点1793099743929：实际30006ms与501ms间隔。Codex1793099816700→1793099906742，下一起点1793099907243：实际90042ms与501ms间隔。计算与最小指标相符；不是统一90秒总截止。

### usage 的实际可查性与边界

最小指标提供真实成功请求的child usage，可与对应主call/review关联。例如CC真实安装38172/11、A38459/11、B38546/11（input/output tokens）；Codex真实安装1210/70且cacheRead38400、A1311/60且cacheRead39424、B815/58且cacheRead40576。只按所给字段解释，不将不同缓存口径相加为账单总量。

失败attempt聚合usage为absent/unknown；取消/timeout child亦unknown。HTTP错误child的0/0为SDK提供字段，不能说成真实模型测量了零token；invalid/empty/deny child的1/1为fixture合成字段，不能计为live用量。CC deny的聚合usage缺失，仍可检查两个synthetic child。Codex成功聚合在选定inputTokens标量键下缺失，但per-request child有可得值；不补0、不重复合计。这满足“可得usage可查、缺失不得伪装零”的产品审计要求，而非承诺所有供应商都提供同口径精确账单。

### full验收的分层判断

独立阅读verification的R2 supplement后，本reviewer接受其分层：每个spec Scenario仍需本轮实际代表性产品结果及可检查证据，但不把design明确归W2–W5的完整时钟、竞态和路由笛卡尔积全部追加为真实慢跑。不是按轮次降标准，也不是拿worker叙述替代旅程。

- 完整三次90秒预算、290秒上界、hint cap：复用独立静态核验的fake-clock/native证据；本产品层只声明亲测CC30秒阶段、Codex90秒后恢复及实际审批时间。
- 非合作iterator、late allow/checkpoint、准备/审计竞态：复用独立静态核验的native/生命周期证据；产品层亲测活动请求、退避、安装停止和实际cancel审计，不声称物理终止远端计算。
- interactive与scheduled fallback：复用已独立核验的原生路由/effect机制，本轮实际Global return_to_agent及其审计补齐代表性产品结果；没有把system-origin native输入称为真实Schedule执行，显式unattended allow仍是旧配置fallback，不是模型allow。
- deny/auth/config：本轮真实有效deny、401及401安装副作用为代表性产品路径；独立native配置/context-budget失败的一次config attempt、extraUsed0与零effect补齐机制。spec没有要求每个永久错误枚举都另建真实配置旅程，因此不再将未真实重演config列为独立产品阻塞。
- design:140明确要求的安装六项不能由动态业务工具替代，已由R3全部独立实测闭合。

### 最新Scenario覆盖（覆盖旧轮未闭合项）

| spec Scenario | 本轮最终依据 | 结论 |
|---|---|---|
| 服务恢复后继续原操作 | 双策略业务调用和安装503→真实allow，原call只执行一次；实际reviewId及attempt/E字段对应，无主Agent重发；native effect边界补充。 | pass |
| 持续故障耗尽 | 双策略实际3次service attempts、extraUsed2、业务执行0与技术不可用/return_to_agent；独立预算与原fallback机制按指定层复用。 | pass |
| 空白或非法判定 | 双策略empty/invalid及混合序列真实审计确认invalidRecoveryUsed1、总extra≤2，业务副作用与终态匹配。 | pass |
| 明确拒绝或认证配置错误 | 真实deny/auth均0extra、CC两stage属于同attempt；auth安装0副作用；配置机制复用独立native核验。 | pass |
| 请求中或退避时停止 | 真实IM停止业务及安装、正式清单0副作用；500ms退避内取消的时间戳与0extra/无下一attempt确认；late边界按native层核验。 | pass |
| 分清恢复与新调用 | 36个选定call对应36个distinct reviewId和62个真实attempts，模型/类别/耗时/路由/可得usage可查，内部恢复与新主调用分离。 | pass |
| 全局 Agent 插件真实旅程 | 两Global角色自主创建、各1次applied安装、各两次真实业务调用480/370，Work与对应真实审核/usage可关联；真实及注入结果分开。 | pass |

### 旧问题处置、环境限制与交付边界

- R1-E1：DeepSeek默认模型当时402/QUOTA事实保留，不声称恢复。caller批准的Sol替代真实成功；本次模型可用性结论只限Sol/high＋Luna及该隔离栈。
- R1-E2：自建proxy的先前连接前置问题由caller修复；R2/R3真实成功已独立证实受阻产品路径恢复，不归为产品实现缺陷。
- R1-E3 / R2-E1：新的明确授权后，正常权限检查通过的最小实际消费者已取得必要数据；本轮独立关联完成，关闭具体取证缺口。原raw拒绝并未被撤销或绕过。
- R2-E2：安装必验由R3补齐；其他指定worker/native边界依据独立verification完成合理分层，不再重复要求所有真实慢跑。无未关闭的必验Scenario。
- 继续保留批准的default替代daily、默认DeepSeek失败后新建Sol角色、无浏览器/iOS视觉覆盖、无生产/外部IM访问等实际范围说明；本unit无视觉must-match，API入口符合runbook。
- caller报告取证前已确认own Node3657/DSH3660/IM95854/proxy7499退出、53939/56096关闭，consumer已shutdown；本reviewer未重新启动或独立停服务。该清理事实按caller来源记录。
- report_path为本文件；reviewer未commit，report_commit由caller统一提交后填写。gh_issues_filed=0。若后续产品或有效base有实质变化，应重新做失效判断；本结论不表示已sync、已archive或已创建/准备好PR。

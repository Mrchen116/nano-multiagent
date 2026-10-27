# feat-625 — 产品验收报告

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

本报告未 commit，由 caller 统一处理；后续轮次追加，不覆盖本轮未通过事实。

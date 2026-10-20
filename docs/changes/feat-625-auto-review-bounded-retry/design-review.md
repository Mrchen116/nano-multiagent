# feat-625 Design Review

## Round 1

### Metadata

- reviewer_target: **独立 delegated Gate 2 reviewer subagent**；本次真实 runtime session ID：`f3bff003-49fa-40ab-b29c-e469c1a0daf4`（定向读取 `DSH_SESSION_ID`）。不是设计作者；fresh context，未参与本 unit 需求或设计。运行时未提供可核实的独立 Agent ID，不虚构名称/型号或借用 P 的长期身份冒充 reviewer。
- review_mode: **full**
- mode_reason: 首轮 R1，没有历史 Round；按 change-workflow 必须 full。独立覆盖首文档全部17个 Scenario、现状 grounding、职责/接口/公开能力复用、预算/错误/取消/并发/审计、delta、runbook 和 milestone，不限于作者自列重点。
- started_at: `2026-10-20T14:37:29+08:00`
- completed_at: `2026-10-20T14:42:40+08:00`（事实核对完成时间；随后落盘本报告）
- duration: `PT5M11S`
- validated_at: `bea22ef0ee3215e2498ac653ad4ee1082657f07e`
- executed_base: `bea22ef0ee3215e2498ac653ad4ee1082657f07e`（本地 `origin/main`）
- effective_base / effective_through: 同上；仅对本轮冻结树有效，后续实质修订须复审。
- checkout: `/Users/czj/.nanoassistant/workspaces/nano-product`，branch `main`。开始时唯一 dirty/untracked 为 `.claude/skills/.usage.json`，未读取或修改其内容。
- skills: 实际加载 `change-design-reviewer`（含 report reference）、`codebase-design`（含 DEEPENING）、`nano-team-work`；读取 TEAM/ROLE、AGENTS、docs 地图、change-workflow、change storage 与 spec contributing。遵守子会话限制：未访问 Inbox/conversations、未公开发消息、未修改团队图、未派其他 Agent。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

设计的 action 级共享额度、完整预算、失败分支隔离和原 fallback 方向总体合理；但固定安装版的 `llm/stream` 并不具备设计依赖的 Agent scope 隔离，且真实旅程固定选取的审核模型在当前声明上明确不支持所需 `low`。两项均会使下游按文档实施/验收实质走偏，应由原作者判真、修订后续投本 reviewer。没有要求重新询问已收口的人类决定。

### Scope and frozen artifacts

以下五项均完整读取，未更改：

| 产物 | 冻结树 blob / 读取范围 |
|---|---|
| `spec.md` | `c01ecf2817dbc14ca02fe1c1cdc2d57ed021c686`，L1–169 全文 |
| `design.md` | `f8c76c1430a246555348efe12e6f3ab42ca4eb5d`，L1–211 全文 |
| `specs/gateway/agent-capabilities.md` | `4c003d9ba89dc25da2bc933642fc6b99b4ad7f39`，L1–85 全文 |
| `reviewer-runbook.md` | `c621dec8f292528c1df159104a247a45b43f9560`，L1–128 全文 |
| `M1-review-recovery/.gitkeep` | 空文件，blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |

`git diff --exit-code` 核对工作树上述 unit 与受审 SHA 一致；另核对 `80134297ddfabb08e80e83c01a20e20280de20f0..bea22ef0ee3215e2498ac653ad4ee1082657f07e` 的 `spec.md` 无差异。没有把设计态当作已实现能力，没有验收产品实现，没有创建分支或提交。

### Coverage and independent evidence

#### 1. Current behavior and actual assembly

不是仅检查引用存在：

- `SPEC.md` L7、L26–50：唯一官方 DSH 执行运行时；integration 持有来源/审批；Node 仅通过公开 client 管进程，PA/IM 不 import DSH。这支持 recovery、transport facts 与 audit 落在 integration，而非产品路由或新服务。
- `apps/node/src/main.ts` L16、L39–44、L85–130 → `packages/dsh-integration/src/client.ts` L13–24、L44–49：生产按锁定安装准备 `dsh-base + @nano/dsh-integration` profile，启动官方 CLI 的 stdio 子进程。`cordis.patch.yml` L19–33 装配 nano-runtime；不是仅测试直接实例化的路径。
- `packages/dsh-integration/src/index.ts` L107–115、L155–158 确实安装现有 attribution 和 CC/Codex/NanoApproval；L370–375 的 `session.observe` 返回持久 approval domain entries。无须为 trace 新建 IM API 或原生不可忽略事件。
- `policy/approval.ts` L99–145：downstream/fastpaths → 独立 reviewer/来源 → 策略 → audit/计数/分流。L71–98 的顺序明确 child 优先 return_to_agent，schedule/heartbeat 为 unattended，Global 为 return_to_agent，普通人类聊天 interactive；unattendedFallback=allow 是真实现行配置行为，不能把耗尽泛称零执行。
- `policy/classifier.ts` L13–38 和 `cc.ts` L11–16：真实 CC workspace exemption、30/60秒独立流、stage1 有效非allow推进 stage2；legacy 单阶段30秒；当前失败字符串化且无本需求的 action recovery。
- `policy/codex.ts` L39–123、L125–156：真实 Guardian full/delta/fork、checkpoint、90秒共享 deadline、一次上下文恢复、原生创建和 scoped request/error listeners。当前错误正则/字符串化及闭包中 request 对缓存复用的影响确实需要本设计处理。
- 完整读取 `codex-context.ts`、`codex-inspection.ts`、`types.ts`、`audit.ts`：原精确动作/授权投影、host-owned 只读工具、可选 schema 扩展和旧行兼容均可沿用；不把这些文件存在当作新 recovery 已生效。

#### 2. Public exports, installed capabilities and reuse judgment

实际读取 integration `package.json`、已安装包的 export maps / public d.ts / 对应打包实现；版本为 DSH `0.2.1-alpha.1`、undici `8.11.2`，与项目固定声明一致。包内部路径仅供只读取证，没有 private runtime import。

- `dsh-llm` 根 exports 导出 `LlmError`、`LlmFailure`、`BlockAssembler`、retry-policy；`types/types.d.ts` L25–44 与 L141–148 提供 failure code/status/delay/requestId；`index.d.ts` L48–71 有 `LlmError.failure`。因此无需自行 JSON 反解错误。`error.d.ts` L17–40 的 canonical code 实际值包含 `QUOTA`、`ACCOUNT_QUOTA`、`EMPTY_RESPONSE`、`INVALID_CREDENTIAL`，与设计永久/格式优先规则相容。
- `dsh-llm-retry/lib/index.js` L151–178 的能力是 `agent/request-error` 插件，不是 `retry(fn)`；normal 默认次数/always 与本产品 action 额度及格式子额度不同。当前 Guardian 后注册的 prepend request-error owner 不调用 next 可终止该次 request，而 CC hand-built stream不经该事件。**不复用它执行本功能是有运行语义依据的选择**，不是无故重造通用库；必须保留 provider always 的隔离反证测试。
- `dsh-agent` 根 `index.d.ts` L48–103、L129–145：公开 create/setup commit、creation-only signal、AgentHandle.dispose；`runtime-types.d.ts` L151–164、L333–356：cancel/whenIdle 与 scoped request-error。打包 agent-loop L1655–1757 核实实际 cancel → idle → scope disposal → detach 的生命周期。可用原生 Agent 做恢复，不需要第二套执行 loop。
- pi-ai 打包 L1380–1452 确实将 in-band 错误转为 code/message 且常不保留 status/Retry-After；L1674–1684 为 `maxRetries:0`。扩展既有单 dispatcher owner 观察实际 HTTP headers 有具体必要性，但不能误以为任意 `scope.on` 都自动按 Agent 隔离，见 **R1-W1**。
- undici 公共 `types/dispatcher.d.ts` L207–232 有 `onResponseStart` 等接口；可观察且不修改/重发响应的方向可行，仍须在实施阶段以真实 HTTP adapter fixture验证 handler透传、headers 与 ALS 的并发归属。

职责判断：私有 ReviewRecovery 隐藏共享额度、计时、退避、取消和 trace，策略保留 CC阶段/Guardian生命周期，facade保留 final route、计数和工具调度，是有深度的 domain module；不应挪成 PA retry service、全局 provider policy 或通用 retry library。HTTP observer 扩展原 attribution seam，而不是第二个全局 dispatcher owner，可降低维护与卸载冲突。Guardian full恢复会增加只读调查费用/延迟，但失败状态不复用有明确隔离收益。该代价已在设计中承认，未发现需要强行另选架构的问题。

#### 3. Requirements and safety/budget completeness

| 首文档17场景（按原顺序归组） | 本轮判断与设计依据 |
|---|---|
| 短暂故障后放行；混合失败共享额外两次 | 设计 L60–78、L93–95、L153–158：同一pre-execute内只重做判定，不调用工具；额度隶属ToolExecution，跨CC阶段/Guardian步骤共享。HTTP归属存在 R1-W1，不能先宣称已完整闭合。 |
| CC完整阶段预算；Codex完整90秒；几分钟但有界 | L88–100：15秒准备，CC每次30/60，Guardian每次90，最多2次额外/20秒退避；330秒Codex、265秒CC最坏估算均在360秒保护内，没有重新引入共享旧90秒残余窗口。cleanup另设5秒，失败quarantine不启动恢复。 |
| 首次格式失败；再次格式或总额度耗尽 | L104–116：EMPTY_RESPONSE/empty/malformed优先归format，最多一次同时占总2次；不是默认native transient另送额度。runbook L111 包含混合顺序反例。 |
| CC两阶段与最终拒绝；Codex风险/授权/检查；永久错误 | L80–86、L104–116、L130–158：保留有效CC stage1、仅重当前阶段；最终deny不刷allow；永久quota/auth不恢复、不换模型；context单独全action一次，90秒内不再领额度。只读工具不扩大。 |
| 请求或退避中取消；非主动单次超时 | L104–107、L160–164：parent/owner取消优先于timeout/allow；generation撤销、iterator/handle drain、late create只清理、quarantine租约。不是仅Promise.race后遗忘底层；相关不合作promise测试有指定。 |
| 普通有人值守；Global/child；unattended allow/deny | L130–132、L176–178：技术no_verdict不增安全拒绝，原interactive/return_to_agent/unattended路径不进retry loop。主动取消不进入fallback。配置allow仍可能执行一次，符合已收口范围。 |
| 可追踪内部尝试；真实双策略插件旅程 | L166–178、runbook L67–128：action/attempt/request三层，真实模型/路由/usage未知不填0，旧domain可读，fallback第二行不重复成本；详细trace经domain导出而非假称Work已有attempt UI。双策略真实旅程与fixture/fake-clock/native证据明确分层。资源选择有 R1-W2。 |

特别检查了：stage推进不消耗服务额度；format额度不在stage/session重置；context rebuild在各技术恢复之间共享；失败branch不能覆盖并发成功checkpoint；缓存reviewer监听器读取可替换currentAttempt；取消后audit/fallback不可恢复工具；审计失败不新增自动allow；trace有100 request摘要上限而不把usage缺失写成完整成本。除以下发现外，这些设计决定足以指导实施，不要求在Gate 2先提供真实产品实现。

#### 4. Delta, unchanged scenarios and milestone

- canonical target正确，唯一落点 `docs/specs/gateway/agent-capabilities.md`；实际读取 current L508–579及相邻兼容场景，对照整个delta。
- MODIFIED 完整保留原 Requirement 下的8个 Scenario：默认规则、来源/去重、窗口超限、child委派、规则切换、失败分流、逐Agent选择、下一轮切换；只明确“已有重试”漂移并添加legacy上限说明，没有误删未改场景。独立CC workspace免审、Codex风险/授权Requirement不被替换。
- ADDED 的恢复/格式/取消/Retry-After/fallback/可检查事实为消费者可观察契约，不是内部类清单。无需增加产品权限或改变 #330 根授权刷新、插件API或主Agent防循环范围。
- 单M1是同一个安全闭环，避免按策略/层机械拆分；空骨架只有 `.gitkeep`，没有提前虚构实施记录。退出标准覆盖17场景、worker/native/HTTP和Q真IM证据、contract/typecheck/build/docs-check/适用独立门禁。
- 无新客户端面，未要求制造prototype、浏览器截图或真实后端实现；详细诊断经现有domain出口，Work仍只核真实工具和副作用。

#### 5. Runbook executable resources and evidence limits

- 读取 `scripts/e2e-up.sh` 全文，确认 --wt 可用临时runtime目录、脚本自身定位repo构建、端口/DB/workspace/node identity隔离、L194设置 `.gateway-owner`；runbook 的config与脚本路径对得上。
- `apps/node/src/configuration.ts` L31、L58–67和 `approval.ts` 验证owner配置继承/逐Agent覆盖与独立审核模型解析；`capabilities.ts` L24–29支持增加plugin_manager后使用已安装独立工具。不是把安装成功当实际调用成功。
- `tests/e2e/critical_paths/_im_client.py` 确有登录、online node、私聊、send_message、GET/PATCH与permission入口；`apps/im-server/src/work.ts` L753–780确有runbook使用的Work分层查询入口。既有 recording stub/native lifecycle/attribution tests 可作为M1的真实测试基础，不是空泛“后面补测试”。
- 真实插件两次结果180/55正确；真IM受控矩阵与真实provider旅程分开，保持默认30/60/90秒的超时证据、不合作回收native证据、fallback真实来源、420秒poll/15分钟旅程上限均合理。
- Python实测 `3.9.6`，不满足仓库≥3.11；**本轮未执行docs-check，未声称通过**。设计已诚实列出环境准备方式，这种标准dev环境缺口本身不另立warning。
- 没有启动IM、Node、DSH进程、HTTP fixture或真实模型/服务，没有安装依赖。`:4000/health=200`仅为委派输入/作者记录，本review未复测，不能证明模型可用。R1-W2不是要求Gate 2花真实模型流量，而是要求先修正文档中已知不兼容的模型声明选择。

### Historical issue closure

R1无历史finding/Author Resolution可关闭；不以作者自检或其他角色结论替代本轮判断。

### Issues

#### R1-W1 — `llm/stream` 不是Agent-scoped事件，Guardian的“scoped listener”不能提供HTTP事实隔离

- **Severity:** WARNING（阻断Gate 2）。
- **位置：** `design.md` L118–128，特别L120“Guardian scoped llm/stream各自包装”；L156复用reviewer的scoped llm监听器/currentAttempt；L187–188把隔离与listener顺序留待fixture，但未确定该公共接口真实隔离边界。
- **核实事实：** 固定版 `dsh-llm/lib/index.js` L2364–2365用 `this.ctx.waterfall(this, 'llm/stream', options, ...)`，public `index.d.ts` L33–45也明确事件bound to LlmRuntime；与 `agent/request-error` 的Agent carrier不是同一契约。agent-loop L771–779与L1072从loop/runtime LLM发流，不替此事件加Agent scope carrier。
- **最小只读验证：** 使用现有公共 imports，在内存Context安装LlmRuntime和一个本地无I/O的LlmAdapter，建两个`createScope`，各注册一个`scope.ctx.on('llm/stream', ...,{prepend:true})`。无论由root还是scope A调用sessionId=a的stream，两个listener都收到它：

  ```text
  {"rootStream":["b:a","a:a"]}
  {"scopedStream":["b:a","a:a"]}
  [exit code: 0]
  ```

  此验证没有访问网络/模型、启动产品或改写文件；它验证的是已安装公开事件语义，不是本unit实现测试。
- **未修后果：** 同时存在的Guardian fork、另一parent、CC和主Agent模型流都会穿过这些“scoped”监听器；仅凭scope注册不能决定绑定哪个currentAttempt/sink。嵌套ALS包装可能把A的429/Retry-After/usage归给B；idle缓存reviewer的currentAttempt为空也不能据此拒绝其他Agent流。会使跨请求事实不串、取消归属与主Agent不受影响的核心承诺失去依据。不能指望通用native scope自动提供不存在的过滤。
- **需要闭环：** 作者在design明确一个公共能力下可执行的**精确reviewer request归属/过滤入口**，对非本reviewer流透明透传，且在绑定currentAttempt/HTTP sink前完成归属判断。可按公开options中的精确reviewer session身份进行受控分派，或其他经核实的public seam；不能用同parent sessionId粗粒度归并，也不要求private import/fork。补充可同时保留idle缓存reviewer、两个active Guardian/fork、CC与main流的原生/HTTP fixture判据，证明只有所属流捕获facts，idle监听器不拦截别人的流。仅补一句“测试并发隔离”不够，需修正接口事实。

#### R1-W2 — 真模型runbook固定审核模型不支持审核器必需的 `low`，现有步骤在发HTTP前就失败

- **Severity:** WARNING（阻断Gate 2）。
- **位置：** `reviewer-runbook.md` L44–55固定 `tool_approval_model='deepseek:deepseek-v4-flash'`；L8–9/`design.md` L203虽要求smoke检查low，但没有解决已知声明冲突。
- **核实事实：** `config/e2e/gateway.yaml` L86–90对该模型只声明 `[high,max]`；`apps/node/src/providers.ts` L29–49将这一集合原样变成native reasoningEfforts；`policy/classifier.ts` L28和`codex.ts` L127、L133、L149均显式选择`low`。已安装pi-ai `lib/index.js` L1705–1708、L1848–1852严格校验effort，不支持时抛 `UNSUPPORTED_REASONING_EFFORT`，在credential解析和模型HTTP之前。代理健康、供应商实际上支持什么都不会修复这个本地配置拒绝。
- **未修后果：** 按当前runbook准备出的CC/Codex真实插件旅程，在首个需要审核的动作就进入不可用/Global阻断，无法产生本设计所需真实审核模型旅程。之后一律记“provider不可用/inconclusive”会把确定的本地资源配置问题误归为外部服务不稳；也不能临时绕过审核或改审核effort后冒称验证原设计。
- **需要闭环：** 在本次隔离source-config中明确选择/提供一个**已声明支持low且有context window的审核路由**，与main模型选择分开记录；对真实服务再做runbook要求的smoke并如实报告可用性。可以从已有合格目录候选选择，但未调用过的候选仍不能提前宣称真实可用。若确实要更改模型能力声明，须有真实支持依据，不为让fixture通过虚报能力。这里只修验收资源选择，不要求产品恢复过程中换模型、不需要重新询问已决定的CC/Codex范围。

### Recommendations

无额外可选recommendation；不把标准Python环境准备、尚未实施的fixture或未知真实provider可用性重复包装成新的产品审批事项。

### Validation log and limitations

- 冻结SHA、origin/main、本轮unit无diff、首文档跨SHA无diff、git tree blobs、Python版本：只读命令成功，最终复核`[exit code: 0]`。
- 公共stream listener内存探针：`[exit code: 0]`，结果见R1-W1。无安装、无网络、无真实模型/产品栈。
- 一次过宽环境枚举尝试被工具拒绝，没有获得环境清单；未重试该操作，改为仅读取本会话身份变量及Git事实。两个查找中错误猜测的文件路径返回不存在后，使用glob纠正并读取正确文件；不将失败工具调用当验证通过。
- 未跑docs-check/typecheck/build/Vitest/pytest/真实旅程，这不是实现门禁报告。Python不足与provider未知已明确记录；本轮设计审查本身无额外执行阻塞。
- 本轮唯一新增仓库产物是本`design-review.md`，未提交。两项warning需原作者判真、修订并追加Author Resolutions；复审按实际diff决定closure/delta/full，不覆盖本轮结论。

### Author Resolutions

本节由原author在R1原文末尾追加；**不改变上面Issues Found、0 CRITICAL/2 WARNING或Gate 2未过结论**，未签Approved，复审mode/结论由独立reviewer决定。修订基线`bea22ef0ee3215e2498ac653ad4ee1082657f07e`，未改已批准首文档、delta消费者契约、M1数量或产品代码。

保留性校验：追加前R1原文件137行的完整字节SHA-256为`95d48d95adf82df0b6b3218813f2779347edbaa92f89fea4d7cca21971c89a57`；本节之前字节必须原样不变。

#### R1-W1 — accepted

- **判真：** reviewer事实成立。复读公开dsh-llm事件签名，其this是LlmRuntime；sessionId是loop stamped路由身份，根exports有isAgentLoopRequest/markAgentLoopRequest。固定版agent-loop打包L1269–1276确实以`this.session.id`构造并mark冻结request。scope只能拥有listener生命周期，不能作为llm请求归属过滤。原设计“Guardian scoped llm各自包装”会串，不能以测试意图代替缺失隔离。
- **修订：** `design.md`决策5改为唯一integration级llm分派，精确原生reviewer session registry + public loop marker，非所属流在访问任何owner/currentAttempt前透明；CC在自己的直接调用点绑定sink，不以parent ID登记。命中后快照当前attempt、模型/effort/generation校验，每stream独立sink/ordinal，idle只阻断自己的异常流；登记、复用、full/fork新ID、失败setup、quarantine tombstone及按entry对象相等回收均明示。接口新增GuardianStreamOwners，数据流/风险/M1退出标准同步。
- **验证契约：** `reviewer-runbook.md` §5.1要求真实DSH loop/HTTP fixture同时保留idle I、同parent active A/fork B、另一parent C、main M、CC D（D与M相同主session），分别注入429/503/成功和不同usage，核对精确sink/headers/delay/取消；追加旧流→新full、缓存新attempt和idle自发流反例。不能仅靠scope mock或P探针签字。
- **author实际无网络probe：** 公共Context/LlmRuntime/LlmAdapter，在内存adapter中并发发marked ga/gb/main和unmarked CC流，唯一listener在marker+exact ID命中之后才读owner，ALS记录如下；另验证idle自己流拒绝、ga下一动作更换attempt。最终运行exit0，未启动Agent/HTTP/provider，不能证明真实loop/fork/header。最初一次同探针断言成功后误用不存在的`ctx.dispose`导致exit1；已改为公开listener/adapter disposer并重跑exit0，没有把失败轮记pass。

  ```json
  {"seen":[{"id":"ga","sink":"ga-attempt"},{"id":"gb","sink":"gb-attempt"},{"id":"main","sink":null},{"id":"main","sink":"cc-attempt"},{"id":"ga","sink":"ga-next-attempt"}],"captures":["ga","gb","ga"],"ownedIdle":"rejected","network":false}
  ```

可复跑probe（从`packages/dsh-integration`执行；只用声明的根exports，loop marker由probe显式添加，因此不是实际Agent-loop测试）：

```bash
node --input-type=module <<'JS'
import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { Context } from '@deepseek-ai/cordis';
import { LlmRuntime,LlmAdapter,isAgentLoopRequest,markAgentLoopRequest } from '@deepseek-ai/dsh-llm';
const ctx=new Context(),llm=new LlmRuntime(ctx),als=new AsyncLocalStorage(),seen=[];
class Fixture extends LlmAdapter { async *stream(o){await Promise.resolve();seen.push({id:o.sessionId,sink:als.getStore()??null});yield{type:'finish',reason:{kind:'stop'}};} }
const unregister=llm.registerAdapter(['memory'],new Fixture());
const owners=new Map(['ga','gb','idle'].map(id=>[id,{current:id==='idle'?undefined:id+'-attempt'}]));const captures=[];
const unlisten=ctx.on('llm/stream',async function*(o,next){
 const owner=isAgentLoopRequest(o)&&o.sessionId?owners.get(String(o.sessionId)):undefined;
 if(!owner||o.purpose){yield* next();return;}
 assert(owner.current,'owned idle request must fail closed');
 const snapshot=owner.current;captures.push(o.sessionId);
 const it=als.run(snapshot,()=>next()[Symbol.asyncIterator]());
 try{while(true){const r=await als.run(snapshot,()=>it.next());if(r.done)return;yield r.value;}}
 finally{await als.run(snapshot,()=>it.return?.());}
},{prepend:true});
const options=(id,loop=true)=>{const o={provider:'memory',model:'fixture',messages:[],sessionId:id};return loop?markAgentLoopRequest(Object.freeze(o)):o;};
const consume=async o=>{for await(const _ of llm.stream(o)){};};
await Promise.all([consume(options('ga')),consume(options('gb')),consume(options('main')),als.run('cc-attempt',()=>consume(options('main',false)))]);
assert.deepEqual(captures.sort(),['ga','gb']);
assert.equal(seen.find(x=>x.id==='ga').sink,'ga-attempt');assert.equal(seen.find(x=>x.id==='gb').sink,'gb-attempt');
assert.equal(seen.filter(x=>x.id==='main'&&x.sink===null).length,1);assert.equal(seen.filter(x=>x.id==='main'&&x.sink==='cc-attempt').length,1);
await assert.rejects(()=>consume(options('idle')),/owned idle/);
owners.get('ga').current='ga-next-attempt';await consume(options('ga'));assert.equal(seen.at(-1).sink,'ga-next-attempt');
unlisten();unregister();console.log(JSON.stringify({seen,captures,ownedIdle:'rejected',network:false}));
JS
```

#### R1-W2 — accepted

- **判真：** 固定e2e目录deepseek-v4-flash只有high/max，与两种审核器显式low不兼容。复读`apps/node/src/providers.ts:29–49`，levels确实映射为native reasoningEfforts，不会自动补low；provider健康不修复本地effort拒绝。原固定路由不是合格验收资源。
- **修订：** runbook §1/§2固定审核候选为**目录已有**`codexOAuth:gpt-6.1-sol`，所属provider anthropic、context_window=258400、levels已有low；main保持deepseek，不改model声明/产品effort，不在故障恢复中切模型。配置生成脚本先断言唯一route、有正窗口、low声明，再设置tool_approval_model，打印main/reviewer分离摘要。design验收资源段同步。
- **smoke契约：** runbook §2.1在隔离IM配置/能力核对后，分别用CC/Codex真实受审bash动作验证low请求实际到HTTP、合法判定与真实工具一次执行；记录实际模型/effort/callId/代理locator。本地UNSUPPORTED_REASONING_EFFORT等记local_config_failed，HTTP/provider失败另记，未发请求/免审不能算smoke。
- **author实际检查：** 使用临时环境已有PyYAML只读解析仓库目录，assert候选唯一、low与258400窗口成立，旧main不含low；exit0。未改catalog，不调用provider，不读取私人凭据；输出如下。临时Python3.9仅用于该静态解析，不宣称满足仓库≥3.11测试门禁。

  ```text
  {'provider': 'anthropic', 'reviewer': 'codexOAuth:gpt-6.1-sol', 'context_window': 258400, 'low_declared': True, 'main_low_declared': False, 'network': False, 'live_smoke': 'not_run'}
  [exit code: 0]
  ```

- **剩余限制：** 候选尚未真实smoke，实际provider可用性未知；Python≥3.11环境仍需E/Q提供，docs-check/真实IM旅程未运行。以上不伪装为通过，不将本地配置错误归到provider。公开IM relay问题由父P处理，与本地设计修订无关。待独立reviewer按实际diff复审，未授权实施。

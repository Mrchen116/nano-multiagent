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

## Round 2

### Metadata

- reviewer_target: 原独立 delegated Gate 2 reviewer subagent，真实 session ID `f3bff003-49fa-40ab-b29c-e469c1a0daf4`（本轮重新定向核实）。沿用同一审查上下文，未参与需求/设计修订，未把长期 P 身份作为独立审查身份。
- review_mode: **full**
- mode_reason: 实际 diff 不只是旧问题的文字关闭：新增 integration 级 `GuardianStreamOwners.register/wrap` 共享 seam，将原错误 scoped 归属改为全局精确身份分派，并明确 setup/idle/cache/fork/full/quarantine 的登记生命周期；M1退出断言也相应扩展。按 skill 对核心共享接口/生命周期变化的标准，选择 full 而不是仅 closure；不仅核对作者给出的两项 resolution。没有需求范围、跨包依赖方向或客户端变化。
- started_at: `2026-10-20T15:00:05+08:00`
- completed_at: `2026-10-20T15:02:13+08:00`（事实核对完成，随后追加报告）
- duration: `PT2M8S`
- validated_at / executed_base: `617ddaf35d33e3b8528b64bd1ec4afa0d4bfea59`（HEAD与本地origin/main相同）
- previous_validated_at: `bea22ef0ee3215e2498ac653ad4ee1082657f07e`
- effective_base / effective_through: `617ddaf35d33e3b8528b64bd1ec4afa0d4bfea59`；仅设计门禁，不声明实现已完成。
- checkout: `/Users/czj/.nanoassistant/workspaces/nano-product`，branch `main`；开始时仍仅 `.claude/skills/.usage.json` 未跟踪，未读取/改写其内容。
- skills: 本轮实际重新加载 `change-design-reviewer`、report reference与`codebase-design`；沿用已加载AGENTS/change-workflow及R1架构证据。未访问Inbox/conversations、未发公开消息、未修改团队图、未派其他Agent、未建分支或提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2均以独立核实的设计/公共接口事实关闭。修订后的接口、归属与生命周期已足以指导实施；没有发现会使下游实质走偏的新问题。此结论只通过本冻结版本的设计门禁，**不代表实现、HTTP并发矩阵、真实模型smoke、docs-check或产品旅程通过**。

### Reviewed artifacts and preservation

本轮完整读取新`design.md`（227行）、`reviewer-runbook.md`（156行）、整个未变`spec.md`（169行）和delta（85行）、空`.gitkeep`；读取R1原报告及全部Author Resolutions。检查`bea22ef0..617ddaf3`真实diff：只有design、runbook、报告三文件变化；`packages/`、`apps/`、canonical specs、首文档、delta、M1骨架均无diff。未将修改摘要或作者probe当成审查结论。

独立计算R1最初137行原始字节SHA-256，仍为：

```text
95d48d95adf82df0b6b3218813f2779347edbaa92f89fea4d7cca21971c89a57
```

与Author Resolutions的保留值一致；本轮仅追加Round 2，不回写R1或作者resolution。

### Full coverage and evidence

#### 1. Actual assembly, responsibilities and public reuse

- 重新读取生产入口`apps/node/src/main.ts` L39–44、`integration/src/client.ts` L13–24、`integration/src/index.ts` L107–115/L155–158：固定profile将Node模型目录装配到官方pi-ai，再装配同一integration attribution与Guardian。新分派位于真实生产seam，不是新增测试专用审批链。
- `design.md` L120–138/L161–173现在明确：单integration级全局listener负责过滤与sink绑定；Guardian owner管理自身原生session登记/currentAttempt；CC/legacy直接绑定自己的stream；原dispatcher仍只有一个owner。接口保持integration私有，不加入product-contracts、不跨PA/Node/IM引入DSH、不复制loop。
- 该registry不是第二套执行状态机：它保存“本service创建的精确reviewer身份→当前attempt”的窄归属，不保存业务授权、模型调度或新重试额度。新增维护代价是登记/清理成对与tombstone资源；对应真实全局事件不提供scope隔离的事实，抽象有必要且职责集中。没有要求为纯内存映射增加网络port或新服务。
- 独立重读已安装`dsh-llm`根export map、`types/call-config.d.ts` L40–52、`types/types.d.ts` L520–530与打包L357–387：`isAgentLoopRequest`是公开根能力，检查精确request对象的WeakSet身份；sessionId公开定义为loop stamped routing identity，purpose公开区分辅助请求。它不是人类授权证明，设计也没有拿它扩权限。
- 独立读取已安装agent-loop打包L1269–1276：普通request确实mark冻结原对象并写入`this.session.id`。读取`dsh-llm` L2197–2226/L2364–2365：native prepared-call仍把原options传入同一全局waterfall，没有先克隆丢marker。包内部文件只读取证，没有private运行时import。
- 重新核对公开`agents.create` setup/creation-only signal/dispose契约（`dsh-agent` root d.ts L80–103/L129–145）及打包cancel→whenIdle→scope disposal路径，确认setup先登记但不drive、create成功后再绑定和followup的顺序可由现有公开接口实现。

#### 2. Isolation, cleanup, cancellation and concurrent state

`design.md` L124–128/L172/L176–180已经给出可实施的不变量：

1. 原生loop marker + 精确reviewer sessionId先过滤，再访问currentAttempt；不用parent/root/model/prefix归并。主Agent、hand-built CC及辅助purpose透明透传，既有CC sink不被清空。
2. 命中后校验当前generation与冻结reviewer/model/low，快照attempt，stream的next/return沿该快照而非反复读取可变entry。旧流不写后继trace；finally只关闭自己的sink。
3. setup失败释放；idle清attempt但保留身份；缓存复用先绑定新attempt；full/fork使用新ID；dispose/quarantine先失效并保留tombstone直到drain，按entry对象相等删除。取消与配置释放仍不能重发布旧checkpoint，另一个成功fork/trunk不被失败动作清除。
4. tombstone只阻断自身旧reviewer的异常流，不影响main/CC/其他reviewer；5秒cleanup失败仍关闭action，不靠移除登记把未drain的旧资源重新开放。服务卸载继续drain，不kill共享DSH。

这些决定闭合了R1的实际缺口，而不是仅将“并发要测试”加进清单。runbook §5.1进一步要求真实DSH loop + HTTP同时覆盖idle I、同parent A/fork B、另一parent C、main M、同主session hand-built CC D，并验证429/header/delay/usage、取消、旧A到新full F、缓存新attempt、setup失败/quarantine/entry卸载。该矩阵在设计态尚未运行，但目标资源、身份和反例足够明确。

**本reviewer独立无网络probe**使用现有公共Context/LlmRuntime/LlmAdapter、`prepareCall().stream()`、精确loop marker和ALS（不是复制作者probe输出），得到：

```json
{"prepared_stream_seen":[["A","a1"],["B","b1"],["M",null],["M","cc"],["I",null],["A","a2"]],"owner_reads":["A","B","I","A"],"owned_idle":"rejected","loop_marker_copy":"not_preserved","native_agent":false,"http":false,"network":false}
```

`[exit code: 0]`。证明公开prepared-stream入口能保留精确marker，main不读owner、CC原sink保留、purpose不计普通审核、idle只拒自身、缓存切换可绑定新attempt；也确认克隆对象不会保留marker，因此设计保持原envelope、不靠复制字段认领是正确的。**该probe没有真实Agent、fork、HTTP或取消/drain，不能替代runbook矩阵。**

#### 3. All user constraints, safety counts and budgets

重新通读17个Scenario并与本轮设计全文逐项对照：

- 短暂成功、混合故障：同一个ToolExecution构造一个controller，只重判不执行工具体，额外最多2次跨CC阶段/Guardian正常步骤共享；没有被新的requestOrdinal或session registry重置。
- CC完整阶段、Guardian完整正常尝试、整体有界：30/60/90秒和15秒准备、10秒单次退避/20秒总退避、5秒单资源回收、360秒保护未改；恢复不挤原90秒残余。新增身份登记不引入另一套budget。
- 首次格式、再次格式/总额耗尽：EMPTY_RESPONSE与空白/非法统一格式子额度最多1次且占总2次；正常stage推进/context重建不是服务恢复，Guardian全action context rebuild仍≤1。
- CC两阶段/最终deny、Codex风险/可信授权/只读调查、永久错误：保留各原流程和精确冻结动作，无刷deny到allow、无换模型、无扩权；public stream marker仅归属，不替代来源证据。
- 请求/退避取消及单次timeout：parent/owner取消始终优先，generation关闭后无后续恢复/fallback放行/晚到执行；新registry的currentAttempt快照与tombstone与此相容。
- 普通有人值守、Global/child、unattended allow/deny：重新读取`approval.ts` L71–98/L126–145，原分流/deny计数真实存在且设计未改；技术不可用不冒充安全deny，配置allow仍可在终态仅执行一次，不作“耗尽一律零执行”承诺。
- 可追踪内部尝试、真实双策略旅程：review/attempt/request三层与usage未知/partial仍保留，trace经原domain/observe而非假称Work新增attempt UI；真模型、真IM fixture、native与fake-clock证据分层不变。

未受实质影响的source投影/独立模型/审计兼容性与fallback理由 **retained_from: Round 1**；本轮通过产品源码/canonical无diff、设计全文重读和上述关键路径复核，确认未改变R1全覆盖结论，不以旧Approved代替本轮判断（R1原本未Approved）。

#### 4. Reviewer resource selection and executable acceptance

- runbook L50–63明确选择目录已有的`codexOAuth:gpt-6.1-sol`，唯一route、正context window、levels含low先断言；main仍deepseek，不改能力声明或产品effort。重新读取`config/e2e/gateway.yaml` L80–95、`configuration.ts` L64–67与`providers.ts` L29–49，候选名→provider→native id/efforts映射闭合。
- 独立运行只读Node探针，用现有js-yaml解析真实目录，**实际调用仓库`providerProfiles`**，而非只复述作者Python结果：

  ```json
  {"provider":"anthropic","reviewer":"codexOAuth:gpt-6.1-sol","contextWindow":258400,"low":"low","main":"deepseek:deepseek-v4-flash","network":false,"provider_available":"unknown"}
  ```

  `[exit code: 0]`。没有写配置或读取私人凭据；仅证明静态声明经实际mapper后合格，不证明代理/供应商可用。
- 重新读取固定pi-ai L1705–1708/L1848–1852严格effort校验；旧资源确定在HTTP前失败的问题已被合格候选选择修复。runbook §2.1新增CC/Codex各自真实受审bash smoke，不能用普通文件fastpath、health、未发HTTP或缺合法判定算成功；本地配置错误与真实HTTP/provider故障分开。`apps/im-server/src/control.ts` L855–872确有所用capabilities endpoint，并返回models。
- 已指定候选smoke失败时，只能在**验收准备阶段**选择另一已有low+窗口的候选并重跑记录；不是在产品失败恢复中换审核模型，不违背首文档。真实服务未知且暂未运行在设计态已诚实标明，不能因此要求Gate 2先运行模型或制造实现。
- 隔离起停、身份/DB/owner config/DSH home、plugin_manager能力、Work/permission查询和清理证据继续 **retained_from: Round 1**；实际diff未改这些脚本/入口。Python≥3.11仍由E/Q准备；本轮实测仍3.9.6，docs-check未跑，不声称通过。

#### 5. Delta, frontend and milestone

- 完整重读delta并核对current L508–579：canonical target仍正确，MODIFIED的8个原Scenario保留，无误删默认规则、来源、超窗、委派、切换/继承与进行中请求；新增恢复消费者契约未因registry设计改变。
- 首文档与批准边界未变，#330、插件API、通用防循环仍非目标；无客户端变化，无需prototype或提前真实后端实现。
- M1数量、范围、依赖与单闭环组织未变，新增退出断言正是stream归属修订的实施验证，不另开产品范围；骨架仍空`.gitkeep`。full本轮连同扩展的milestone criteria核对，未发现并行冲突或不可解释的验收入口。

### Historical issue closure

| Finding ID | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R1-W1 | accepted；唯一全局dispatcher listener + public loop marker/精确reviewer身份，定义登记/快照/idle/quarantine及并发矩阵 | 本轮读取公开d.ts/exports、真实loop/prepareCall打包数据流；独立prepared-stream/ALS无网络probe；设计L120–138/L161–180和runbook§5.1生命周期/反例闭合 | **closed（设计层）** |
| R1-W2 | accepted；改选已有low+258400声明候选，main分离、配置断言和双策略受审smoke | 本轮读取真实catalog/configuration/mapper并实际调用providerProfiles，确认输出low/窗口；核实smoke不会以health或fastpath替代审核 | **closed（设计层）** |

### Issues / Recommendations

- 新增CRITICAL：0。
- 新增WARNING：0；无历史still-open finding。
- 无额外可选recommendation；不把正常实施/验收门禁重复升格为未收口需求。

### Validation limits and handoff

- 本轮只读Git/身份/探针均检查成功exit code；一次错误猜测的`apps/im-server/src/agents.ts`搜索返回不存在，已用目录grep定位并读取真实`control.ts`，未当作验证成功。
- 未运行docs-check、build/typecheck、Vitest/pytest、真实模型smoke、Agent/HTTP fixture或IM产品旅程；未安装依赖、未启动服务。本轮两个probe均无网络且不是实现验收。
- 具体后续前置：E/Q需≥3.11 dev环境、实际构建与冻结实施SHA；指定审核候选须先按§2.1实际smoke；§5.1真实loop/HTTP及取消/清理矩阵、原17场景和Full适用门禁仍必须执行。若provider不可用据实inconclusive，不用本Approved代替。
- **设计审查无未沟通的具体阻塞。** 本报告未提交；仅向委派者交付。Approved不授权自动merge、部署或发布，后续实质设计变更仍按workflow复审。

### Author Gate 2 closure / retained

原author完整读取Round 2（含full范围、独立公共prepared-stream probe、实际providerProfiles映射证据、17场景、历史finding关闭及执行限制），核对当前受审产物后，**无实质异议，无待改设计事项**。接受R2 `Approved — 0 CRITICAL / 0 WARNING`，R1-W1/W2仅在设计层closed；设计门禁闭环，不等于产品实施或测试通过。

- **reviewed_design_ref / retained_from:** `617ddaf35d33e3b8528b64bd1ec4afa0d4bfea59` / Round 2。受审之后仅追加本报告的Round 2与本closure，无实质设计变化；无需为报告保存动作复审。R1、Author Resolutions及R2 reviewer原文均未回写；追加本节前完整319行报告SHA-256为`bea64a44f6e6579f550e68b0acc1b10b3493cf66d64657d0bb08babf28f3510c`。
- **retained依据：** 与受审SHA逐字节及Git blob比对，下面五项均未变；本次文档交接commit只允许本`design-review.md`一项diff。

| 受审产物 | retained Git blob |
|---|---|
| `spec.md` | `c01ecf2817dbc14ca02fe1c1cdc2d57ed021c686` |
| `design.md` | `d026f8b23c5817001cb7127af9d9c9a71be0731d` |
| `specs/gateway/agent-capabilities.md` | `4c003d9ba89dc25da2bc933642fc6b99b4ad7f39` |
| `reviewer-runbook.md` | `e37371434ba93df07650dbf8b35e3ea257e54875` |
| `M1-review-recovery/.gitkeep` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |

**交E边界：** 默认`change-orchestrator-simple`承接单M1工程交付；须由父P完成正式交办，不在本author会话开始实施。沿用完整预算、action共享2次/format1次、Guardian全action context rebuild≤1、精确原生身份分派/失败状态隔离、取消优先与既有fallback。Python≥3.11及审核候选真实low smoke仍是E/Q前置；真实loop/HTTP并发矩阵、17场景、真实双策略插件旅程、适用Full门禁仍未运行，不写pass。公开IM relay待父P恢复处理；本报告保存不代发消息或团队图、不授权merge/部署/发布。

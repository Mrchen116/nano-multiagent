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

### Author pre-handoff compatibility check — bugfix-626 baseline drift

**新产品事实基线：`051e7d68e159814cdba1e622f760208fc6d3af68`。** 已确认本workspace main只有原有usage.json未跟踪后ff-only同步；未stash/reset/覆盖用户内容。实际读取`ff5fbc8..051e7d68`审批源码、tests和canonical diff，并读626归档design与current实现。不是仅凭PR标题或归档状态判断。

**结论：需实质修订，不能沿用R2 Approved硬交E。** R2对其受审版本的结论保留历史原文，但本次新设计需父P回原独立reviewer复审；author不签新的Approved、不自行派reviewer。用户首文档决定和单M1不变，不需重复问用户。

| 实际变化 | 对625的影响与本次文档处理 |
|---|---|
| approval/classifier/types删除普通动作pa.authorization及personalAuthorization注入 | 625旧prepare表明确要求pa.authorization，已与current冲突，必须改。design准备只冻结有效history/inherited/必要messageContext，显式禁止普通动作全库重读，不把独立消息检查当备用。 |
| sources新增codexEntries、Inbox按message、同call正文去重，历史/继承规范化 | 保留真实sender/page/reply/live-restored和不同call；design明确投影后cursor、冻结rows和full恢复不复活压缩原文，runbook加入交叉回归。 |
| codex-context profile/admission恢复固定参考逻辑，codex.ts移除0.65乘数 | preserve/recovery phase需跨service恢复保留；全action context rebuild额度不重置，required/action不可丢，不能从旧草案恢复任意缩放。design决策2及626交叉约束同步。 |
| 新output_contract及parser接受bare/embedded/default verdict，不再parser额外critical-allow拒绝 | 会改变625“格式失败”入口，必须明确现parser是语义owner；合法bare allow/deny不得耗format额度，不重建旧四字段校验。新增503→bare allow等用例。 |
| canonical新增“普通工具审批遵守当前有效执行上下文”Requirement | 位于625 delta所替换Requirement之外，原最窄delta仍适用；已逐段比较完整replacement与最新canonical，其差异仍仅原计划的失败分流两行。保留626新Requirement，不用旧canonical整文件覆盖。 |

修订文件为`design.md`（最新事实基线、626保真约束、prepare/context phase/format及M1退出标准）、`reviewer-runbook.md`（§5.2组合回归）及本报告追加。首文档、delta、M1骨架未变；没有产品代码修改。完整预算/2次总恢复/format1次、精确stream身份分派、原fallback及审核路由smoke前置不变。

**工程必须保留的验证：** 现有approval-sources、codex-approval、personal-security和native/lifecycle测试；新增恢复中pa.authorization读取0、库外/压缩历史不入prompt、规范化正文不重复/来源不升级、503→bare allow的format=0、bare deny不重试、context→service恢复phase/required保护不退化及PA独立两道消息检查回归。626历史报告不是625实现pass；本轮仅静态核对，未运行产品测试/真实smoke，Python≥3.11和真实reviewer候选可用性仍待E/Q。

## Round 3

### Metadata

- reviewer_target: 原独立 Gate 2 delegated reviewer，实际session `f3bff003-49fa-40ab-b29c-e469c1a0daf4`（本轮定向重新核实）；同一执行者续审，未参与626产品修改或625设计修订，不以长期P身份冒充独立reviewer。
- review_mode: **full**
- mode_reason: 实际产品diff改变普通审批证据入口、共享来源投影、Guardian admission与parser语义；设计实质修改prepare的核心证据边界、context恢复策略及M1退出判据。不是单纯报告保存，也不能仅做旧finding closure。按skill选择full，覆盖本轮影响并重核完整需求/安全闭环；未变化的公共运行时能力有明确retained依据。
- started_at: `2026-10-20T18:10:52+08:00`
- completed_at: `2026-10-20T18:13:35+08:00`（事实核对完成时间；随后追加本报告）
- duration: `PT2M43S`
- validated_at / executed_base: **`d9de1581d13cca8485dfc1db658e1ac13bc06b47`**（本轮HEAD及本地origin/main相同）。
- product_baseline: **`051e7d68e159814cdba1e622f760208fc6d3af68`**；独立Git核实其后至本轮冻结SHA的`packages/`、`apps/`、canonical spec均无diff。
- previous_reviewed_design_ref: `617ddaf35d33e3b8528b64bd1ec4afa0d4bfea59`；历史R2闭环保留，但不作为新设计自动通过的依据。
- effective_base / effective_through: 本轮冻结SHA；仅设计审查，不是实现/产品验收。
- checkout: `/Users/czj/.nanoassistant/workspaces/nano-product`，branch `main`；开始时仅原`.claude/skills/.usage.json`未跟踪，未读取/修改。
- skills/scope: 实际加载`change-design-reviewer`，沿用已加载`codebase-design`、report reference与仓库workflow。只追加本report；未改设计/产品/团队图，未提交、建分支、访问Inbox/conversations、公开发送或委派。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。新冻结设计的Gate 2未通过。**

主要兼容修订方向与626实际产品一致；但新增来源描述把“同action技术恢复/同进程委派”和“失去live provenance的进程恢复”混在一起，可能引导工程无条件将当前仍可信live的继承/冻结证据降为restored。应由原author局部消歧并补双向回归，见 **R3-W1**。不要求重新确认已决定的人类范围、预算或fallback。

### Artifact and diff coverage

先读Author compatibility check L338–354，再独立读取实际diff，没有用其摘要替代取证：

1. 比较`617ddaf35..051e7d68`的产品审批源码、资产和canonical变动；完整读取当前`approval.ts`、`classifier.ts`、`types.ts`、`sources.ts`、`codex-context.ts`、`codex.ts`及相关测试定义。
2. 比较`051e7d68..d9de1581`，确实只改625 design/runbook/report三文件；完整读取新design（236行）、runbook（166行）、delta（85行），重读首文档17场景与非目标、当前canonical L508–596，并读取626归档design作历史参照而非产品事实替代。
3. spec/delta/M1骨架从R2至本轮均无变化；新design blob=`bf805a016b136192641341574ea442291a7d82e7`，runbook blob=`7d9df2dbff9f25f2b5417ecd12842b4dcb34d022`。
4. 本轮追加前354行报告SHA-256=`74dc583befee89eea2b5de9b09f3b5ad08868e2bb48054d43ebc322cea570374`。R1、Author Resolutions、R2和兼容核对均保留；不修改旧结论。

### Full coverage and independent evidence

#### 1. Production assembly and responsibility boundary

重新读取生产`apps/node/src/main.ts` L39–44、integration `index.ts` L107–115/L155–158，确认仍是Node生成官方profile、integration安装attribution和CC/Codex/NanoApproval，非仅测试入口。`approval.ts` L126–129现在只构造exec/config/sources/inherited/messageContext/reviewer，已删除普通动作`pa.authorization`；classifier的transcript/system和types也删除该参数。`codex.ts` L66–73的真实动作没有旧授权包。

本轮设计L58/L101将15秒prepare改为当前有效history/既有inherited/必要messageContext，禁止全库重读；与生产边界吻合。恢复controller应隐藏额度、时间、取消和trace，不负责检索新授权、重建消息库或解释风险schema。原策略/source/parser继续拥有投影与语义，facade继续拥有最终路由和工具调度。复用626纯投影/admission比新增retry专属摘要器、授权包或第二套parser更局部且维护代价更低；设计选择正确，除R3-W1的来源范围表达外未发现需重构的职责缺口。

PA独立链确实仍存在：读取`personal-assistant.ts` L59–84的非主人participant入站、L103–109的prepare→独立action review→commit、L136–155的主人DM豁免/对外证据；integration `index.ts` L429–456暴露`pa.evidence/pa.review`，`personal-security.ts` L23–43使用独立无工具stream。它们不是普通工具失败备用审核，不因普通取数为0而应删除。对应源码从R2至本轮无diff。

#### 2. Effective history, normalization and frozen evidence

- `sources.history` L131–175使用`deriveMessages()`，PTC仅挂到仍有效的root；普通CC不附generic工具正文，Codex请求toolResults/fullAssistant，压缩删除原文不靠遍历DB补回。
- `codexEntries` L20–27按宿主结果call id仅删除同call generic outcome/body，Inbox逐message复制页级外壳；sender/reply/delivery/observation不会因类别选择而改写。空页保持结果。当前history L175已规范化；`codex.ts` L66对inherited也规范化，L67才计算serialized cursor，L68前缀不匹配即丢cache。
- 规范化后的冻结rows适用于技术恢复full；失败reviewer历史不回灌，model/provider/动作不切换。设计L59、L91、L93和runbook§5.2覆盖这些新交叉点，未要求复活父压缩原文。
- 重新读取`approval-sources.test.ts` L34–66/L86–113/L122–147，现有测试定义覆盖当前live、release后restored、压缩root、manual exact action、恢复继承去重；本轮未执行这些测试。**同进程继承是否仍live必须按真实epoch保留，不能从测试只含recovered=true反例推导“一切inherited都是restored”**，详见finding。

#### 3. Guardian profile/admission and service recovery

完整读取当前`codex-context.ts` L86–130及`codex.ts` L78–87：历史计入message成本；非用户纳入才计40；单项消息/工具5000/1000、聚合20000/10000；已选assistant和最近5条已选工具required。最终请求计入完整action、framing和omission；required不足时只有recovery可按顺序缩历史正文、保来源和首尾，其余required不牺牲；optional先剔除无法单项容纳者，再从旧项移除。当前delta显式false，full默认true；0.65确实已删。

修订设计L60/L93及runbook L157正确沿用这个现行phase：初次full也使用默认recovery admission，并非service故障后才首次允许历史收缩；有checkpoint的delta preserve不裁历史，放不下进入正常context rebuild。service失败后的干净full使用冻结证据与同一规则，不通过新session重置全action contextRebuildRemaining。没有新百分比缩放、扩大窗口、换模型或裁动作以换成功。要求context rebuild→503→full与required放不下的组合回归，是合理新增退出条件而非暗增需求。

#### 4. Parser owns valid verdicts; format recovery does not reinterpret risk

当前`codex-context.ts` L10–26与新增output_contract确实接受bare allow/deny及外围文本JSON；allow缺省low、deny缺省high、authorization缺省unknown、空/缺rationale用默认，非法outcome/enum/type仍拒。旧四字段强制和额外critical/high allow过滤已删，不应由retry controller重造。

设计L61–62/L118将有效性完全交给现parser；runbook§5.2明确503→bare allow只耗service额度、format=0，bare deny不重试，符合首文档“真实有效deny不刷allow”。读取`codex-approval.test.ts` L8–14/L28–52的现有样例定义核实预期；本轮没有运行parser/产品测试，也不把626旧测试记录当625通过。此兼容修订闭合，无新增warning。

#### 5. All 17 scenarios, budgets, cancellation and old routing

重读首文档L59–169并与新design全文核对：

| 首文档场景组 | 本轮判断 |
|---|---|
| 短暂恢复成功、混合共享次数 | controller仍隶属ToolExecution，2次总恢复跨阶段/故障类型，新source/cursor/session不另送额度；只重判不调用工具体 |
| CC完整阶段、Codex完整90秒、整体有界 | 30/60/90秒、15秒prepare、20秒总退避、5秒回收、360秒保护未变；Codex330/CC265秒估算仍容纳完整末次机会 |
| 首次格式、再次格式/总额耗尽 | format最多1次且占总2次；626 bare/default语义由parser先决，EMPTY_RESPONSE仍统一格式子额度 |
| CC阶段/最终deny、Codex风险授权检查、永久错误 | 正常CC stage推进不耗恢复；只读调查与context不成新授权；永久错误不换模型/刷allow；证据原样保真范围尚有R3-W1 |
| 主动取消、非主动单次timeout | parent取消优先，generation失效、drain/quarantine、late create只清理仍在；不会以context/profile新phase重置期限 |
| 普通有人值守、Global/child、unattended allow/deny | 重新读取`approval.ts` L71–98/L131–143，原route/计数事实未改；耗尽按旧配置，cancel无fallback放行，不声称全部耗尽零执行 |
| 内部尝试可追踪、真实双策略插件旅程 | action/attempt/request与已知usage/unknown、optional audit兼容、真实Work/副作用及四类证据分层保留；§5.2增加有效上下文/输出组合回归 |

**retained_from: Round 2**：公开DSH failure/create/dispose/全局stream marker能力、精确reviewer registry/ALS方案、HTTP facts seam、optional audit、取消晚到不复活的架构可行性。独立Git核实依赖声明/lock、安装入口、attribution/audit及相关DSH边界没有产品diff；新design对应接口与决定逐段未改。R2 probe仍仅说明公开seam可行，不能当本轮新source实现或真实loop/HTTP验证。

#### 6. Canonical/delta, milestone and acceptance prerequisites

本轮独立Node只读文本断言核对delta的完整MODIFIED块：8个Scenario都在，规范化预期的失败WHEN及新增legacy AND后，与最新canonical对应块逐字一致；返回`modified_scenarios=8, only_expected_failure_lines=true, new_626_requirement_outside_replacement=true`，exit0。626新增“普通工具审批遵守当前有效执行上下文”在该窄replacement之外，必须保留；delta无需复制整个canonical或另写重复Requirement。

单M1数量/依赖/并行组未改，扩展的是626交叉回归退出条件，和恢复安全闭环同属一项，不需拆层或新审批。M1骨架仍空；源码/前端没有本轮新客户端面，无prototype要求。runbook原隔离起停、真实IM/Work入口与专用low审核候选前置 **retained_from: Round 2**，对应apps/config/脚本未变化。新§5.2已明确真实PA受审任务不走fastpath冒充审核、库外标记和副作用分开记录、626历史replay不替代本候选SHA。Python仍3.9.6，模型真实smoke/HTTP旅程仍待E/Q，不写已验证。

### Historical issues

- **R1-W1 — closed（设计层，retained_from Round 2）**：本轮仍为精确原生身份先过滤的唯一全局分派，无恢复错误scoped隔离假设；本轮不重跑也不升级旧probe为产品证据。
- **R1-W2 — closed（设计层，retained_from Round 2）**：审核候选、静态low/窗口断言和双策略真实smoke契约未变，不把health当可用性。
- R2无finding；本轮新基线需要自身结论，不沿用旧Approved。

### Issues

#### R3-W1 — 明确区分同action技术恢复、同进程委派与失去live provenance的进程恢复，不能无条件把inherited写成restored

- **位置：** `design.md` L59“恢复/inherited仍restored”；`reviewer-runbook.md` L154“继承Inbox维持restored”。前者与L58/L91所说复用冻结投影相邻，未限定“恢复”是进程恢复而非本unit的service恢复；后者也没有给出同进程对照。
- **独立事实：** 当前`approval.ts` L55–57保存委派来源时记录`epoch: this.epoch`并保存真实history；L65–68仅在`saved.epoch !== this.epoch`时以`recovered=true`重投影。`sources.restoreEntries` L77–87明确：同进程旧`host_context_live`在`!recovered`时保留live，已有`inbox_result`也只有recovered=true才改restored。`codex.ts` L66再次restore时传false，`codexEntries`本身只规范化/去重、不改observation。因此当前并非“一切inherited都restored”；同一action一次503也不使本进程失去已经观察到的live来源。
- **为何需要修订：** 625承诺保留626来源语义，不新增授权规则。若按这两句实现统一降级，原本同进程可信Inbox证据会在委派或内部service恢复后变成仅历史背景，已授权动作可能无故被拒/要求重确认、转人工或进入unattended fallback；反向若为保通过又一律升live则更错误。新接口必须固定真实observation，而不是因“恢复”重命名来源。现有recovered=true测试不足以证明两条路径都保留了现状。
- **需要闭环：** 原author把文本限定为：技术恢复重用本action已冻结的实际live/restored标记，普通同进程inherited按现有epoch/来源契约保留，不做无条件降级；只有真正失去进程观察证明的恢复/跨epoch委派记录才按现有restore规则变restored，已restored不能提升。runbook增加同进程live继承及其503→full仍live、跨epoch/旧持久记录restored的对照，均保留sender/page/reply与去重/cursor。无需新消息库检索、改变授权语义或重问用户。

### Recommendations and validation limits

- 无额外可选recommendation；新增0 CRITICAL / 1 WARNING。
- 本轮成功只读Git/文本断言均核对exit0；没有安装、启动服务、真实模型、产品源码执行探针或实施测试。未运行docs-check/build/typecheck/Vitest/pytest/真实IM旅程，Python合格环境与实际路由可用性仍需E/Q。
- 本轮仅追加R3。具体阻塞是R3-W1来源语义消歧与对照验收契约；回原author判真修订、冻结后续投本reviewer。没有需求范围或人类决策阻塞，不授权merge/部署/发布。

### Author Resolutions — Round 3

**完整读取R3，R3-W1 accepted。** 原author核对current `approval.ts:55–68`的delegated epoch及`sources.ts:65–88`的restore逻辑后判真：原文把技术恢复、同进程继承与丢失观察证明混称“恢复”，存在误导统一降级的实际风险；不能以收紧来源为安全理由改变既有可信授权语义。

| Finding | Author resolution | 具体修改 / 待验证 |
|---|---|---|
| R3-W1 | **accepted，已修订，待独立reviewer复核** | design的626来源约束明确三条路径：同action503/timeout/full/context重建保留冻结的真实live/restored；同epoch继承按现`restoreEntries(...,false)`保留，包括旧`host_context_live`；仅跨epoch/丢观察证明按现true规则restored，旧`host_context`及已有restored不升live。runbook§5.2同步删去无条件降级措辞，加入同epoch live继承→503→full仍live与跨epoch/旧持久restored→503→full仍restored的双向对照；sender/page/reply、去重/distinct call及cursor均继续对照。 |

**retained / 边界：** 首文档、最窄delta、M1骨架均无变化；626其余入口/admission/output、恢复预算/次数、失败分支隔离、精确stream归属、审计、取消与既有fallback不受W1修订影响。没有新增授权取数、重检用户、产品代码或范围调整。仅design一处来源约束、runbook§5.2来源措辞及一项对照验收、本报告追加；旧reviewer各轮原文未修改。R3非Approved，本resolution不是门禁通过；冻结新ref交父P续原reviewer，author不指定审查mode、不签Approved。本轮只做静态文件/diff核对，未执行产品测试、真实smoke或docs-check，不新增pass声明。

## Round 4

### Metadata

- reviewer_target: 原独立 delegated Gate 2 reviewer，实际session `f3bff003-49fa-40ab-b29c-e469c1a0daf4`（本轮定向核实）；同一reviewer续审，未参与设计修订或产品实施。
- review_mode: **closure**
- mode_reason: 已独立检查`d9de1581..6760d853`真实diff：设计仅L59来源语义消歧，runbook仅§5.2对应措辞及同epoch/cross-epoch对照，报告保存R3并追加Author Resolutions。没有需求、核心职责/接口、milestone或产品变化；新增对照是原R3-W1所需验证契约，不是新范围。118行增量主要来自历史报告，不据行数扩大为full。closure范围足够，无需扩大。
- started_at: `2026-10-20T18:20:34+08:00`
- completed_at: `2026-10-20T18:21:05+08:00`（事实核对完成，随后追加报告）
- duration: `PT31S`
- validated_at / executed_base / effective_base / effective_through: **`6760d853f06ac81401977514975a9985587196f9`**（HEAD与本地origin/main相同）；产品基线仍为`051e7d68e159814cdba1e622f760208fc6d3af68`。
- checkout: `/Users/czj/.nanoassistant/workspaces/nano-product`，`main`；开始时仅原`.claude/skills/.usage.json`未跟踪，未读取或修改。
- skills/scope: 实际重新加载`change-design-reviewer`及report reference；仅读文件/Git和追加本报告，没有改设计/产品/图、提交、建分支、公开发送、读取Inbox/conversations或派Agent。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

**R3-W1 closed（设计层）。** 作者accepted不是通过依据；本轮按实际源码与修订契约独立核实后关闭。Approved适用于新冻结设计，不表示625实现、真实smoke/HTTP矩阵或产品验收完成。

### Closure evidence — R3-W1

- **Author Resolution：** L460–468 accepted，明确三个不同生命周期，设计与runbook同步修订，没有以更严格来源降级为理由改变现有语义。
- **当前宿主epoch事实：** 重新读取`approval.ts` L26/L55–68，epoch属于NanoApproval实例；委派保存实际来源和当前epoch，读取时仅以`saved.epoch !== this.epoch`选择recovered。新design L59同epoch使用false、跨epoch使用true与真实入口一致，不是由reviewer sessionId或技术retry次数推断来源。
- **旧格式和新格式均闭合：** 重新读取`sources.restoreEntries` L65–88：旧`host_context_live`仅在false时live；仅旧`host_context`始终restored；新`inbox_result`在true时降为restored，false保留原标记，不把已有restored提升。新设计明确旧持久格式沿原restore语义；runbook L156另列同epoch旧`host_context_live`，没有仅测新格式或跨epoch。
- **规范化不重标：** 重新读取`codexEntries` L20–27，其只按call去重并按message展开，保留外壳；`codex.ts` L66–68先对已按epoch处理的inherited使用false并规范化，再算serialized cursor。新design L59把首次prepare冻结规范化rows、后续service full复用及禁止反复按进程恢复规则重标写明，与源码边界和既有625冻结设计相容。
- **原缺口已消除：** design L59删去“恢复/inherited仍restored”，明确503/timeout/新full/context rebuild均不改变同action冻结observation；runbook L154–156删去无条件继承降级，并要求①同epoch父live→委派→503→full仍live，同时混入restored仍restored；②跨epoch/失去证明/旧host_context→restored→503→full不提升；另测旧host_context_live。sender/page/reply、同call去重/distinct call、cursor继续逐项对照。既防止误降级导致重新确认/错误fallback，也防止为通过而升级来源。
- **职责与权限没有漂移：** 仍由现有宿主epoch/restore契约解释来源，codexEntries负责投影，controller只复用冻结证据；未增加消息库读取、授权检查或第二套来源规则，不改变原用户授权边界。

### Retained scope and preservation

**retained_from: Round 3**：全17场景、626零普通全库读取、admission/parser与canonical窄replacement、M1和其他安全契约；**retained_from: Round 2**：既有公开DSH/transport seam与审核模型预检设计事实。本轮独立Git核实从产品基线至6760d853的packages/apps/canonical/config/scripts/lock无diff，spec/delta/M1骨架从R3受审版本无diff；设计和runbook实际变化仅上述闭环，不是仅凭作者声明保留。

开始时冻结报告468行SHA-256=`aa149f36e428d11ac94814042c3a68d7354a0add6e60bcd07889c38b6b312fc4`；本轮只在其后追加Round 4。重新断言原R3输入的前354行SHA-256仍为`74dc583befee89eea2b5de9b09f3b5ad08868e2bb48054d43ebc322cea570374`，没有回写历史结论或Author Resolutions。

### Issues / Recommendations / limits

- 新增CRITICAL 0，WARNING 0；R3-W1关闭，无still-open finding。R1-W1/W2的设计层关闭状态不变。
- 无额外可选recommendation，无设计审查具体阻塞；回原author完成报告闭环保存，再由父P按workflow交接。
- 本轮是静态closure，所有执行的Git/文本校验检查exit0；未运行产品源码探针、模型smoke、Agent/HTTP fixture、IM旅程或docs-check/build/typecheck/Vitest/pytest。实测系统Python仍3.9.6；≥3.11环境、实际审核路由可用性及所有实施/验收门禁仍由E/Q完成，不写pass，不用旧probe代替。
- 未提交、不授权自动merge、部署或发布。后续若产品基线或设计实质变化，仍需按实际diff核对，不能将本次Approved无限外推。

### Author final Gate 2 closure / retained — Round 4

原author完整读取Round 4，核对其R3-W1独立闭环证据、retained范围和执行限制后，**无实质异议，无新增设计修改**。接受R4 `Approved — 0 CRITICAL / 0 WARNING`；R3-W1与R1-W1/W2均在设计层closed。R4 closure与R3 full retained共同构成当前设计门禁闭环，不表示产品实现或验收通过。

- **reviewed_design_ref / retained_from：** `6760d853f06ac81401977514975a9985587196f9` / Round 4（full范围沿R3 retained）。本次只保存R4原文并追加本closure；所有reviewer历史及Author Resolutions保留，不修改结论；无需为report-only保存再审。
- **交接前远端核对：** fetch origin main成功，远端仍为`6760d853f06ac81401977514975a9985587196f9`，未出现进一步提交或影响625的语义变化。产品事实基线仍为`051e7d68e159814cdba1e622f760208fc6d3af68`；最终提交与受审SHA在全仓和unit内均只允许本报告差异。五项产物逐字节及blob比对不变：

| 受审产物 | retained Git blob |
|---|---|
| `spec.md` | `c01ecf2817dbc14ca02fe1c1cdc2d57ed021c686` |
| `design.md` | `f44953c2164854c83b056bab3ff043d7ac85d111` |
| `reviewer-runbook.md` | `d7f3259772b4f3627d926fe8dacbb0aa802d573e` |
| `specs/gateway/agent-capabilities.md` | `4c003d9ba89dc25da2bc933642fc6b99b4ad7f39` |
| `M1-review-recovery/.gitkeep` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |

**交E：** 由父P正式分配，默认simple、单M1。626来源双向对照（同epoch live继承→503→full仍live、跨epoch/旧持久restored不提升）、零普通全库取数、admission/output组合回归，与完整预算/共享额度、精确stream归属及原fallback必须保留。真实low审核路由smoke与Python≥3.11仍为E/Q前置，所有实现/真实HTTP/IM旅程及Full门禁待执行，不新增pass声明。本author不实施、不发群/改图、不授权merge/部署/发布。

## Author re-grounding for 2026-10-26 clean retest — awaiting independent Gate 2

本节是新author对当前材料的适用性说明，**不是Round 5 reviewer报告、不是Approved，不继承以上历史验收或设计批准**。历史Round 1–4及各Author Resolutions原文保留。新目标仅来自本群 `c_sfokibtk` / `tg_0dd3b230`，P节点n2；无旧群/会话/任务/定时复查恢复，没有产品代码修改。

- product_baseline: `304c59412e8316ef3ea7df9d904a9a450ca618a2`；本次新workspace main开始clean，远端同SHA。
- first_document: `411c4a5b846c3ca632dab3e5632b78f296d5ea83`重新grounding；`d72e220f1d21827c65e046f704c13837ea39d7c2`以父P二次提供的实际消息正文替换首次压缩交接引文，二者均已正常推送main，无历史重写。末次历史授权措辞按父P反馈随设计提交修正，17场景/取舍不变。
- author_checkout: `/Users/czj/.nanoassistant/workspaces/nano-product-r2-1026`，同一持续现场，设计branch `design/feat-625-r2-361`；没有新建worktree，未接管旧分支/dirty材料。按本次明确派发在设计分支提交，而非沿旧报告main习惯推设计。
- skills: 实际加载change-spec-author、change-design-author、codebase-design及nano-team-work；Gate2需父P调度独立change-design-reviewer，并因冻结输入/恢复/来源生命周期影响执行agent-context-review Design Review。reviewer自行决定复审mode/范围，不由author签字。

### Current evidence and material revisions

| 当前核对 | 修订 / 保留 |
|---|---|
| classifier.ts无失败恢复；codex.ts只有原90秒内context重建；当前audit无attempts | action controller/共享2次/format1次、完整预算、结构化failure、可取消退避与drain/quarantine仍为真实新增缺口。保留原stage/Guardian流程、路由与权限。 |
| 当前默认Codex，继承含Codex/CC/DSH | delta原默认Nano已过时；现完整MODIFIED条目以current为准，只有失败Scenario是本次行为增量，其它Scenario原样保留。 |
| classifier/codex已按模型声明low/default/first选effort | design与runbook改为冻结resolvedEffort；不固定low、不新增选择器、不要求改模型。旧R1-W2的旧配置事实不延伸为当前限制。 |
| Guardian现同时服务tool/disclosure，PA严格parser/上下文不同 | 普通tool才持有恢复controller/registry；disclosure原预算/parser/context/host commit/namespace保留，增加同parent并发回归，不扩成PA消息重试产品。 |
| inspection已是可SIGKILL单次子进程；current有shared-host owner lifecycle与新来源 | 保留killable FS、独立系统/指令隔离；补owner disable/release不复活/不影响其他owner，represented user/Task/UI stop来源与冻结证据组合验证。 |
| 现行worktree-runtime要求daily真实验收 | runbook改daily清单与实际阵容/策略回执/路由smoke；default fixture另跑，不与daily混用。Q实际节点、实例身份、实施SHA、可跑fixture与脱敏observe导出由E工程冻结交接，不伪造。 |

### Actual checks and limits

- `pnpm install --frozen-lockfile` exit0；重读固定公开DSH exports/d.ts及相关打包实现，根import核实LlmError/BlockAssembler/isAgentLoopRequest/resolveRetryPolicy均为function。原生retry仅agent/request-error插件，不能取代action级共享额度；没有private import/patch。
- `pnpm exec vitest run packages/dsh-integration/tests/codex-approval.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/approval-sources.test.ts`：3文件、31/31通过，exit0。它们证明已有回归基础，不证明625恢复实现或真实产品旅程。
- 默认docs-check因系统Python3.9.6缺yaml失败；在本次独立临时venv安装PyYAML/markdown-it-py后发现collection缺pytest，补pytest/httpx/websockets后仍缺pytest-timeout；直接collect诊断出不识别timeout参数，补插件后最终 `PYTHON=<本次临时文档环境>/bin/python ./scripts/docs-check` exit0：271 maintained Markdown sources / 68 required routes。此环境仅用于文档检查，不假称满足仓库Python≥3.11全栈门禁。
- 未运行build/typecheck/全量CI、native HTTP fixture、真实provider smoke或IM插件旅程；没有产品验收结论。正式fixture/trace导出尚待M1实施，真实服务是否可用未知。
- 下一步：父P取得设计冻结ref/SHA后创建本次独立reviewer，以此report为历史入口续写Round 5；审查可扩大范围，不能据旧R4 Approved放行。author继续承担同目标文档返修，不自己做独立审核或开始产品实施。

## Round 5

### Metadata

- reviewer_target: **本次干净重测的新独立 delegated Gate 2 reviewer**，本会话身份 `3f058592-de41-4487-93b5-116f6a20e871`（运行时提供）。未参与本任务需求、设计或实现，不是历史 reviewer `f3bff003-49fa-40ab-b29c-e469c1a0daf4`，不以 P 的长期身份充当独立性证据。后续本任务设计复审继续交本 reviewer，不另开首审上下文。
- review_mode: **full**。
- mode_reason: 新人类交办、新 reviewer 与新 main 适用性审核；current 已改变默认策略/effort、共享 tool/disclosure 执行器、来源语义、可终止 inspection 与 shared-host lifecycle。旧 R4 是旧树的 closure，不能证明本次核心边界/共享接口与验收链仍正确。完整重核全部五项产物、17 场景、真实装配入口、职责/复用、Context Lifecycle、delta 和 M1，不沿用旧 Approved。
- started_at: `2026-10-26T13:01:05+08:00`（首次显式采集的审查时钟；初始加载和阅读早于此值）。
- completed_at: `2026-10-26T13:05:33+08:00`（事实核对结束，随后追加报告）。
- duration: `PT4M28S`（上述可核实时钟区间，不冒称包含此前全部阅读时间）。
- validated_at: **`c78148c1aab7a8486341c5ba839528417a6b4fff`**。
- executed_base: **`d72e220f1d21827c65e046f704c13837ea39d7c2`**（本轮实测本地 `main` 与 `origin/main` 相同；远端同名设计 ref 的 ls-remote 由父 P 核实，本 reviewer 未另查网络）。
- product_baseline: `304c59412e8316ef3ea7df9d904a9a450ca618a2`；独立 `git diff --exit-code` 核实至受审 HEAD 的 packages/apps/config/scripts/lock 无产品差异。main 的新增首文档不被当作已实现能力。
- effective_base: executed_base；effective_through: validated_at，仅表示本轮设计审查适用范围，**不是 Gate 2 通过或实现有效性声明**。
- checkout/branch: `/Users/czj/.nanoassistant/workspaces/nano-product-r2-1026` / `design/feat-625-r2-361`；开始与落盘前均 clean，HEAD 未变。
- skills: 实际加载 `change-design-reviewer`、`agent-context-review`（**Mode A — Design Review**）、`codebase-design`、`nano-team-work`，读取 report/DEEPENING、AGENTS、TEAM/ROLE、文档地图、change-workflow、Agent Context Engineering、storage 与 canonical contributing。未读 Inbox/conversations，未公开发消息、改团队图、建 worktree/分支、提交或委派他人；唯一写入为追加本报告。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 未通过。**

总体恢复方案可实施：action 级计数、每次完整预算、冻结来源、Guardian 失败分支隔离、精确 stream 分派和原 fallback 有明确落点。新发现 **R5-W1**：设计把 `configuration release` 列作当前 action 的撤销边界，却未区分真实产品中“配置事务释放 reservation”和“执行 owner/审核租约退役”。前者在配置被拒或持久化失败时也发生，不能据此取消正在按旧配置运行的工具审核。需原 author 按真实入口消歧并补对应反证；不需要重新询问已确认的预算、策略或授权。

本结论不是因为缺少产品实现、fixture 实物或真实模型运行而阻断；这些在设计中明确属于 M1/工程冻结交接与后续门禁，不能伪造已执行。

### Frozen artifacts and preservation

完整读取以下受审文件以及原报告全部 555 行，旧 Round 1–4、Author Resolutions 和 2026-10-26 re-grounding 附录均保留，不把作者附录当新 review verdict：

| 文件 | 受审 HEAD Git blob |
|---|---|
| `spec.md` | `7d0b83f9b7e573df2b3b4994cf20a708a16b58c0` |
| `design.md` | `f15e4b0037a4ef19e819636015194199a774ee2a` |
| `specs/gateway/agent-capabilities.md` | `54bc2519aeca6b88a8e881edb155a408d10cae66` |
| `reviewer-runbook.md` | `7976b37c7f1507344aa750494436e5cfa9970c99` |
| `M1-review-recovery/.gitkeep` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`（空） |

追加前完整报告 SHA-256 为 `1e8a7db4a5db7d8ea41367255aad75e8b662813017113fdd615af3cbe66bb01d`。本轮不回写旧结论或作者 resolutions；没有新 tasks/progress/实现记录。

### Full coverage and independent evidence

#### 1. 从真实产品入口核职责与复用

- `apps/node/src/main.ts:19–21,100–155`：产品装配 PA/Channels，经 `@nano/dsh-integration/client` 启动普通 shared host/PA partition；实际 providerProfiles 写入公开 profile。`integration/src/client.ts:14–26,47–52` 与 `cordis.patch.yml:19–33` 确实装配官方 DSH base + NanoRuntime，非测试独有路径。`SPEC.md:26–52` 的依赖方向不变。
- `integration/src/index.ts:137–145,208–212` 在该真实 runtime 安装唯一 attribution、CC/Codex 与 NanoApproval；`policy/approval.ts:103–150` 是 downstream/免审→真实 message context→策略→审计/原分流的实际工具闸口。`session.observe` 在 `index.ts:460–466` 返回持久 `approvals`；不是新建 IM API、Session event 或另一执行 loop。
- 私有 `ReviewRecovery` 适合归 integration policy：集中隐藏共享额度、计时、取消、结构化失败与 trace；CC 保留 stage 语义，Codex 保留 reviewer/检查/context 生命周期，facade 保留计数和最终路由。若整个 facade 套 loop，会重做免审/来源准备/CC stage1 或原 fallback；若全局改 provider retry，则影响 main 且无法表达 format 子额度。设计不选这两者有实际安全与维护理由。
- `policy/codex.ts:17–27,56–81,100–158` 当前泛型 run 同时服务 tool/disclosure；`reviewDisclosure` 使用独立 `purpose`、严格 `parsePersonalDecision` 和 fullEvidence profile。`index.ts:562–583` 是真实 PA action 入口，`personal-security.ts:97–126` 另有严格 parser 与独立入站审查。设计 L32、69、90、186 明确 tool 才接 recovery；保留 disclosure 原 90 秒、context rebuild、namespace、reason/needs_owner/unavailable 与宿主 commit。此共享代码不意味着扩张 PA 重试权限。
- 只读 inspection 已是 `codex-inspection.ts:59–65` 的单次 `execFile` + `SIGKILL`。设计保留它，不重新发明进程内 FS，也没有以仅 Promise.race 声称底层终止。新增 generation/drain/quarantine 是恢复租约的必要保护，而非另一通用 Agent 管理器。
- 实际 owner 停用入口 `index.ts:697–744` 先关闭 admission、按 owner 取消，再 drain/dispose 自己的执行；其他 shared owner 和 host 不退出。新 controller 必须连接 exec signal 与实际 owner lifetime；**配置事务释放的另一语义见 R5-W1**，不能只因出现 release 名称就视作同一生命周期。

#### 2. 当前默认、继承、模型能力与公开 DSH 能力

- `product-contracts/src/approval.ts:19–22` 默认 Codex；Node `approval.ts:7–24` 合并 owner/workspace，`configuration.ts:55–77` 再应用逐 Agent `cc→nano` / Codex 或 null 继承，并独立解析审核模型。设计和 delta 没有恢复旧默认 Nano，未改变 CC/DSH 已有继承或免审。
- `classifier.ts:15–29` 与 `codex.ts:100–105,174,196` 已是 low→defaultEffort→first declared effort，未声明能力不强设。设计冻结一次 resolvedEffort，不继承主 Agent effort、不为恢复切模型。当前 lifecycle baseline 测例只显式覆盖 high/default、low 和无可调；first-only 的新增组合仍是 M1 退出条件，未声称原 31 项已覆盖全部 effort 分支。
- 独立读锁定 `dsh-llm` export map 和 public `index.d.ts:16–26,48–71`、`types.d.ts:25–44,141–148`：根 exports 的 `LlmError.failure`、`BlockAssembler`、`isAgentLoopRequest` 和 public `LlmFailure` 足够获取结构化 facts。内部实现文件仅为阅读证据，不授权 runtime private import。
- `dsh-llm-retry/lib/index.js:151–178` 的执行能力是 `agent/request-error` 插件，always/default policy 不等于 action 共享 2 次。原生 loop `lib/index.js:1117–1134` 使用该 waterfall 的最终 action；现 Guardian prepend owner 不调用 next 可结束该次尝试，CC hand-built stream 本来也不走该事件。因此不调用该插件执行本功能是基于真实 seam 的复用判断；provider=always 不叠加仍须 native fixture 反证，不能仅按“listener 名字正确”通过实现门禁。
- public Agent `index.d.ts:48–103,129–145` 提供 creation-only signal、setup/commit 与 dispose；锁定 loop 打包 `1655–1708,1734–1756` 确实先 cancel/whenIdle/scope cleanup 再 detach。可实现 generation 先撤销、late create 只清理、旧资源先 drain 再恢复，无须新 loop/private API。
- `llm/stream` public 事件 this 是 LlmRuntime，不是 Agent；loop 打包 `1269–1276` 用自身 sessionId 标记冻结原对象，public GenerateOptions `types.d.ts:520–530` 区分路由身份与 auxiliary purpose。设计先 marker+精确 reviewer ID 过滤、后访问 currentAttempt 的决定正确；main、CC、disclosure 和 auxiliary 不得被 idle tool reviewer 拦住。
- undici `types/dispatcher.d.ts:207–231` 有 public onResponseStart/handler 生命周期；当前 `llm-attribution.ts:7–41` 已只有一个 dispatcher owner 和 iterator-local ALS。pi-ai `lib/index.js:1402–1452,1684` 的 in-band failure 常只有 code/message，且 SDK maxRetries=0；新增只观察 HTTP facts 有具体需要。设计没有许诺所有 adapter 都能取得 headers；无法取得时 unknown 与本地退避是诚实限制，真实 Anthropic/HTTP fixture 仍待实现。

本 reviewer 另执行**独立、无网络、无文件写入的 public prepared-stream/ALS 探针**，不是粘贴作者输出：以公开 Context/LlmRuntime/LlmAdapter 建内存 adapter，精确 owner registry 先过滤；并发 A/B/main、同 main session 的 hand-built CC、idle auxiliary，再试 idle 自身异常流和 A 的下一 attempt。结果：

```json
{"seen":[["review-A","A1"],["review-B","B1"],["main",null],["main","CC1"],["idle",null],["review-A","A2"]],"ownerReads":["review-A","review-B","idle","review-A"],"ownedIdle":"rejected","exports":["function","function","function","function"],"nativeAgent":false,"http":false,"network":false}
```

`[exit code: 0]`；同时断言对象克隆不保留 public loop marker。该探针只证明公开 prepared-stream 能支持方案所需归属和 ALS，**没有真实 Agent/fork、HTTP header、取消或 dispose，不代替 M1/真实产品验收**。

#### 3. Agent Context Review — Design Review

受影响 Surface：审核模型的 system/policy、有效消息与工具结果投影、planned action、失败结果及恢复/失效；Consumer 为 CC/legacy、tool Guardian，以及需证明不受波及的 disclosure Guardian。未扩到无关 Memory/Skill 全量审查。

- **来源与 owner：** `sources.ts:23–31,69–93,135–185` 以有效 deriveMessages 为输入，去掉快照/Skill 正文、只把仍有效 root 的 PTC 结果投影回来；Inbox 按 message 保留 sender/page/reply/observation，同 call generic body 去重但 distinct call 不删。`approval.ts:59–72` 保存 delegated epoch、仅跨 epoch restore=true；`codex.ts:60` 对已处理 inherited 再用 false 规范化。design L59–65、203–205 正确区分技术恢复冻结、同 epoch 委派和失去观察证明的恢复，没有新 reviewer 就一律 restored 或 live 的错误。
- **当前身份与控制：** `input-source.ts:21–24` 依宿主 actor/channel/message 身份判断真人；`sources.ts:8–10,167–182` 与 `approval-sources.test.ts:187–224` 明确 represented user/pa_agent_id、实际 sent、Task stop/UI resume 与自动提醒不同。设计将它们作为冻结事实而非重试授权，保留“排队旧输入不因处理较晚而盖过 stop”的语义。恢复不得从全库补授权、把 PA observer 或未送达提案变成人类许可。
- **选择与交付时点：** 首次 prepare 冻结规范化 rows、精确 action/参数/受众/schema、配置和能力；各次技术恢复重新 full 但不重读消息库或失败 reviewer 的 assistant/read 残片。新工具调用才取新有效历史；来源失效/换窗与配置 fingerprint 失效原 checkpoint。CC 正文省略/不裁超窗，Codex 既有 full/recovery 与 delta/preserve admission 各自保留。
- **可理解输出：** current `codex-context.ts:10–26` 接受 bare/embedded verdict 与默认值；合法 bare allow 的 format=0、bare deny 是最终判定而非格式恢复。PA parser `personal-security.ts:97–103` 仍必须 decision+非空 reason；不能把 tool 默认值套到 disclosure。design/runbook 的 Before/After 例能区分这些 Consumer。
- **预算与恢复：** `codex-context.ts:87–138` 的 User/ManualApproval 成本、ProtectedAssistant/最近 5 条工具保护、可容纳 optional 选择与 required/action 保护继续由现 admission 拥有。新 controller 只消费其结果，不新增 0.65 缩放、证据摘要器或第二 parser；全 action context rebuild≤1，不靠新 full 重置额度。
- **Validation 闭合：** runbook §5.1/5.2 和 M1 明确 captured 实际请求、同/cross epoch 对照、tool/disclosure 并发、来源/预算/parser 与 stop 组合；请求证明实际交付，Work/副作用/实际 sent 证明消费结果。当前只有设计和窄 baseline，未观察真实模型请求或后续行为，不能从探针/类名推断 LLM 已正确消费。当前 lifecycle 语义歧义仍须 R5-W1 闭环。

#### 4. 全部 17 场景、次数/预算/安全和最终路由

| 首文档场景组 | 设计覆盖与独立判断 |
|---|---|
| 短暂失败后放行；混合失败共享两次 | design L74–84、88–100、118–130：controller 隶属同一个 ToolExecution，最多额外 2 次跨故障/CC stage 共享；只恢复判定，不调用工具体。有效最终 verdict 不进入技术分类。 |
| CC 完整阶段；Codex 完整 90 秒；几分钟但有界 | L104–116：15 秒 prepare，CC 每次 30/60 秒、legacy 30 秒，Guardian 每次 90 秒；等待总≤20 秒，cleanup 单次≤5 秒，360 秒整体保护容纳 Codex 330/CC 265 秒估算。context rebuild 在当前 90 秒内，非所有尝试挤原 90 秒；cleanup 不可用则关闭而非扣残余启动新尝试。 |
| 首次格式恢复；再次格式/总额耗尽 | L124–130：EMPTY_RESPONSE/空白/非法统一 format 子额度≤1，计入总 2；不接受原生通用 transient 再送一套额度。parser 先拥有有效性，不另造字段校验。 |
| CC 两阶段和最终 deny；Codex 风险授权检查；永久错误 | L96–102、124–132：CC 有效非 allow 才正常推进，失败只恢复当前 stage；Guardian 失败 handle 退役后干净 full，另一并发成功 checkpoint 不被覆盖；auth/quota/config 永久优先，不借 429/Retry-After 刷 allow/换模型/扩 inspection 权限。 |
| 请求/退避停止；非主动单次超时 | L92、122、193–197：父取消/owner 撤销优先于 timeout/allow，generation 先失效、iterator/handle 收束，5 秒无法 drain 则 quarantine 且不发后继，late create/allow 不能复活。**真实 configuration reservation release 不是上述 owner 撤销，见 W1。** |
| 普通有人值守；Global/child；unattended allow/deny | 当前 `approval.ts:75–101,138–150` 的 child→return_to_agent、schedule/heartbeat→unattended、Global→return_to_agent 与原 interactive 得到保留。design L156–158、219–221 先记录 no_verdict/拟 route，技术不可用不增 classifier_block；配置 fallback allow 只在终态一次，不冒充模型 allow；cancel 不 fallback 放行。 |
| 内部 attempts 可区分；真实双策略插件旅程 | L209–221 和 runbook §3–6 的 review/attempt/request 三层区分原 callId 与主 Agent 重调，usage partial/unknown 不补 0、不重复统计 fallback；optional domain v1 旧行可读。真实 CC/Codex 自建/安装/两次调用 180/55、用户可见结果与 Work/副作用、独立 Q 和故障证据分层均纳入退出标准。 |

#### 5. Delta、milestone 与验收交接

- canonical target 正确，仅 `docs/specs/gateway/agent-capabilities.md`。独立执行文本断言：MODIFIED 完整保留 **8 个 Scenario**，只把“已有重试”失败 WHEN 改为本次有界恢复语义并加 legacy 兼容 AND；归一化这两处后，与 current 对应 Requirement 逐字相等，`[exit code: 0]`。626 普通工具有效上下文、CC workspace fastpath 和 Codex 风险 Requirement 都在 replacement 之外，没有拿旧整文件覆盖新 main。
- 无新客户端页面/按钮，详细 attempts 不冒称已有 Work UI；既有 observe/domain 导出用于维护者检查，Work 核真实工具/公开结果。没有 prototype 或生产迁移的必要性；不新增 deployment-prompt，不要求生产变更验收。
- 单 M1 囊括同一安全闭环，范围、依赖和 test seams 合理，无按层机械并行冲突；骨架只有空 `.gitkeep`。可替换外部模型用 HTTP fixture，domain/controller fake clock 保次数与时钟，native 层保生命周期，真 IM/daily 观察用户旅程，各证据层不互相冒充。
- 真实资源入口已独立核对 `scripts/e2e-up.sh:113–137,188–215`、current worktree-runtime 的 daily 契约及 `_im_client.py` 的真实登录/配置入口。daily 不和 --main-config 混用；两种策略在自己的隔离副本设置，Auto 开启且不跳权限。runbook 没有宣称模板 Luna 已真实可用，需实际审核 smoke，配置/能力错误与 HTTP/provider 故障分别报告。命令示例有一个低风险补全建议 R5-R1。
- runbook L10、52、65–79 明确**当前还没有**实际 Q 节点、daily 运行身份、625 fixture 命令实物或 trace 导出 CLI。E 必须在工程冻结交接时补真实 branch/ref/SHA/构建、Q 节点、清单身份、策略/fallback/模型/effort、PID/端口、可执行 fixture 及脱敏导出定位，Q 执行前核实。它们是已明确分派的验收前置，不是要求设计 author 现在伪造实现或增加一个审批 Gate。

### Historical issue reassessment

| 原 issue | Author resolution / 当前内容 | 本轮独立核实与状态 |
|---|---|---|
| R1-W1 | 单全局 listener，精确 native reviewer ID + public loop marker；非所属流透明；attempt 快照/idle/tombstone | 重新读取 public 事件/marker、真实 loop stamped identity，执行本轮独立 prepared-stream/ALS 探针；**closed（设计层）**，但 native/HTTP lifecycle 未实现验证，旧 probe 不作本轮产品 pass。 |
| R1-W2 | 原固定 low-only 资源要求已经过时；当前实现会选择原模型支持的 low/default/first | 重读实际 classifier/Codex/Node 选择链；新 runbook 不固定 low 或旧 Sol，不需要为旧 warning 回退新能力。**旧缺陷不适用于当前设计**；真实 daily Luna smoke 仍未知，不把静态能力当真实服务可用。 |
| R3-W1 | 分开同 action 技术恢复、同 epoch 委派、跨 epoch/失去观察证明；冻结 actual observation | 本轮核对 approval epoch、sources restore、codexEntries/cursor 与 §5.2 双向对照；**closed（设计层）**。没有把历史 R4 Approved 当关闭依据。 |

### Issues

#### R5-W1 — 配置事务释放 reservation 不是执行 owner 退役；不得将 `configuration release` 一概作为取消当前审核的边界

- **Severity:** WARNING；**evidence status:** CONFIRMED（设计指令与当前接口语义存在不一致/未消歧）；尚无625实现，后述运行损害是按该指令实施可成立的机制，不宣称已复现产品故障。
- **位置：** `design.md:92` 将“当前 shared-host 中的 Agent disabled、configuration release、service 卸载”并列，要求“均撤销所拥有 action 的 generation、打断退避、cancel/drain”；相邻“配置切换排队不抢改正在执行整轮”与 L189 的配置 fingerprint/租约失效没有说明哪个 release 入口才能终止 action。
- **真实装配证据：** `packages/personal-assistant/src/configuration.ts:65–78` 在 prepare 被拒、persist 抛错及 apply 完成时都会调用 options.release。Node `apps/node/src/main.ts:413–415` 将它转为 **`configuration.release` RPC**。integration `src/index.ts:608` 仅调用 `capabilities.release(agentId, operationId)`；`capability-state.ts:31–32` 只删除相同 operationId 的 reservation，不撤销任何执行 owner 或旧配置。真实配置切换 `index.ts:626–634` 等待该 Agent idle 后才 setConfiguration；真实停用则是 `index.ts:697–744` 的独立 admission/cancel/drain 链。当前 `CodexApproval.release(parentId)` 又是另一个用于缓存的 API，不能与上述 RPC 同名归并。
- **Context Surface / expected：** ToolExecution 的控制/恢复生命周期与最终工具结果。Agent 已在原配置下执行的受审动作，应持续持有本次冻结规则，直到父 exec 主动 cancel、实际 owner 退役或对应审核租约确实被撤销；配置提案被拒/释放预约本身不能变成一次用户 stop。
- **Observed design / failure scenario：** 一个 action 正在等待503恢复，用户尝试撤下当前忙碌工具/Feature，prepare 按现契约拒绝，随后正常发送 configuration.release。若工程按 L92 给此 RPC 绑定“撤销所有该 owner action”，没有配置生效、也没有用户停止指令的审核就被 cancel；同理 metadata-only/失败配置清理不能顺带终止旧 action。即便作者本意仅指内部 reviewer cache 的 release，目前也未标明该区别，且其取消含义不等于当前 release API 的全部语义。
- **Impact：** 正常旧配置工作被无故中断，主 Agent 收到取消/失败并可能再次调用工具，破坏“进行中整轮保留原策略”和本功能减少主 Agent 技术重调的目标。错误地把 transaction reservation 当 runtime ownership，会扩大新增机制职责，不是纯命名偏好。
- **需要 author 闭环：** 明确区分①父 exec/owner disabled/disposed/service teardown 的真正 action 撤销；②配置事务 reservation release（包括 rejected/failed/metadata-only 路径）**不取消**当前 action；③实际配置生效后的 idle cache/fingerprint 失效或内部 reviewer 租约退役的精确范围。给出连接真实入口的规则，不把 cancellation 挂到通用 configuration.release RPC。补一个设计层验收反证：503/backoff 或请求中并行配置 prepare 被拒/事务 release，原 action 继续按冻结配置完成且最多一次工具执行；真实 owner disable/cancel 仍撤销/drain 且另一 owner 不受影响。若 L92 所指是新私有方法，明确其 owner/purpose/parent 与触发条件，不能仅重命名而保留相同混用。

### Recommendations

- **R5-R1（可选、非阻断）— 补全新 runtime 目录创建步骤。** `reviewer-runbook.md:28–30` 给 WT_ROOT 赋全新 `.e2e-feat625-daily-${POLICY}` 后直接传 --wt；当前 `scripts/e2e-up.sh:115` 先 `cd "$2"`，不会创建该目录。E 落实可复跑交接命令时，在已核实的本次隔离路径上显式 mkdir，或说明目录已存在；避免 Q 首次复制示例就遇到目录不存在。这不改变资源隔离或产品设计，不另计 WARNING。

### Validation record, limits and required follow-through

- 本轮成功的 Git 核对、canonical delta/旧报告 hash 断言、public prepared-stream 探针均检查成功；探针/文本断言显式返回 `[exit code: 0]`。最初一次猜测 integration 的直接 node_modules 存在 agent-loop 路径返回不存在，已用 glob 找到锁定 pnpm 实际路径并读取；不把失败查询记作证据。
- Author 所报 3 组 31/31 baseline 与 docs-check：本轮读取其报告及三组测试定义，覆盖 source/parser/admission/缓存 namespace 和部分 effort、当前 bounded inspection。未重复运行，未获得新的独立测试 pass；这些定义/既有结果不能证明新增重试、first-only effort、真实 SIGKILL 卡 FS、HTTP attribution 或完整并发取消矩阵已验证。docs-check 的临时环境通过只作作者文档检查记录，不作本次 CI 或合格全栈 Python 环境证明。
- 本 reviewer 未执行 build/typecheck/全量 CI、HTTP/native fixture、真实模型/IM/daily 插件旅程，未查共享代理健康、未启动服务、未读生产配置或凭据。当前没有本次实现、真实服务可用性或 Q 产品验收结论，均为 **not verified**，不是已通过也不是因此新增设计 finding。
- **需作者闭环：** R5-W1 的精确 lifecycle 语义、真实接口连接与反证退出条件；追加 Author Resolution，不修改本轮原文。修订冻结新 SHA 后续投本 reviewer，按实际 diff 自主选择 closure/delta/full，不重开首审。R5-R1 可在准备可运行交接时处理。
- **工程冻结必须提供而尚未产生：** 本次实际 Q 节点/隔离 daily 阵容、实施 SHA/构建、可跑 fixture 命令与脱敏 observe 导出/locator；随后独立静态/Context Implementation Review、verifier、Q 双策略真实旅程及确定性矩阵和 Ready PR/CI 仍须按原 workflow 执行。不能用本轮静态审查、旧 R4、作者窄 baseline 或 template ready 代替。
- 只向父 Agent 交付；本报告未提交，不授权 merge、生产部署/重启、发布或恢复旧群/任务/会话/证据。

### Author Resolutions — Round 5

- **R5-W1 — accepted。** 本作者重新读取PA `configuration.ts:65–78`、integration `index.ts:599–645,697–744`、`capability-state.ts:31–32`、`agent-config.ts:142–168` 和 `codex.ts:47–53,81–98`：真实事务reservation release只是释放预约，可在拒绝/失败/metadata-only发生；不是exec取消或runtime ownership。旧design把它与owner停用并列确有实质错误，不按“仅换名称”处理。
  - `design.md` 关键决策1分成三种精确入口：父exec/真实owner disable/disposed/service teardown才撤销action；事务RPC只删匹配operation reservation，明确禁止连接新controller取消/currentAttempt/cache失效；idle实际执行配置生效后后继action才比较fingerprint/替换trunk，metadata-only原地revision不修改已冻结快照。
  - 明确私有reviewer租约按owner+parent+purpose+reviewId/attempt定位，只在本attempt失败/timeout/context rebuild、真实取消、idle cache替换或parent/service销毁时退役/drain。原 `CodexApproval.release(parentId)` 保持cache失效：阻止旧trunk回写、只dispose idle handle，不凭同名API取消活动exec；它不是configuration.release RPC。
  - 同步接口/成功commit条件、Context Lifecycle/Validation和M1退出标准，消除“config release不能republish”与笼统“配置变更失效”措辞。保留现有capability admission边界，不新增取消路径，不改变17用户场景/恢复额度/授权或delta。
  - runbook矩阵及§5.2要求请求中与503/backoff中经真实prepare拒绝→PA/Node事务release后，旧action保冻结配置/输入/次数/退避/发布权并最多执行工具一次；native/事务层补persist失败/metadata-only清理；idle真实生效→下一动作换cache；真正owner stop/disable作为相反对照仍撤销/drain且不伤另owner。
- **R5-R1 — accepted（非阻断建议）。** runbook§2在全新WT_ROOT传 `--wt` 前增加打印/核对路径与 `mkdir -p`；不删除旧目录、不启动服务或创建额外worktree。
- 本次只有design/runbook及本报告追加，spec/delta/M1空骨架不变；保留R5 reviewer原文。本author未实施产品代码，未把静态修订记成测试/产品pass。下一步正常提交推送新冻结SHA后，由父P续投同reviewer自主选择closure/delta/full；本节不代替独立门禁。

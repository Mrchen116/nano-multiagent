# PA execution isolation：锁定 DSH 公开能力与实施落点

recorded_at: 2026-10-16
nano_commit: 481467ac16f0eda4561fca5c8230050541600de9
upstream: @deepseek-ai/dsh 及相关包 0.2.1-alpha.1
upstream_commit: npm 元数据未提供 gitHead；以各包 tarball 的 SHA-512 与本仓 pnpm-lock.yaml 一致性锁定
scope: fresh root session、preset/scope、工具执行、提示词/历史注入、配置刷新、workspace/网络/凭据与 child 边界
current_landing: feat-616 设计研究，未实施、未运行 runtime 验证，不构成 Gate 2 Approved

## 结论

**公开 exports 足够实现受限的 fresh root Agent/preset 与确定性工具边界，不需要 fork DSH 或 private import；现有 Nano AgentConfiguration/session.ensure 原样使用则不够。** 应新增宿主确定的 execution profile，把产品身份 agentId 与执行配置身份拆开。external_chat / observation 应是独立 root session，不从 private global fork，不作为普通 child，也不通过改变 PA 的 work_mode 实现。

必须区分两个承诺：

1. **可实现的首版模型能力隔离**：新会话不带 owner 历史；不会装配 owner persona、memory、skills、workspace 插件和指令；仅接收 broker 明确提供的会话/观察数据；模型不能调用文件、网络、代码执行或 child 能力。依赖可信宿主与受审插件，必须通过真实运行不变量测试后才能称已完成。
2. **现有 DSH scope/sandbox 不提供的强环境隔离**：同进程插件仍可执行任意 Node 代码；scope 不是内存、凭据、UID、文件可见性或网络 namespace。原生 sandbox 的政策词汇只有文件副作用。若需求要求即使宿主插件恶意/被攻破也不能接触 owner 资料，必须额外提供独立的受限执行环境及最小凭据/挂载/网络策略，不能把本方案写成已满足。

尤其不能用“toolAllowlist: [] + 空 persona + 新 cwd”作为完整隔离：除了 global 强补工具，DSH base 还全局加载 agent-instructions，能够在工具调用之前直接把 $DSH_HOME/AGENTS.md 写入模型历史。

## 证据边界与复现

只读检查本仓 main；保留已有未跟踪 feat-616 材料，仅新增本文。公开 npm 元数据与 tarball 经 HTTPS 下载到临时目录，未安装依赖、未执行依赖代码、未读取用户秘密、未使用用户电脑。每个已读取 tarball 的计算 SHA-512 同时匹配 npm dist.integrity 与本仓 lockfile。没有 node_modules，未运行测试或启动服务。

核查了 19 个锁定包：scope、tools、system-prompt、agent、agent-loop、agent-preset、agent-preset-registry、api-session-controller、session、persona、workspace、sandbox-policy、sandbox、subagent、base、agent-instructions、fs-observation-policy、ptc-runtime-node、subagent-spawn-in-process。npm 包只带编译 JS/声明而非 src；以下 upstream 行号指相应包的 lib/index.js，类型指 lib/types/*.d.ts。分析 transitive 包不代表允许产品 import 未声明依赖。

关键公开源：

- [dsh-scope 0.2.1-alpha.1 metadata](https://registry.npmjs.org/@deepseek-ai/dsh-scope/0.2.1-alpha.1)
- [dsh-agent 0.2.1-alpha.1 metadata](https://registry.npmjs.org/@deepseek-ai/dsh-agent/0.2.1-alpha.1)
- [dsh-agent-preset-registry tarball](https://registry.npmjs.org/@deepseek-ai/dsh-agent-preset-registry/-/dsh-agent-preset-registry-0.2.1-alpha.1.tgz)
- [dsh-api-session-controller tarball](https://registry.npmjs.org/@deepseek-ai/dsh-api-session-controller/-/dsh-api-session-controller-0.2.1-alpha.1.tgz)
- [dsh-tools tarball](https://registry.npmjs.org/@deepseek-ai/dsh-tools/-/dsh-tools-0.2.1-alpha.1.tgz)
- [dsh-agent-instructions tarball](https://registry.npmjs.org/@deepseek-ai/dsh-agent-instructions/-/dsh-agent-instructions-0.2.1-alpha.1.tgz)
- [dsh-sandbox tarball](https://registry.npmjs.org/@deepseek-ai/dsh-sandbox/-/dsh-sandbox-0.2.1-alpha.1.tgz)

这些精确版本源码证据优先于 upstream master 文档或未锁定网页。核查没有把当前仓测试代码存在等同于本次测试通过。

## 已证实的公开能力

### Fresh session / preset

- @deepseek-ai/dsh-agent 的根 export 公开 AgentRegistry.create/resume、CreateAgentOptions、AgentSetup。create 可以不传 parentAgent、parentSession、seed、isSeeded；setup 在 session/agent 发布及首次 prompt 前完成，失败回滚。类型 index.d.ts:35-103。
- @deepseek-ai/dsh-agent-preset-registry 根 export 公开 register、mount、resolve、inspectCompositions、acquireScope。每次 preset generation 使用独立 createScope(owner, key)；mount 将 Agent 的 scope parent 绑定到这一 generation，而非另一个 Agent。lib/index.js:495-505、654-711。
- @deepseek-ai/dsh-api-session-controller 根 export 的 SessionController.create({sessionId,cwd,agentPreset}) 已走上述 fresh create，没有 parent/seed；同 ID 已存在时会 adopt/resume，并检查 cwd/preset。lib/index.js:414-460、688-711。**因此 fresh 必须使用宿主新生成的 ID；不能允许外部指定一个已存在的 owner session ID。**
- Nano 已在 index.ts:278-297 的 preview 使用单独 preset + agents.create，且 session.ensure 在 515-526 使用公开 SessionController。复用这些公开能力即可，不必新增 Agent loop。
- 原生 subagent spawn 宣称 zero parent context；这只说明不继承消息前缀。Nano 的 agent/created + NativeHistory.configuration 仍为 child 复制父配置，原生 composeFrom 还继承父 preset generation。不能把“spawn 无历史”当作 persona、目录、插件、权限全隔离的证据。

### Tools：有真正执行边界，但需两层

- tools.restrict 对 scope 继承的全局和祖先工具生效，作用于 schemas 与实际 dispatch；自己的 scope-local tools 不受该 restriction 过滤。工具实现 lib/index.js:2939-2984 明确这个例外。
- tools.guard 是公开、单调拒绝的同步校验，位于可扩展 pre-execute waterfall 之后。所有匹配 guard 只能拒绝，不能覆盖另一个 guard 的拒绝；可在 profile/preset scope 安装，适用于其 Agent。lib/index.js:2912-2936、3206-3241。
- run_code 是保留的 PTC transport，位于普通 restriction layers 之外。restricted profile 要**始终** presentAs('native')，而不是只在空 allowlist 时设置，并在 guard 中显式拒绝 run_code。外部只保留 send_message 等一两个工具时，也不能默认留下 PTC。
- 因而推荐“最小展示 allowlist + 固定 ceiling guard + broker 再核权”。只检查 UI 工具列表、依赖 Auto 分类器，或者仅 restrict 都不能替代后两者。

### Prompt / persona

- @deepseek-ai/dsh-persona 根 export 接受 prefix、suffix、complete、includeRuntimeContext。complete persona 最终成为唯一 system section；includeRuntimeContext:false 调用公开 suppressRuntimeContext。system-prompt 在 assemble waterfall 完成后仍执行 complete/suppress 限制，lib/index.js:306-360。
- 这能够屏蔽其他 system sections/runtime context 的最终模型投影；**不会清理已经进入 user/history 的材料，不会阻止全局 listener 先读文件或写入消息，也不会给 tools 加权限**。complete 不是数据防火墙。
- createScope 只隔离注册归属/事件路由；未标 scope 的 listener 仍全局适用。ScopedLayers.merge 从 global layer 开始，再叠加祖先/当前层；fresh root scope 不意味着“不见 global 注册”。

### Sandbox 的实际承诺

- @deepseek-ai/dsh-sandbox-policy 根 export 支持 setSandboxMode(session, mode)，resolve 使用 session.cwd 作为 workspace-write 边界。
- sandbox README 明确：read-only 限制写，workspace-write 限制写入范围；是 same-world confinement。其限制段明确没有 network、process、syscall、device、credential policy。
- @deepseek-ai/dsh-workspace 是目录身份、session 归属与持久记录，不是沙箱。
- 新 cwd 不会自动阻止读取 owner 文件；单独 DSH_HOME 不会清理进程环境；RuntimeClient 当前用 {...process.env,...options.env} 启动，client.ts:47-53。不存在“传空 env 就不继承环境”的能力。
- 首版受限域可通过不暴露任何 read/bash/run_code/plugin/network/child 工具避免模型触达这些能力；不得据此声称进程内不存在凭据或机器上没有私有挂载。

## 当前必须修的四条旁路

### 1. Global 强补与 generic communication

capabilities.ts:53-68 在 mode=global 且 origin 非 subagent 时补入 inbox、conversations、send_message、subagent。external root 也属于非 subagent，空表不能阻断。global-mode.ts 非 global 分支仍注册 conversations 和带 agent_id 的 send_message，不能直接把 mode 改 single_thread 当受限方案。

改为以**可信 execution role** 决定固定工具集合，仅 private global_main 获得旧 global 固定能力。external_chat 的 send_message schema/handler 只接受本 conversation 的对外回复；拒绝 agent_id/message、任意 target、其他 conversation 和内部 child 控制。observation 没有 public send。两者的数据请求/读取从 bounded broker 取得，禁止自己把参数提升为 owner 授权。

### 2. agentId 配置串域

当前 preset key 为 nano:<agentId>:<revision>；ConfigurationScopes.config(agentId) 找同 ID 第一项；setFeatures、restrictSelection、setConfiguration、whenIdle 以 agentId 遍历全部配置及活 Agent。setConfiguration 逐字段删除后 Object.assign(next)，会直接把私人 persona、skillRoots、extensions、workspace 覆写到同 PA 的受限域。features() 还按同 ID 的任意配置启用功能。ModelPolicy.changed、WorkspaceExtensions.tools、cron 等同样按 agentId 聚合。

必须拆开 productAgentId 与 executionProfileId。不要用“伪造另一个 agentId”临时避免污染：产品 bridge、审计、Work、定时任务需要保持真实 PA 身份。持久 session binding 应存 executionProfileId/role/policyRevision/audienceEpoch；preset 插件只按 profile key 取配置，不按 product agentId 取第一项。

Owner 配置更新只能重新**派生**各 profile：模型与公开名字可按明确规则变化，受限 capability ceiling 不随 owner 工具/记忆/插件设置扩宽。已有 profile 配置采用不可变快照，冷恢复也验证 role/audience epoch 与 ceiling。受众撤权不能只更新下一步配置，必须废弃旧受限上下文并用新 session ID 重建合法最小历史。

### 3. Global plugin 与自动 project instructions

- agent-config.ts:76-91 把 extensions.global 通过 mountExtensions(this.host, path) 挂宿主根；受限配置即使省略 extensions，也能收到此前 root plugin 的 prompt/listener/tool 注册。
- DSH base 的 agent-instructions row 全局启用；integration 的 cordis.patch.yml 当前未禁用。upstream agent-instructions lib/index.js:561-578 发现 $DSH_HOME/AGENTS.md 和 cwd root-to-project 指令；1271-1288 在 agent/pre-step 插入 user message。它不是 skill provider，也不要求模型调用 read。
- 所以建议禁用 host 全局 agent-instructions row，将该**公开插件**只装配到有权限的 private/ordinary preset；integration 需新增其精确版本的声明依赖，不能直接 import transitive 包。把 owner global extensions 改为 owner-private capability scope/preset 上的共享贡献，不再向整个 runtime root 注册。多 private preset 的共享策略需独立处理生命周期，不能留一条 root fallback。
- 用 fresh root 配合 skills roots=[]、explicit_allowlist=[]、features 全显式 false、knowledge.enabled=false；不能仅 knowledge.enabled=false，因为 memory prompt 注入主要由 features.memory_curation 决定，features/memory-curation.ts:22-39。
- WorkspaceExtensions.attach 只要 config.workspace 存在就挂该 workspace profile；restricted config 不传 owner workspace，并不能调用 workspace plugin manager。SessionController 所需 cwd 使用宿主新建的空执行目录，不能用 owner workspace；这不是新增用户 workspace 产品对象，也不使目录本身成为读取沙箱。

### 4. 真实 actor / broker / permission fallback

product-bridge.ts:12-27 现在沿 parentSession 找根 binding，只传 agentId/ownerId/sessionId/rootSessionId；global-agent.ts 对 child 仅特判部分工具。这些事实不能证明 external/observation 具有 owner 权限。

bridge 需从不可由模型改写的 binding 附带 role/profile/audience/policy epoch，PA broker 依其持久记录复核。产品工具既做 tool-name allow，又做 operation/target/object/version/attachment 与当前 ACL 检查。外部回当前聊天、观察读当前批次、向 private 侧提交请求必须各自有有限 schema；请求记录和模型总结始终是第三方数据。

现 NanoApproval 把 read、web_search、memory、subagent 视为 safe tools；unattendedFallback 可 allow；普通 root 的 nano-human 输入会走 interactive 审批。因此 restricted role 需宿主固定 approval=never、禁止 skip/fallback 扩权，并独立使用 ceiling guard。外部人的“同意”不能成为 owner approval。普通 private Agent 的既有行为不应被连带更改。

## 推荐接口与改动清单（proposed）

下面是责任明确的接口方向，不宣称已经存在：

```ts
type ExecutionRole = 'private_main' | 'external_chat' | 'observation';
interface ExecutionBinding {
  executionId: string;            // 宿主生成的 session identity
  productAgentId: string;         // 仍是同一个 PA
  ownerId: string;
  profileId: string;              // 不同于 productAgentId
  role: ExecutionRole;
  policyRevision: string;
  audience?: { conversationId: string; epoch: string };
  observationBatchId?: string;
}
// Node 派生，不接收模型提供的任意 capability flags 或 owner workspace。
deriveExecutionProfile(ownerConfig, binding, hostPolicy): ExecutionProfile;
// agent root 绑定受限 preset，不传 parent/seed；恢复时校验完整绑定。
ensureExecution(binding, profile): Promise<ExecutionReceipt>;
```

私密主脑与受限执行的父工作关系应记录为产品因果链接，不写 native parentSession 来继承 private preset。若未来允许受限 child，须单独设计向下取交集的 policy inheritance；首版直接不允许，不复用宽权限父 child 后再尝试降权。

| Owner / 文件 | 必需改动 |
|---|---|
| product-contracts/src/index.ts | 增加执行 role、profile identity、绑定/epoch 与受限输入/产品调用契约；继续不依赖 DSH |
| apps/node/src/configuration.ts | 区分 owner 完整配置与派生受限 profile；不从 runtime(ownerConfig) 浅拷贝私人字段 |
| apps/node/src/main.ts | 初始化/恢复所有 profile；配置更新逐 profile 派生；reverse product.call 交给 scope-aware broker |
| PA routing / global-agent / single-thread / store | 可信选路；独立 external binding 与 observation 入口；私密 global 不接收所有外部原文命令；scope 过期和撤权管理 |
| integration/index.ts | initialize/configuration.apply/session.ensure 增加 profile key；fresh root 建立；恢复验证；外部/观察控制接口拒绝跨域；公开身份不变 |
| integration/agent-config.ts | PresetScope/AgentScope 改按 profile；私人 features、persona、skills、extensions 有明确装配边界；禁止同 agentId 全量覆盖 |
| integration/capabilities.ts | global fixed 工具按 role；受限始终 native presentation；immutable ceiling guard；工具动态变化不扩权 |
| integration/global-mode.ts 或专用 communication 插件 | private global 保留当前契约；external 只绑定当前 conversation；observation 无发送与内部通信 |
| integration/cordis.patch.yml + package.json | 移除全局 agent-instructions，按 private preset 挂公开插件；声明精确依赖。审计其他全局 listener |
| integration/product-bridge.ts + PA broker | 宿主注入 scope identity；按 role/target/revision 再核权；禁止 ownerId 作为全权凭据 |
| integration/history.ts | override/snapshot 记录 profile；拒绝拿 private fork 作为外部执行；history export 只写对应空执行目录 |
| integration/model-policy.ts / knowledge/runtime.ts / workspace-tools.ts / cron-owners.ts | 去掉危险的 agentId 首项/全量联动；模型更新不带能力配置；知识、cron、插件管理限合法 role |
| IM Work/trajectory/attachment ACL | 同一 PA 的 external 可联系性不授予 private Work、其他 session、附件、搜索 snippet 的读取权 |

可在同一官方 DSH process 内实现首版，前提是 owner-specific 自动注入与插件贡献已经从 root 移走，root 仅保留受审的公共运行时服务。这是最小改动且复用现有 stdio 管理的路径。

若不能证明所有 owner root 扩展/监听的注册范围，**不能放行 same-host 隔离**。替代方案是由 integration client 管理独立的 restricted DSH host/profile（依然官方 runtime，不是第二套自研 loop），隔离 DSH_HOME/持久状态/自动发现/环境来源；此举涉及当前“一节点受管执行进程”的架构变更，需明确 SPEC delta。即使另起进程，真实 OS 挂载/网络/凭据隔离仍要额外提供，不能假定自动成立。

## 实施门禁：什么还没有证明

首个 milestone 应先完成公开 API 的 native fixture，不接真实模型/秘密。使用唯一 canary 字符串分别放在 owner 历史、persona、memory、skill 内容、owner/global AGENTS.md、global/workspace prompt/listener；新 external 和 observation 的**实际 LLM request、持久历史、tool result**必须均不包含它们，不能只看 preview。

必须至少覆盖：

1. 新 external root 与 observation root；无 parent/seed；另一个 DM/群不能继承前一会话历史。普通 native spawn 与 fork 用作负面对照。
2. 非空最小 allowlist 时 run_code 仍缺席且实际调用被拒；read/read_image、bash、web_search/web_fetch、plugin_manager、workflow、subagent/subagent_fork、内部 send_message 均实际拒绝；注入 scope-local 工具仍被 ceiling guard 拒绝。
3. owner global extensions 的 prompt 与 agent/pre-step 注入、DSH_HOME/AGENTS.md、cwd ancestor 指令不会进入受限输入；memory feature、自动 knowledge review、cron/heartbeat 不会因同 agentId 重新启用。
4. 同 PA private 和 restricted 同时运行，owner configuration.apply 开启全部工具/skills/插件后，restricted ceiling 不扩宽，private 不被 restricted 空表关闭；包含 in-flight 撤权、cold restart、HMR 与历史 override。
5. 伪造 actorId、profileId、target、owner approval、release receipt、session ID、attachment URL，以及直接调用 product.call 均由 broker 拒绝；不能靠模型“知道不可做”。
6. 群成员/资格/资料授权 epoch 改变时取消或失效旧输出并重建 context；旧 release bytes 不继续通过历史或 export 复活。
7. 私密本人 /stop 与 external /stop、observation 历史命令分离；restricted approval 不弹 owner 卡、不走 unattended allow；模型错误/未知投递不伪报成功。
8. 依赖边界 contract、现 capabilities/global-mode/child/workspace/approval/恢复测试回归；普通 global 固定工具体验保留。

**可下的设计结论**：采用独立 root + profile key + 非 root 私人装配 + ceiling guard/broker，无需等待 DSH 私有能力或 fork。

**尚不能下的交付结论**：该隔离已运行通过、全部宿主插件已审计、不存在注入外泄、同进程或 read-only 已构成强沙箱。真实 native fixture、全局贡献清单、冷恢复/撤权验证仍是必须完成的实施前置。

## R1 补充取证：private egress 强制接缝与源清理的可承诺边界

2026-10-16，仍以 main@481467ac 为源码基线。本轮父任务已安装锁定依赖；本调查仅读取 node_modules 的公开声明/实现，没有运行模型、读取密钥或修改 design/spec/prototype。以下补充不能被第一版的“可下设计结论”省略：该结论覆盖受限域的实现能力，不等于 private 全功能域也自动具备相同隔离。

### A. private egress 不能停在“在 Auto 前再检查”

**确定性接缝确实存在。** 锁定 dsh-tools 的 ToolExecution 具有 registry 创建的不可由 caller 指定的 token，参数在 policy 前物化并 deep-freeze；tools/pre-execute 是异步 waterfall；tools.guard 是同步单调拒绝。实际顺序是 pre-execute → 必要的 ask resolution → guard → tools/execute/body，见 lib/index.js:3214-3272 与公开 types.d.ts 的 ToolExecutionInput/ToolExecution/ToolDispatchExecution。

当前 NanoApproval.review 存在多条 allow：缺 policy 直接 next、顶层 run_code 直接 next、dangerouslySkipPermissions、safeTools、alwaysAllowTools、owner_message、classifier allow，以及 escalate 的 unattendedFallback=allow。仅把一段逻辑加到分类器或 safeTools 之后不够。必须保证 **PA 专属确定性 gate 独立于这些选项，且任何 allow 之后仍受 guard 拒绝**。

建议职责明确地实现一个 Nano-owned PaExecutionGate，挂在 profile/preset 的可信装配层，并让现 NanoApproval 在一切 early allow/分类器调用前执行其 admission：

1. 根据宿主 binding/原生 Agent 身份查 PA principal、role、epoch 和代码侧 effect descriptor。不能从工具参数、工具自报的 safe 标记或模型文本判断 owner 身份。缺 principal/未知 effect 的 PA 调用拒绝。
2. 对需要外发的能力，异步到权威 grant store 核验真实 authenticated owner 所批准的精确 action：recipient/provider、URL/query/body/附件 bytes hash、operation、profile/source policy revision、期限和一次性状态。历史 owner 语句、wake、child 报告与 Auto 输出都不能签发 grant。首版没有长期规则实现时不得假定已有泛化授权。
3. 为此次 native exec.token 建立仅宿主持有的短时 admission record，关联 normalizedArgsHash、principal、grant ID、epoch、operation ID。字符串 callId 本身不够，模型提供 grant_id 也只是引用。同步 guard 只接受匹配本次 token/参数/epoch 的 record；因此 NanoApproval safe/skip/人工 allowed-once/unattended allow 都不能覆盖缺 grant 的拒绝。
4. 受审 tool wrapper/broker 在真正动作入口再次核验并预留/消费对应 operation 的 grant，固定最终目的地与待发字节，不在 grant 之后从未知路径重新读可变内容。必要时用公开 tools/execute wrapper 做统一最后校验，具体网络/文件上传仍由受审实现掌握。pre-execute 完成到实际 body 之间有调度间隔，不能只在 pre-execute 看一次远端状态。
5. 消费许可与外部网络发送不能成为跨互联网数据库事务。明确授权的线性化点：权威 store 接受此次提交/预留之前撤销则拒绝；动作已开始后撤销无法撤回已发字节。超时回执保留 unknown，以同一 operation 查询，不发新操作重复消费。断线拿不到新许可时 fail closed。
6. tools/result 后销毁短时 token admission。原生 child、workflow、knowledge fork 和审核器各带可信 principal/可取交集的权限，不允许普通继承路径重新获得 owner 的全部外发能力。agentless 或非标准旁路不能自动当可信后台任务放行。

monotonic guard 只约束经过 ToolRuntime 的调用。插件 JavaScript 在加载时、listener 中或工具内部直接 fetch/readFile 不会自动经过它。因而 **未知 extension 不能在 PA 私密自动观察域加载；只屏蔽其公开 tool names 仍不够。** 宿主 root 同样必须维持受审代码清单。工具名相同也不证明实现相同，不能让 owner extension shadow 一个已被认为安全的 broker。

#### 首版需要具体收窄的工具类别

| 类别 | 首版可承诺的 enforcement |
|---|---|
| web_search / web_fetch / HTTP / 上传 / 插件外发 | 无精确目的地与 payload grant 时拒绝；仅受审 adapter 可以拿有效 grant 出站。web_search query 和 URL path/query 本身就是披露。web_fetch 的额外 extraction prompt 也会送模型，需区分授权的模型处理与任意外部披露 |
| bash/pwsh、run_code、任意解释器、shell worker、任意 workflow/custom bundle | 在含观察/私料的 PA 执行域默认拒绝，不能只扫描 curl/wget 或批准 command hash。任意代码可动态读取数据、编码并联网，参数 hash 无法穷尽实际外发 payload。若要保留该能力，需另行设计真实无网/文件可见性边界或受审有限动作 broker；当前 DSH file-effect sandbox 不够 |
| read/read_image/glob/grep | 不因名字 safe 就拥有全部路径。允许读取受控、当前有效的 materialized data 和 owner 已批准本地范围；路径需由宿主解析并检查真实文件/来源。要兑现清理后的不可重读，不能保留任意绝对路径读取。read-only sandbox 没有 read deny 能力 |
| memory/skill_manage、本地 write/edit | 非网络外发，但属于会长期保留和再次注入的资料通道。新增 PA provenance 写入口，metadata 由宿主绑定，不让模型伪造来源；禁止通用 memory safe 分支、原始文件写或 shell 修改 PA 记忆/规则/知识根来绕过。无法证明来源的自动派生项不得保留为可用记忆 |
| child/internal send、schedule/workflow | 不允许借再委派、定时运行或旧 parent root 绕过上述 gate。宿主主动的知识维护也必须带同一 policy epoch；普通公司 Agent 的现有权限可保持 |

**设计选择必须明确**：既要 private 主脑持续接触第三方观察，又要它保留无约束 shell/任意插件，并保证“所有非 IM 外发必须精确 grant”，仅靠现 DSH tool hooks 不能同时成立。最小可实现方案是 PA 观察型 private profile 收窄为 brokered tools；将需要通用执行的 owner 明确任务交给另有真实环境边界的执行入口。否则应明确声明尚未实现非 IM 全通道防外泄，而不是将 guard 当作万能沙箱。

### B. 已证实：没有公开的逐源历史擦除 API

进一步检查锁定包的根 exports 与声明：

- SessionPersistence 的公开抽象服务只有 create/open/flush/stat/list；SessionHandle 提供 append/read/flush/close。文档明确 append-only，events never rewritten。没有 source delete、session purge、redact。JSONL 的 truncateTornTail 用于修复 torn physical tail，不是删除已提交历史的可用接口。
- Session 的 deriveMessages 可通过 surface replacement/compaction 不再包含某些旧节点，但 snapshotEvents 和持久原日志仍保留它们。SessionQuery.readSession/readEvent/observeSession 可读完整 raw log。compaction 是上下文投影变更，不能当删除证明。
- AgentHandle.dispose 停止 loop、等待退出、卸载 scope 并从 live store 移除 session；不删除持久日志。SessionController.create 复用已有 ID 时会 resume，故仅“重新 ensure”会恢复旧资料。workspaceRegistry.delete 的对象是 workspace 记录，不是其目录或 session body。
- 公共 subagents.drainContinuableDescendants(parents) 可以关 admission、停止并等待 continuable descendants 释放 handles；interrupt 只取消当轮且保留队列/descendants，不能当 purge。one-shot run 仍需由其持有者 abort + await result/dispose。Agent.cancel 不传 keepInbox 才清掉排队输入；现 Nano session.cancel 特意传 keepInbox:true，是正常停止语义，不适合撤源清理。
- session/api 的 archive、隐藏或关闭 UI 不能替代物理擦除。没有查到覆盖原生日志、派生索引、附件、spill、审核轨迹的全局删除原语。不能通过直接编辑 DSH 内部 JSONL 格式伪造受支持的生命周期。

公开参考：[SessionPersistence 精确版本](https://registry.npmjs.org/@deepseek-ai/dsh-session-persistence/0.2.1-alpha.1)、[SessionQuery 精确版本](https://registry.npmjs.org/@deepseek-ai/dsh-session-query/0.2.1-alpha.1)、[fs-sandbox 精确版本](https://registry.npmjs.org/@deepseek-ai/dsh-fs-sandbox/0.2.1-alpha.1)。本轮读取的是已安装对应锁定包的公开声明/实现。

### C. 当前资料的残留不止主 session

1. NativeHistory.writeExport（history.ts:267-318）把完整 events 写入 DSH_HOME/exports，还把可读 user/assistant 正文写入 cwd/.nanoassistant/chat_history。recoverExports 可以从 native log 重新产生已删除的导出。只删一个 cache 会复活。
2. memory/skills：KnowledgeFiles.memory 只记 source.session_id 与 timestamp，没有 source conversation/object/version；Skill usage 保存 session_refs。KnowledgeRuntime.batchHistory 会按 usage refs 用 sessionQuery 读旧正文再交给 fork review。当前数据不能准确逐源反向删除所有衍生事实。
3. MemoryCuration 还在 WeakMap 中保存 memory prompt snapshot，通常直到 compaction 才刷新；只改磁盘 MEMORY.md 不立即清掉当前模型输入。
4. NanoApproval 的 delegated 表保存从 parent 复制的审核历史；CodexApproval 还有独立 reviewer session、checkpoint、fork 与 trunk cache，未必出现在 private root 的普通 subagent lineage。release(sessionId) 可丢 in-memory cache，但不擦除原生 reviewer 日志；在途 reviewer 也必须因撤权 abort 并等待收口。
5. codex-inspection.ts 的 guardian_read/stat/list 用 resolve(cwd, suppliedPath)，允许绝对路径；它限制 regular file/大小/阻塞，并未做 private source revocation ACL。清理不能漏掉审核器的本地读取能力。
6. 原生 fs-sandbox 的实现注释明确 reads pass through untouched；模式只约束 mutations。即使 fresh private session + read-only，read/bash 或具备文件权限的插件仍可重读旧 exports、memory、skills、native logs、工作产物。新 cwd 也不改变绝对路径可读性。

### D. 推荐最小且可验收的清理语义

应把三类动作分开，不用一个“清理完成”覆盖全部：

**排除来源**：从提交的新 policy revision 起停止该来源的新摄取/历史回溯，撤销未执行候选和受影响 release/grant。它默认不等于删除已经保留的工作记录，也不撤销别人收到的消息。UI 必须直说这一点。

**从后续 PA 执行中移除受影响资料**：这是可以设计实现的逻辑撤销，需要持久 retirement/tombstone 与完整数据依赖清单，而非只重装 prompt：

- 先提升 epoch、封闭受影响输入/工具/LLM request/最终发送入口；标记 cleaning/incomplete，不能在 drain 前报告完成。
- 根据 source→execution/derived record 依赖找出污染集合。对当前无细粒度 provenance 的 private history/child/审核器/记忆，采用**整 session/整未知派生集合退休**；不要尝试用模型总结证明已过滤干净。
- abort 并等待 root、continuable forest、one-shot、workflow、知识维护、审核器、定时与相关网络操作退出；不用现 keepInbox:true 的 session.cancel。已经发出的模型/外部请求不可召回。
- 持久退休旧 session IDs、阻止旧 queued work/child continuation、源 backfill、history/export recovery、knowledge batchHistory、Work/attachment read 将它们重新交给模型；重启前先加载 tombstone，所有 resume/ensure/fork/child 恢复途径都查它。
- 清除可定位的 Nano 自有 source cache、candidate、release bytes 与 provenance 记忆，并等待写入/导出队列排空；没有来源元数据的内容保守隔离或重建。用户亲写文件不能凭猜测删除。
- 用新 ID、无 parent/seed 的 fresh root 重建，只输入当前有效的 owner 明确资料和剩余来源。不要把旧主脑总结当新初始上下文；记忆 snapshot 与审核缓存同时失效。
- 后续 PA 的文件读取只走有 provenance 的 broker/明确受控根；禁止 generic read、shell、guardian inspection、插件读取隔离区。否则“下次不再读取”无法成立，即便普通检索 API 已过滤。

这里退休的原生日志可作为 owner-only 历史残留保留，但必须与**可重新进入模型的执行资料**分开。由于原生 storage 本身仍在同机可读，此语义依赖 trusted host 和无旁路工具，不能称 OS 级不可访问。

**完全删除本地及远端全部副本**：当前不可承诺。没有统一公开 DSH purge 原语，也缺任意文件/派生 memory 的完整 provenance；模型服务、接收者、备份和已经导出的文件不能倒退撤回。若未来提供物理擦除，需独立支持的 persistence/attachment/index cleanup 接口和删除回执、停机/恢复纪律及明确备份范围，不能在本 unit 通过私改 native logs 临时补齐。

建议将过强契约替换为：

> 排除来源后停止继续观察，并使该来源的未执行建议与资料授权失效。选择清理执行资料时，PA 停止受影响工作、重建后续上下文，并移除可定位的 PA 管理缓存与派生记忆；无法精确定位的派生内容会隔离或整体重建。只有这些步骤完成才显示完成。既有执行日志及用户自行保存的文件可能仍保留，已发送给模型服务或接收者的内容无法撤回；本功能不宣称完全擦除全部副本。

若产品坚持“清理后旧资料不能再进入任何 PA 推理”，则上述读取 broker、持久 tombstone、所有执行/审核/知识派生路径的 revocation 是本 unit 的必做范围；若仍保留 unrestricted private read/shell，必须撤下这一保证，而非只调整措辞隐藏缺口。

### E. 新增针对性验收证据

- 同一 PA 外发依次命中 safeTools、alwaysAllowTools、dangerouslySkipPermissions、classifier allow、人工 allowed-once、unattendedFallback allow，缺 grant 时全部由最终 guard/broker 拒绝。未知自建工具、同名 shadow、child、PTC nested 调用不扩权。
- grant 只能匹配原生 execution token + 精确参数/字节/目的地；并发消费、过期、revoke-before-commit、断线和 unknown 回执均不产生未经授权的新网络请求。使用受控假网络 endpoint，不能用真实秘密验证。
- 在主会话、child fork、knowledge review、Codex reviewer、MEMORY/USER、skill usage、双份 exports 中植入不同 canary；撤源后检查实际 LLM request、cold restart、旧 session ensure/fork、batchHistory、history recoverExports、guardian read 与普通文件工具。
- 分别断言：新来源停止、旧执行被退休、后续上下文无 canary、Nano 指定缓存删除、native logs 仍保留且不会被 PA 工具读入。不能把最后一项写成“物理删除通过”。清理中断/进程重启保持 cleaning 或 incomplete，不能静默恢复旧上下文。

### F. 功能代价与 owner 批准的独立执行：PA 仍然能推进工作

限制自动观察域的任意 shell/网络，不等于只能聊天。private 主脑仍可通过有 provenance 的产品读取完成任务/依赖核对、资料归纳、准备具体回复、方案与文件内容、请求限定资料，以及通过经批准的 broker 写回 task/交付结果。区别是“任务规划和资料准备”不自动授予“任意本机代码能访问全部私料并联网”。

需要通用代码、安装、构建或专业工具时，推荐将 PA 产出的**具体执行候选**交 owner 批准，宿主建立 independent task root；仍由同一个 PA 汇报进展。原生 private parent/seed 不传过去，专业 Agent 不因名字/所属 owner 自动继承批准。task_graph 保持任务真相，grant 只引用 graph/node/revision 和执行操作，不另立任务状态库。

最小授权载荷可使用下列字段；每项都必须有宿主兑现或明确不可用的结果，而不能只在 prompt 中描述：

```ts
interface IndependentExecutionGrant {
  id: string;
  ownerActorId: string;        // 服务端认证写入，模型不能指定
  candidateHash: string;      // 本人所确认的任务、输入与权限的不可变快照
  taskRef?: { graphId: string; nodeId: string; revision: number };
  assigneeAgentId: string;    // 明确批准的专业执行者，产品身份保持真实
  executorProfileId: string;
  environmentId: string;     // 实际执行环境及其能力版本，由宿主解析
  environmentPolicyRevision: string;
  inputs: Array<{ objectId: string; version: string; bytesHash: string }>;
  allowedActions: string[];   // 受审 broker 操作，或明确的代码执行工作范围
  readMounts: string[];        // canonical capability IDs，不是模型随填的路径
  writeMounts: string[];
  networkPolicyId: string;    // 默认无网络；需要外发时仍用有独立 grant 的 broker
  credentialCapabilityIds: string[]; // 默认空；不把原始秘密放在任务 prompt
  resultAudience: 'owner';    // 进一步对外发送需单独授权/资料放行
  maxRuns: number;
  expiresAt: string;
  sourcePolicyEpoch: string;
  operationId: string;        // 重试/未知回执复用，不重复消费
}
```

输入应是 owner 批准的最小 materialized 文件/文字，而不是 private 全历史、memory 目录、owner HOME、DSH_HOME、全部 provider credentials 或整个个人 workspace。即使对象名不变，bytesHash/版本变了也不能沿用旧授权。专业执行者的结果以带 provenance 的数据返回；其“主人已同意下一步”不是新的 grant。需要发布、发送、扩大输入、联网或再委派时另核授权，不能扩大原候选。

**最小落地次序**：

1. 已有受审结构化工具可执行的任务，先做 independent fresh root + finite broker capability，公开 AgentRegistry.create/setup 与 preset/guard 足够支撑这一条。
2. 真正需要任意 shell 的任务，只有在环境已经证明不挂 owner 私料/历史、环境变量最小化、文件可见性受控、网络默认为 deny 或仅受审 broker 可出站时，才能仍沿用 PA 的强披露保证。当前本仓 RuntimeClient 和原生 file-effect sandbox **没有证明这些能力**；这是一项部署/执行能力前置，不能写成已经可用。
3. 若暂时只有普通宽权限 specialist，可交付详细执行候选、材料与准备结果，让 owner 明确选择在其普通环境运行。该确认应说明它具有哪些 workspace/网络访问，属于 owner 批准的普通执行权限；不得在后台自动升级，也不得把此分支宣传为“只读批准输入、非结构化 shell 完美信息流隔离”。如果当前产品契约不允许这一较弱保证，保持 prepared/blocked，而不是偷换执行域。

公开扩展接缝可支撑未来受限 executor：@deepseek-ai/dsh-fs 根 export 的 FileSystem 抽象服务、@deepseek-ai/dsh-subprocess 的 SubprocessRuntime、@deepseek-ai/dsh-ptc-runtime 的 resolve/run 与 @deepseek-ai/dsh-subagent.registerProvider。DSH sandbox README 要求远端/独立世界同时替换一致的 fs/subprocess/shell 能力。**存在这些接口不等于已有满足 Nano 部署要求的安全 provider**；新增 import 仍须声明精确依赖，不能 private import，也不能只换一个 shell 而让 read/插件继续访问宿主。

残余风险必须保留：批准输入本身可能含恶意指令；任意执行结果可能错误或恶意；被批准的代码仍可能破坏其获写权限的目录；开始后的外发不能撤回；同进程受信插件/宿主失陷不在 tools.guard 的保护范围。明确的任务授权降低歧义，不会把不受控代码变成确定性数据流证明。

# feat-770: 普通执行 Agent 与 Dreaming 整合默认 PTC — 技术方案

> 对齐：[spec.md](spec.md)。状态：设计提案；本轮不实施、不切生产。运行时代码基线 `be23e8fc7`；本次文档修订基于 `3e77928a0`，DSH 锁定版本 `0.2.1-alpha.1`。

## Changelog

## 现状分析

### 涉及范围

- `packages/dsh-integration/src/agent-config.ts`、`child-role.ts`、`capabilities.ts`：配置、角色和实际工具选择。普通子会话、Global 一级 worker、二级 subagent 与 worker fork 已有宿主判定，不能靠模型声明或 session ID 前缀识别。
- `src/policy/approval.ts`、`review-session.ts`、`sources.ts`（均相对 integration 包）：现有 Auto、人工审批和证据链；最外层 run_code 当前免 Nano 审核，子调用仍被审核。Codex 工具/披露审核器固定 native；CC/DSH 分类及 PA 输入审核为无工具 LLM 调用。
- `src/knowledge/memory-sources.ts`、`memory-source-view.ts`、`memory-trajectory.ts`、`dreaming-history.ts`：第一层 child 原始经历、root 材料、冻结批次与回查。目前普通事件处理未覆盖 PTC 子调用事件；公开 `createHistoryView` 的条目不能假定包含子调用。
- `src/knowledge/dreaming-agent.ts`、`dreaming-prompts.ts`：两阶段当前均固定 native；整合已有文件/Bash/source_history，提炼只有上下文恢复工具。维护会话无 Nano preset，不经普通业务 `ConfigurationScopes.attachAgent`/NanoApproval 装配，使用自己的 scope guard 与部署 sandbox。
- `apps/node/src/configuration.ts` 和 `packages/product-contracts/src/configuration.ts`：现有 features 字典已进入 canonical 配置、fingerprint、保存和 runtime 传递；本期复用，不增加第二套配置存储。

### 既有约束

仅通过 DSH 公开 exports 接入；不 fork/patch runtime、不新增 Agent Loop。只改本 unit 文件进行设计；实施期遵循原有 workspace、权限、生命周期与隔离规范。使用当前能力契约、Global 交付、个人来源与记忆契约，不用旧研究替代 current。

DSH base 已挂载 Node PTC runtime；工具模式默认 native，支持按 scope `presentAs(native|ptc|both)`。Node 每次新进程，允许直接 Node API，使用 session sandbox；没有持久变量、yield/wait。Auto preset 是 danger-full-access。两者组合意味着外层免审不能继续保留。

事实依据：当前 `cordis.patch.yml`、`src/client.ts`、上述 integration 文件，以及主 checkout 已安装版本的 `dsh-tools`、`dsh-ptc-runtime-node`、`dsh-permission-presets` 公开包。设计 worktree 未安装运行依赖；安装包结论由与本 worktree lock 相同的版本核对，不把参考仓旧 HEAD 当当前依赖。

### 可复用能力

| 能力 | 处理 | 原因 |
|---|---|---|
| DSH tools.presentAs 与 run_code | 用 | 运行时已有 SDK 生成、子调用派发、错误和取消，不另造 transport |
| DSH Node runtime | 用 | 首期复用；把程序作为实际代码执行审核，不新建 V8/QuickJS provider |
| ToolSelection | 改 | 统一决定业务可见工具与最终模式，避免同一 scope 重复 presentAs |
| NanoApproval / ReviewSession | 改 / 用 | 补外层程序审核；保留子调用、native 审核器和故障分流 |
| ApprovalSources 的 PTC 关联 | 用 | 保留原始 call ID 与有效历史边界，不把程序输出当唯一授权证据 |
| MemorySources / source_history | 改 | 补子调用的配对、批次材料与受限原文回查 |
| features 字典、空闲应用和恢复配置 | 用 | 增加一个显式 native 回退值，沿用配置持久化与恢复 |
| Workflow PTC | 不改 | 独立 runtime consumer，不是本期模型展示切换入口 |

### 相关历史

- `feat-676` 与后续 `bugfix-767` 等当前记忆/恢复实现影响本期依据读取；最终以基础 commit 的代码和 current spec 为准。
- 前轮调研在旧本地 `47aa2c179` 上看到按聊天来源过滤经历的代码；最新基线已规定“已记录的执行轨迹不按会话来源删改”。本设计修正为：保留原始执行经历；实时 IM 补查仍执行当前来源权限，generation 变化仍中止旧批次。
- `bugfix-767` 的恢复与模型路由成果继续适用，不因 PTC 引入新的整体重放机制。
- Codex 当前对话暴露代码编排与持久 CUA REPL，不能推出所有 Codex Agent 默认 PTC。官方机制参考只说明可能收益：[PTC](https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling)、[Computer Use](https://developers.openai.com/api/docs/guides/tools-computer-use)；本方案不依赖 Codex 私有行为。

## 架构总览

保持一条 DSH Agent Loop：按角色默认选择普通执行会话 → 同一工具选择器生成 SDK 和 run_code → 整段程序经 Nano 审核 → DSH Node runtime 执行 → 工具 bindings 继续经原权限与产品边界 → 返回精简结果。Dreaming 整合在自己的维护 scope 装配相同 PTC 展示，保留现有维护权限链。原始 PTC 子调用事件分别供审核和受控经历读取消费；不把全量中间结果重新塞回执行模型。

## 关键决策

### 1. 范围内默认 PTC，仅在配置文件保留 native 回退

复用 owner Agent 的 `features.ptc_execution`：缺失或 `true` 表示普通执行及 Dreaming 整合默认 PTC，显式 `false` 改回 native。不增加第二个开关、不新增顶层配置字段或数据库迁移，不在 IM 网页增加选项。已有布尔 features 经可信节点配置、canonical、fingerprint、配置 operation 和恢复配置传递；partial edit 保留未修改的值，尤其不能丢掉显式 false。生产更新仍需另行授权。

模式由可信角色和实际工具集决定，不用 owner 标志把全部关联会话一并切换：

| 会话 | 缺失/true | 显式 false |
|---|---|---|
| 非 personal、非 global 的普通独立 root | 满足下述资格则 ptc | native |
| 非 fork 的普通业务 child、Global/PA 一级 worker、其二级普通 subagent | 满足资格则 ptc | native |
| Dreaming 整合（包括 Global/PA 的记忆整合） | ptc | native |
| Global/PA 主会话、Dreaming 提炼、审核器、配置检查专用实例 | 保持既有 native/无工具路径 | 同左 |
| Workflow 的 modelRouteFrozen 执行 | 保持现有路径 | 同左 |
| fork | 继承来源会话的实际展示模式与权限 | 继承来源会话；显式新配置回退按安全边界应用 |

普通执行资格：已取得有效业务配置且处在普通业务生命周期，实际工具 view 中存在可执行 bash。不得仅检查 owner 的 allowlist，因为 Global worker 有独立工具集合。没有 bash 的受限会话保持 native，空工具选择维持已有行为；不通过新增 run_code 获得原来未开放的通用执行能力。Dreaming 整合已有独立 Bash，由维护 setup 判定，不套普通业务资格。bash 可见不等于免审。

fork 创建/恢复延续来源模式，不因默认值变化重写继承前缀。已有会话按当前配置恢复契约读取持久值；旧配置缺失新字段时，普通非 fork 会话在首次安全装配采用 PTC。仍存活或恢复的历史 native 来源 fork 保持 native，直到明确的新配置更新；该次更新可以改变后续请求前缀，不能声称仍与原 fork 前缀相同。定向覆盖默认切换、历史 fork 与恢复。

`both` 仅作为隔离诊断对照，不是长期配置选项。native 是对照和配置回退，ptc 是范围内默认；不因模型一次语法错误静默转 native。

### 2. 复用 Node runtime，整段程序先审核，子调用继续审核

对接入 NanoApproval 的普通业务会话，移除 Nano 对顶层 run_code 的无条件免审。外层按与通用代码执行相称的权限路径处理：完整 description、code、timeout/sandbox 请求、cwd、运行时实际能力与上下文交给当前审核策略。说明 Node API 可以产生直接文件、网络和进程效果，不能把它称为纯编排。不得给整个 run_code 套用 native write/edit 的免审核规则，也不允许 alwaysAllowTools 对 run_code 成为新的隐式免审；显式 dangerouslySkipPermissions 保留原用户选择。

- Auto 开启：Codex、CC、DSH 三种现有策略分别评估完整程序；审核器自己始终 native/无工具。明确 raw Node 效果与 bindings 效果的区别，禁止把外层批准解释成任意后续目标的授权。
- Auto 关闭：普通 root 走现有人工审批；后台/child 按既有无人值守和禁止交互规则处理。即使只读批处理也可能增加一次审批，这是首期 Node 执行方案的代价，纳入效率比较。
- 外层获准后，bindings 的每个实际参数继续进入已有子调用审核/来源/角色限制；read 等现有安全工具仍可走原有豁免。拒绝、上下文变化或取消不能被外层批准覆盖。
- raw Node 使用的是与原 bash 相同的 OS 权限和审核模型信任边界；本期不声称建立逐个 syscall 的确定性沙箱，不以静态语法检查声称代码纯净。把数据驱动脚本的未知实际效果如实交给审核策略；危险的动态执行不能以“只调用 bindings”文案免审。
- `run_code` 默认总超时包括内部审核/工具等待。遵循 DSH schema 允许的 timeout，不扩大默认 deadline、不自动重放程序；明确已完成副作用不可回滚。

不选择“新建只允许 bindings 的隔离 runtime”：其安全与生命周期是独立实现工作，首期无须扩展。若实测外层审核开销抵消收益，如实报告并提供配置文件 native 回退；不擅自推翻用户确定的 PTC 默认，也不在本期添加双 runtime 路由。

### 3. SDK 和原始证据分工，不能混淆摘要与原始结果

执行模型看到 DSH 生成的工具声明及 run_code，只收到程序主动输出、返回值和 DSH 原生附加图片上下文。引导并行独立读取、在代码中筛选结构化结果；需要语义判断的内容返回模型，不要求模型在 JavaScript 中模拟理解。失败不得用空数组替代；最后应带任务所需的出处、结果和缺失。

审核继续通过 ApprovalSources 消费持久子调用事件；恢复时只纳入原生有效历史保留的外层调用，遵守压缩边界。不要为审核“省 token”删掉其必要授权原文。

Dreaming 的输入必须包含宿主记录的 PTC 调用与结果，不能从 code 文本或最终汇总推断哪个调用真的执行。按 `rootCallId`、`parentCallId`、`subCallId` 精确关联，不解析 ID 字符串格式。outer 输出仍是程序输出；每条 inner 记录保留原始 seq/time、工具名、参数、结果、isError。只接纳属于同一可信执行会话和冻结范围的事件。

普通结果沿用现有有界摘要/按需回查；IM/交付等需要完整证据的类型遵循已有材料规则。保留 PTC 子调用来源元信息，不假造原生 history 的 item_id，不把运行代码中出现的 ID 当宿主来源。已执行历史不按当前聊天来源删改；实时 conversations 工具仍独立校验当前权限。

### 4. 失败和回退使用已有生命周期

模式应用与 tools restriction 作为同一次空闲配置更新完成；catalog/preview 必须与实际可调用表面一致。模型 fallback 和恢复沿用当前配置/冻结路由规则，不把模型换了当成自动降级 native 的理由。

程序失败、超时、取消后不自动重跑；后续模型收到原生失败及可用输出，由它核对已完成效果后决定下一步。runtime 无跨调用内存、重启无代码续点；没有明确完成回执的副作用标 unknown，不制造事务回滚语义。

显式设置 false 在普通业务会话空闲边界生效，已开始程序正常完成或按用户取消；删除新增模式层的 disposer 后显式恢复该会话应有的 native/default 表面。不删除原会话、记忆、文件或日志；有历史 PTC 的普通会话仍保留只读 ptc_history 恢复入口。会话热更新/进程恢复均测试，不改生产现场。

## 接口与数据流

### 配置和工具装配

1. 既有 canonical features → fingerprint/配置 operation → Node runtime configuration，原字段与身份不变。
2. `ConfigurationScopes` 只对已经附着业务配置的执行会话提供模式意图；Dreaming 整合由独立 setup 使用同一个 owner 配置值；其他内部维护/审核不因 parentAgent 或 origin=subagent 被错误归类。沿已有 attach lifecycle 显式区分检查实例。
3. `ToolSelection.refresh` 先解析实际业务工具和 scope，再决定模式。收敛现有 empty-allowlist 的 native disposer 与新增模式 disposer，由同一 owner 每 scope 声明一次；底层工具 catalog 使用 registry schemas，不用 ptc collapse 后的 wire schema 反推工具集合。
4. fork 在创建与恢复时取可信来源会话的有效模式；保持其权限、继承消息和 tool prefix。与 workspace extension 已声明的同 scope 模式冲突时在配置阶段报明确错误，保留原可用配置，不能静默覆盖第三方模式或让下一次 LLM 请求才失败。
5. 诊断只记录 配置值（含缺失）、effective mode、角色/资格原因和配置 revision；不把这些内部字段塞进用户聊天。能力预览使用生产相同判定，不另复制选择逻辑。

### 执行模型的 PTC 原始回查

新增 scope-local 只读工具 `ptc_history`，普通执行与 Dreaming 整合复用，与 Dreaming 的 source_history 共用事件关联/分页 helper，但使用独立的调用者范围解析。它是持久执行记录的恢复入口，不运行原程序、不查询当前外部世界。不会用 bash 读整份运行日志替代授权检查。

- `action: list`：可选 `root_call_id`、`cursor`、`limit`，默认按最新在前列出当前 scope 的外层调用及已记录子调用，返回宿主认证的 root/sub IDs、工具名、seq/time、完成/错误/缺失状态。调用者不必记住失败程序的 ID；无 root ID 可发现最近失败的调用。单页上限 100。
- `action: read`：必需 `sub_call_id`，可选 `offset_chars`、`limit_chars`；返回宿主原始调用与结果的确定性文本及 Unicode 续读位置，上限 20,000 字。真实记录存在时恢复真实回执；确实无结果才返回 unknown，不推断未执行。IDs 来自 list 返回，不要求模型拆解字符串。
- 工具不接受任意 session_id。默认只读自身 session 的持久事件；fork 可读当前 session 中实际继承的原始事件，但不能据 parentSession 自动读取父会话后续或其他会话。若 seed 没有携带某子调用原件，则明确 inherited_result_unavailable，不伪造证据、不自动扩展父会话范围。自己的历史在换窗后仍可分页读取；不会把原始证据自动注入主上下文。
- 在普通会话首次启用 PTC 前注册；恢复时若有效模式为 PTC 或本 session（含实际继承部分）含历史 run_code，则重新挂载。配置回退后仍保留此只读入口用于旧记录恢复，执行表面恢复 native。没有 PTC 历史且未启用的会话不添加工具。Dreaming 整合只注册维护自身事件回查；提炼/审核器不注册，保持既有 schema。
- ToolSelection 对已挂载的此恢复工具保留可见性，不让业务 allowlist 阻断自身历史回查；不修改通用 contextTools 集合，避免向提炼/审核等内部角色自动扩散。普通执行的 NanoApproval、整合的维护 guard 分别按内部只读恢复处理，scope-local guard 限制到调用者实际执行记录；无命令/网络/写入能力。fork 工具声明仍沿来源继承；native→PTC、关闭和恢复等明确配置变化按已有安全边界处理。
- 最小提示放在执行者现有 Context 指导中：程序失败、取消或用户追问被省略的依据时，先用 ptc_history 的 list/read 取原始子回执，再决定后续动作；它与 history（恢复模型对话）、source_history（维护阶段读取指定业务来源）用途不同。提示与工具一起恢复，不要求记住跨窗口 JS 变量。

本工具开放的是实际执行记录，不保证 raw Node 的每个系统操作都有子调用回执；直接 Node 效果仍须核对真实产物，没有决定性证据保持 unknown。M1 必须覆盖“bindings 子调用写入成功，outer 在输出前失败 → 换窗/重启 → list/read 取到已有回执 → 不重复写入”，以及用户追问被筛掉的查询原文。fork 未继承原件的 unavailable 分支单独验证，不称为成功恢复。

### 子调用经历和 source_history

在 integration 的 knowledge 内提取一个窄的 PTC 事件关联 helper，给 batch material 与 source_history 共用；不复制 DSH session 存储或创建第二份全量日志。ApprovalSources 原有投影语义不同，不为统一形式改写其有效上下文语义。

`qualifiedEvents` 保留合格的 PTC 原始事件，`safeBoundary` 和 batch 游标考虑 outer/inner 配对；未闭合子调用不被呈现为完成。outer 完成前的子事件不能让批次越过尚未安全结束的 step。替换型事件仍按当前原生规则处理。

扩展已有 `source_history` 两个有界 action，而不修改外部 dsh-agent-context：

- `list_tool_calls(session_id, root_call_id?, cursor?, limit?)`：在 `resolveScope` 的冻结 cut 内列出已观察 PTC 子调用；返回工具名、root/parent/sub call ID、seq/time、状态和可用的原生 outer history locator。单页上限沿用 100，cursor 绑定 scope、generation 与查询条件。
- `read_tool_call(session_id, sub_call_id, offset_chars?, limit_chars?)`：读取匹配调用及结果的确定性文本（按事件顺序），沿用 Unicode 字符偏移和 20,000 字上限；返回下一偏移/总长与原始身份。缺失结果返回未完成/不可用，不将 code 文本当执行事实。查询前后均检查 generation；先截断可信会话/时间范围，再检索分页。

批次中大的 inner 结果提供 `{session_id, sub_call_id}` 及具体 action 回查说明，不能给一个不含原始子结果的 outer item_id 当替代定位。新 action 只向本来拥有 source_history 的阶段开放；extraction 继续消费完整有界原始经历并用自己的 history 恢复输入，不额外给它业务回查权。旧 native 条目的 window/item ID 及 read 行为不变。

普通 ptc_history、根批次和 child 提炼复用原始关联规则，但各自保留独立范围检查。根批次和 child 提炼两条材料路径都使用以上记录规则，覆盖第一层 child 的原始经历以及受控展开的后代。缺少可信事件时保持原文可得范围和 unknown 状态，不补造历史、不批量回填旧 summary。

### Dreaming 仅整合阶段切换

在 `runDreamingAgent` 的 setup 中按可信 `run.stage` 分支：提炼继续 `presentAs('native')`，工具集、输入选材、提炼 prompt 与最终 JSON 契约不变。整合读取 owner 的 `features.ptc_execution !== false` 后声明 ptc/native；阶段模式在本批创建时固定，不在程序执行中改模式。配置更新用于下一整合批次，已有取消及来源失效仍立即生效。

整合保留底层文件/Bash/source_history/conversations 和上下文恢复工具，复用 `ptc_history` 查询本维护会话的原始子回执，不让它访问业务会话。业务轨迹仍只通过已有 source_history 的冻结来源目录回查。不新增轨迹分析服务、不改变提炼的“材料入上下文再阅读”路径。

现有 `system-prompt/assemble` 同时按 section 和工具名过滤；实施时必须区分底层业务集合与最终展示表面：限定底层集合后由 DSH 生成 SDK，整合保留该 scope 的 PTC 指导、SDK 声明与 run_code，不能继续只用底层 allowed 列表把外层删除。提炼/native 回退仍保留原生声明和原过滤规则，不额外复制一套 SDK。输入预算的 measure 与真实首次请求都计算最终组装结果，包括新增 SDK/指导。

现有维护 `tools/pre-execute` 对外层 run_code 单独检查阶段、取消、来源 generation 和部署权限结果；允许后不把 code 参数送入文件路径检查。每个 bindings 子调用仍进入原 allowed、路径、来源和取消检查；不向 SDK 暴露被禁止的业务工具。整合没有 Nano preset，不能假称它已经接入 NanoApproval，也不为切模式额外挂载完整业务配置；保持现有维护 guard + 部署 sandbox 权限链。

原有 Bash 已允许在部署 sandbox 下执行程序，raw Node 同样属于这个程序执行信任边界，不能宣称文件 bindings 的路径 guard 能拦截所有直接 Node API。整合指导明确只写正式仓、来源只读、所有调用 await、不启动脱离当前调用的进程；文件/Git 操作优先现有 bindings。沿用 Bash 的禁止后台/超时转后台配置，验证 run_code 超时/取消结束对应 runtime 及其前台命令后再释放单写者；不新增 syscall 沙箱或静态代码判纯机制。

整合 prompt 加最小 PTC 用法，按需回查被省略的原始子结果。自己的 history 恢复维护输入，ptc_history 恢复自己的执行回执，source_history 读取已授权业务轨迹，三者不能混用。Git 提交仍通过现有 Bash；正常结束后的最多三次修复、仍失败回到本批起始提交、异常结束保留实际文件/Git、只在宿主核验成功后推进来源游标等现有语义全部保持。

### Context 生命周期

| Consumer | Before → After | 保留/失效与观察点 |
|---|---|---|
| 普通执行模型 | 原生 tool schemas → SDK + run_code；中间值留在程序中，ptc_history 按需恢复宿主子回执 | 首请求、批处理后下一请求、失败后、new_context 后、重启后检查实际 provider 输入；配置回退后仍可读既有 PTC 记录 |
| Auto reviewer | 具体工具动作 → 增加完整外层程序，随后仍审具体子调用 | 不获得执行权限；审核快照与用户授权更新按既有规则失效 |
| Dreaming 提炼 | 展示仍 native、能力及输出结构不变；输入可含宿主 PTC 子调用经历 | 仍直接阅读宿主给定材料；不增加业务回查工具 |
| Dreaming 整合 | 原生工具声明 → SDK + run_code，增加自身 ptc_history | 首次/子调用后/换窗/异常及 native 回退的真实请求；冻结 cut、generation、维护 history/自身回执/业务 source_history 分离 |
| fork / nested worker | 原生继承规则 → 同一规则下保留来源展示模式 | inherited prompt/tool prefix 与 own events 的界限不能混淆 |

PTC 指导最小增量：新进程无持久变量；工具必须 await；不要捕获错误后伪称成功；输出答案所需依据；new_context/完成任务等结束当前执行的工具单独调用并立即结束程序，不能在其后排队其他动作。以 DSH 实际工具语义验证上述终止路径，不用额外 Agent Loop 模拟。

## 本次审查安排

| 必须回答的问题 | 能力/阶段 | 证据 |
|---|---|---|
| 普通执行角色与例外是否准确，公共 runtime 与权限边界是否成立 | codebase-design 作者设计；change-design-reviewer；change-code-review 实施 | 实际创建/恢复路径、public exports、全程序/子调用拒绝与 allowed 效果 |
| 模型是否理解 SDK，恢复/审核/记忆是否有足够原始依据 | agent-context-review 设计与实施 | 受控 provider 抓真实出站输入；代表性真实模型请求、动作和结果；同时覆盖 fork/换窗 |
| 用户任务、委派与回查是否仍能完成 | product-journey-review 实施 | 隔离 IM 发起任务、工作回执、取消后恢复、Dreaming 产物及实际来源回查 |
| 是否减少真实总开销 | performance-review 设计与实施 | 下述同条件对照，包含 reviewer，不能以脚本 provider 的正确行为证明模型收益 |

无新的视觉/交互决定，不制作原型；不新增 frontend 评审套餐。源码自检只证明机制，不能替代最终真实模型/产品验证。

## 验证与效率对照

确定性验证覆盖：角色矩阵；配置缺失/true 默认 PTC、false 回退和 bash 不可用；禁止扩大空 allowlist；同 scope 模式冲突的原配置保留；外层允许/拒绝/异常；子调用拒绝与读写豁免；Auto off、显式 skip；raw Node 临时文件副作用在拒绝后不存在；取消/超时部分副作用；成功子调用未打印即 outer 失败的 ptc_history 发现/读取和不重复副作用；用户追问被筛掉的原文；配置回退后回查与 fork 未继承原件的 unavailable；fork 与冷恢复；memory 内外层配对和 Unicode 分页、cutoff/generation 越界；native 老历史不回填。Dreaming 两阶段矩阵覆盖提炼工具/schema/JSON 不变、整合 SDK 与 run_code 未被过滤、最终输入预算、维护自身回执恢复、禁止业务工具/越界 bindings、来源失效、前台 Bash、runtime 取消后再释放单写者、Git 核验/三次修复及失败恢复。

代表性真实任务选三类：批量读取并筛选、顺序依赖工具查询、读取并修改临时工程。每类固定输入、工具返回数据、模型/effort、权限/审核模型和隔离 workspace，native 与 ptc 各至少三次，交替顺序；区分冷/热缓存，不把 native → ptc 首次 SDK 前缀失效混入长期收益。另测 Global/PA → worker → 结果交付、已有 PTC worker fork 延续、Dreaming 利用未输出的原始子结果形成有据经验。Dreaming 另用相同冻结批次和起始记忆仓副本对照 native/PTC 整合，提炼产物固定复用，核对记忆质量、来源、Git 和失败状态，分开计量整合本身消耗。无需向生产或真实联系人发送测试消息。

逐次保存：业务结果与必要证据、真实模型输入/输出与 session locator、主/child/审核分别的 input/cached-input/output tokens、模型轮次、工具次数、重试、审核等待和总墙钟时间。重叠并行耗时不相加；计费信息可得才报告费用，否则只报告 token。

交付底线是正确性、权限与恢复均通过；效率报告可以结论为无收益。若没有稳定净收益，如实记录，提供显式 native 回退，不擅自改回默认 native，也不扩大到主 Agent。本 unit 交付默认 PTC、配置回退和实测结论，不预设节省百分比。

## 契约层增量（delta-spec）

仅 [specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md)：普通执行与 Dreaming 整合默认 PTC、提炼不变、权限不放宽、原始依据可恢复和安全退出。其余不改 current；实施完成后才归并。

## 风险与回退

整段代码审核会增加延迟/输入；双层审核有真实成本，必须计入总量。Node 仍有与 bash 同级的程序执行能力；本方案不承诺消除任意程序的审核模型误判。工具 SDK/output schema 的不稳定或缺少结构化返回会使程序容易出错，返回原始内容给模型判断，不做泛化解析兜底。

PTC 固有超时可能不适合长等待；模型使用已声明 deadline，长任务用原有后台工具/作业，不把无持久 run_code 伪装成常驻 REPL。恢复不得重放有副作用的代码。配置回退保留全部记录，关键原始证据恢复不通过则本项验收不通过。

## 一次性部署迁移

无历史数据迁移。实现版本部署后，缺失配置值即按角色采用默认 PTC；不用逐 owner 写 true，不迁移历史事件、不清空 session。后续用户授权部署时，指定 owner 可在配置文件写 false 回退；本轮不修改生产配置或部署，也不安排生产写入试验。

## Runbook for Reviewer

本轮仅设计审查，无常驻服务。实施验收涉及隔离 Node/DSH 和用于真实任务入口的 IM：

| 服务 | 停止 | 启动 | 健康/身份核验 |
|---|---|---|---|
| worktree IM + Node/DSH | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh --profile daily` | 以脚本 readiness 结果和该 worktree `.e2e-ports.env`/PID 身份为准，核对受审 commit；禁止访问生产端口 |

执行前按 local-development 安装受审版本依赖并构建；先 `python3 scripts/dev_host.py check`，按 worktree-runtime guard 确认 config、数据、身份、workspace 与端口隔离。真实 provider 来自本机 dev-host 的 E2E 配置，当前仅已核实路径和工具存在，尚未验证模型可达性。实施时缺模型访问则记录相应验证 inconclusive，不伪造成功；不影响本次静态方案可审。

窄测试使用 `pnpm exec vitest run` 运行本 unit 修改/新增的 integration tests，优先复用 capabilities、approval-sources、global-child-tools、fork-prefix-provider、Dreaming 来源与恢复 fixtures；选择实际存在的文件，不运行假想脚本。真实旅程后执行 e2e-down 回收；原始轨迹/日志留受保护本地产物，仓库只写必要脱敏结论及定位。

## Milestones

单 M1：模式、审核和经历证据必须一起成立才可交付，拆成分别可部署的部分会留下权限或记忆缺口；本期没有独立并行交付需要。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-ptc-trial | 普通执行与 Dreaming 整合默认 PTC | 无 | A | integration 的模式/角色、审核、Dreaming 整合装配、knowledge 回查、提示与定向 tests；必要的 Node 配置保真 tests；unit delta 与结论 | [reviewer] spec 的全部场景成立，普通任务/主从交付/整合/回查/配置回退在真实入口有证据，权限与未知状态如实；[worker] 上述角色、程序和子调用审核、fork/恢复/终止、经历分页边界确定性验证通过；实际 provider Context 及三类同条件对照齐备，计入审核消耗；范围内默认 PTC、配置 false 回退，提炼与其他例外保持原模式，DSH 公共依赖边界通过；受影响 canonical 归并和资源回收完成 |

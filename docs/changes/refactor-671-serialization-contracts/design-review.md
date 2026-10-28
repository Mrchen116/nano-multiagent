# Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`（独立 reviewer，未参与受审设计编写）
- target: `refactor-671-serialization-contracts` 的 motivation、design 与 M1 骨架
- review_mode: `full`
- mode_reason: 首轮独立 Gate 2，覆盖需求、现状、公共接口、职责、验证和 milestone。
- started_at: `2026-10-28T10:49:00+08:00`
- completed_at: `2026-10-28T10:52:03+08:00`
- duration: `>= PT183S`；started_at 是本轮审查中首次取得的时钟记录，源码阅读在此前已开始，不推算未记录的起始时刻。
- validated_at: `c422fedcdb9aeb609593a42e835230985ae5bfaf`
- executed_base: `a34af8473c15f1145d6a1dbbc036bc320560f351`（现场 `main`）
- checkout: `/Users/czj/.codex/worktrees/serialization-contracts/nano-multiagent`
- branch: `codex/serialization-contracts`；开始时 working tree clean。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**

两个纯函数的职责划分、特殊字节规则保留与零用户面验证路线成立。但“完整盘点并决定复用/保留边界”的要求尚有一个涉及持久 Workflow replay 身份的遗漏，见 R1-W1。该问题可以通过明确补齐盘点与范围决定解决，不要求机械扩大所有序列化代码的改动范围。

### Coverage 与证据

1. **现状与真实入口。** 已读 `AGENTS.md`、文档地图、workflow、`SPEC.md` 的包边界和相关 current specs。实际路径为 `apps/im-server/src/server.ts:177` → `registerControlRoutes` → `control.ts:1106` 的 Channels 路由；`channels.ts:30-69` 的 `sealChannelSecret` 实际使用 Task serializer，`apps/node/src/main.ts:80` 装载 ChannelKey，`packages/channels/src/channel-credentials.ts:49-60` 执行真实解封。不是只在测试出现的代码。Task 由 `gateway.ts:50` 实例化，任务比对与迁移摘要也确实依赖该函数。
2. **排序、Unicode 与遍历。** 核对 `task-graphs.ts:44-56` 的 replacer + `Object.keys().sort()`、`configuration.ts:7-11` 的 `Object.entries` 预遍历 + U+0080..FFFF 转义、`control.ts:39-43` 的 U+007F..FFFF 规则、`identity.ts:89-105` 的递归预遍历、Channels 和 Node 的浅排序实现。设计正确区分 UTF-16 排序与 localeCompare、DEL 转义边界、数组保序、JS 数字索引枚举、toJSON 执行顺序和浅/深排序。identity 复用 configuration 后补 DEL 对实际 JSON/SQLite 纯数据输入成立；不应据此声称任意带 getter/Proxy 的 JS 对象访问顺序完全一致，设计已将实际输入域限定为数据对象并排除扩展非 JSON 对象支持。
3. **消费者和未用实现。** 已全仓搜索 canonicalJson/canonical/asciiJson。`product-contracts/src/index.ts:82` 的显式导出覆盖 `:97` 的 interactive 星号导出；未发现 interactive serializer 的直接导入者，删除该实现与迁移当前根导入合理。configuration 对应 IM message-attempts、interactive-source、interactions、gateway，以及 PA Inbox/global-agent/personal-assistant 的身份计算；设计的按字节语义迁移覆盖这些消费者。遗漏的 Workflow 实现单列为 R1-W1。
4. **职责与复用。** 将无 Buffer/crypto 的共享字节编码放在 product-contracts 独立公开 subpath，消除 IM Channels 对 Task 通用函数的依赖，符合 `SPEC.md:30,46-49`。保留 candidate/identity 的 DEL 策略和 Node/Channels 的浅排序，比引入多选项 serializer 更小，也避免悄悄改变凭证 AAD。crypto、AAD 投影、配置归一化继续由现有 owner 负责；无需新增框架或兼容别名。配置模块仍需其领域哈希依赖，纯 subpath 的价值是让其他消费者不经配置入口取得编码能力。
5. **需求、delta 与零用户面。** motivation 限定字节等价、无数据迁移、无 Row/ImContext 重构。设计无 HTTP/WS、存储 schema、权限、交互或模型上下文变化，故 `no spec delta`、无 prototype、无一次性 deployment prompt 和跳过产品 reviewer 均合理。PA 只是同一实现的导入/命名变化，不构成新增 Context 选择/注入行为；本轮不另开 Agent Context Review，也不要求真模型或飞书旅程。此判断以实施保持所有字节为前提，不能用零用户面标签豁免字节兼容核验。
6. **测试方案。** 已核对 PA 配置固定 SHA-256（`packages/personal-assistant/tests/configuration.test.ts:38-43`）、旧 receipt 恢复、IM approval-configuration、control 信封及 Channels 凭证测试。现有 Channels 测试主要是同一实现的随机 round-trip；设计新增改动前固定向量、合成历史信封、真实 IM seal → ChannelKey.open、owner/revision 拒绝测试，能够补上双方同时变错的风险。计划覆盖中文、emoji、DEL/非 ASCII 边界、孤立代理项、嵌套、组合字符与数字索引，且要求 expected 来自旧实现，充分支撑本次搬移。Node 算法仅改名，保留现有 proof 测试即可，不必为未变逻辑新增框架。
7. **M1 与验证边界。** 单 milestone 没有并行冲突；固定字节/摘要/历史信封/实际 owner 互操作退出标准可执行。已存在 `M1-serialization/.gitkeep`，没有提前创建实施台账。设计审查只做源码、接线和现有测试内容核对，未执行尚未实现的新测试、未运行服务、未修改生产数据；不能将本报告作为实现验证通过的证据。

### 历史问题闭环

首轮，无历史问题或 Author Resolutions。

### Issues

#### R1-W1 — 全仓盘点漏掉与 Task 同语义且用于持久 replay 身份的 Workflow serializer

- **位置：** `design.md:11-23` 的全仓盘点与 `:29-41` 的复用/归属结论；M1 范围 `:84`。
- **源码证据：** `packages/dsh-integration/src/workflow/control.ts:48-57` 仍有私有 `canonical`，与 Task 一样是 JSON.stringify replacer、递归 `Object.keys().sort()` 和非 ASCII 原样输出。`:138-142` 对 `[previousKey, prompt, behavior]` 求 SHA-256，`:161-169` 用该 key 决定历史调用能否 replay。`workflow/engine.ts:373-395` 实际创建控制器、接收 previous.calls 并保存 record.calls；`packages/dsh-integration/src/index.ts:176-177` 装配引擎和工具，故不是死代码。现有 `workflow-control.test.ts:68` 与 workflow lifecycle/native 测试覆盖 replay。
- **影响：** 用户要求完整盘点真实调用者和持久指纹后决定共享/保留，而本设计称已做全仓盘点，却遗漏与新 shared UTF-8 函数相同语义的实现。实施者目前不知道此持久 key 是刻意保持原位还是漏迁，无法完整兑现“该共享的复用、该保留的明确区分”的边界，亦不能从 M1 得知相应验证是否需要纳入。
- **所需修订：** 将该实现、prompt/options/schema 输入域、持久 key 与 replay 消费者补入盘点，并明确决定复用 `sortedJsonUtf8` 或因本 unit 边界原样保留的理由。若迁移，补齐 M1 范围及旧 key 固定向量/replay 验证；若保留，明确不改变其代码与历史 key。本 finding 不要求改动 Workflow 调度、上下文或 runtime 架构。

### Recommendations

- **R1-R1（可选）：** 在实施接线清单里注明 `tests/contract/test_runtime_dependency_contract.py:14-45` 对公开 subpath 使用精确 allowlist。新增 serialization subpath 后按实际消费者增加精确项，保留现有禁止跨包私有源码导入的约束；不应为使测试通过而放宽为任意 `@nano/*`。设计已要求公开 exports 与完整 CI，此项是实现提醒，不额外阻断。

### Author Resolutions

- R1-W1 — accepted。全仓搜索确认 workflow/control.ts:48 的同语义 replacer 与 :141 持久 key 消费；已在 design 盘点表、架构总览、验证第 4 项和 M1 范围补齐，选择复用 sortedJsonUtf8，保持行为 options 与 SHA-256 投影不变。改动前已在 a34af8473 的原实现采集 Unicode/嵌套 schema key 1eb5c3ecce73fd0725c41e4d87e08168cedeb7be110fc8e7741e9b30743f326c，后续从固定历史记录验证 replay。motivation 同步这一纯编码范围，无产品语义变化。
- 补明 runtime dependency contract 仅允许现有合法 owner 的新 serialization subpath；测试不放宽生产跨包相对导入。


## Round 2

### Metadata

- reviewer: `/root/design_review`（沿用 R1 独立 reviewer）
- target: `refactor-671-serialization-contracts` 修订后的 motivation、design、M1 骨架及 R1 Author Resolutions
- review_mode: `full`
- mode_reason: R1-W1 的处理新增 integration Workflow 消费者并扩展 M1 范围，按 milestone 范围变化执行 full；同一 reviewer 保留 R1 直接源码证据，同时核对完整设计仍成立。
- started_at: `2026-10-28T10:53:07+08:00`
- completed_at: `2026-10-28T10:54:41+08:00`
- duration: `PT94S`
- validated_at: `a55c9b999ba8ff717dbf1ce060a720d523cfd3c3`
- executed_base: `a34af8473c15f1145d6a1dbbc036bc320560f351`
- checkout: `/Users/czj/.codex/worktrees/serialization-contracts/nano-multiagent`
- branch: `codex/serialization-contracts`；本轮开始时 working tree clean。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

R1-W1 已闭环。完整方案能够在现有职责边界内保留旧字节与持久身份，并为 Workflow 增加所需的历史 key 兼容验证；允许进入实施。

### Coverage 与证据

1. **现状与需求。** 已核对 `c422fedcdb..a55c9b999` 的全部文件差异，只有 motivation、design 与历史审查报告，没有产品源码、测试或 SPEC 变化。motivation 新增的范围仅为 Workflow 持久 key 所用的相同纯编码，仍不修改调度、上下文、Row/ImContext 或 Gateway 架构；用户要求的完整盘点现在包含这份真实消费者。
2. **新增调用链与输入域。** design 现状表补充 WorkflowControl 的前序 key、prompt、去掉 label/phase 后的 options 及嵌套 schema；与 `workflow/control.ts:138-142` 一致。其 `:161-169` 比较历史 key 决定 replay；真实组装仍由 `workflow/engine.ts:373-395` 接入 previous.calls 与持久 save，再由 integration `index.ts:176-177` 注册。`packages/dsh-integration/package.json` 已声明 product-contracts 依赖，不新增逆向依赖或私有 DSH import。
3. **职责与公共接口。** 两个无选项函数的签名、UTF-16 排序、转义边界、遍历方式和 owner 特例均未改变。Workflow 的现有函数与 Task 相同，选择共享 sortedJsonUtf8 可以删除实际重复实现；crypto 和 `[previousKey,prompt,behavior]` 投影继续留在 Workflow owner。新 subpath 的精确 allowlist 已加入设计，不放宽现有生产边界。R1 对 IM/Channels/PA/Node 以及无消费者 interactive 实现的直接源码核对仍成立。
4. **历史兼容验证。** 设计新增 Unicode prompt、嵌套 schema 的固定旧 WorkflowCall.key，并要求从固定历史记录 replay；与现有 `workflow-control.test.ts:68-97` 的 replay fixture 相接，不需要真实模型。已读本地 ignored 的 `output/refactor-671/workflow-capture.ts`：直接调用未修改的原 WorkflowControl；`workflow.json` 中的 completed record 包含 key `1eb5c3ecce73fd0725c41e4d87e08168cedeb7be110fc8e7741e9b30743f326c`、Unicode prompt、嵌套 schema 和 completion，满足后续固定历史输入的来源需要。只核对采集方式与记录，不将该记录或作者报告的 14 个基线测试通过认作待实现版本已验证。
5. **未改变的覆盖。** R1 的 Unicode/DEL/孤立代理项/嵌套/数字索引固定向量、PA 配置固定 SHA-256、旧 receipt、历史信封、真实 IM seal → ChannelKey.open 与 owner/revision 拒绝测试方案均保留；实际源码没有变化。identity/Node/Channels 的特殊规则仍分别保留，既有跨端差异不在本 unit 修复。
6. **delta、零用户面与 M1。** 复核完整设计后 `no spec delta` 仍正确；新增的 Workflow 变更也只改变同字节函数的导入，不改变模型可见内容、权限、调度或恢复时序。无需 prototype、产品 reviewer、真模型旅程或部署迁移。M1 已显式包含 integration workflow，验证章节明确历史 key/replay 要求；单 milestone 没有并行写入冲突。实现后仍须 code review/verifier 和相关 CI，设计批准不替代这些门禁。

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution accepted；已补齐现状表、motivation、架构接线、M1 范围和历史 key/replay 验证。源码证据见本轮 Coverage 2–4，保留相同字节并明确复用的决定已收口。
- **R1-R1 — addressed。** design 的契约增量段明确 runtime dependency contract 只为实际使用者补 serialization 精确 subpath，保留原依赖方向限制。

### Issues

无。

### Recommendations

- **R2-R1（可选文案修正）：** 现状表“由 workflow/service 装配”应写为 `workflow/engine.ts`（由 integration `index.ts` 注册）。仓库没有 `workflow/service.ts`；本轮已核实真实入口，因此该名称笔误不影响方案、范围或门禁结论，修正后可按非实质变化 retained。

### Author Resolutions

- R2 — 核实 Approved，无实质异议。可选 R2 装配路径文案建议 accepted：将 workflow/service 更正为 workflow/engine.ts；仅修正文档来源路径，无接口/范围/验证改变，Gate 2 retained。

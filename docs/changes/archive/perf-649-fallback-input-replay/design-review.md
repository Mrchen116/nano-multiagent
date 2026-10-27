# perf-649 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`，独立于本 unit 的首文档与设计作者。
- target: `docs/changes/perf-649-fallback-input-replay/`。
- review_mode: `full`。
- mode_reason: 首次 Gate 2，完整审查现状、需求、设计、契约增量、milestone 与验收前置。
- started_at: `2026-10-23T23:10:48+08:00`。
- completed_at: `2026-10-23T23:13:34+08:00`。
- duration: `166s`（按本轮记录的基线核对时间计）。
- inspected_base: `c5ee4d1bdca912391097fe1769ce56ec2015c297`，branch `main`；相对开工 `893d903a00dff83c47b08310ed528b71eaae6786`，受审两份产品源码没有变化。新增提交为并行 unit 的首文档，不据此宣称其他 unit 已通过门禁。
- reviewed snapshot SHA-256:
  - `motivation.md`: `f7a0d99a6a77fbd46b00b722e6c4175d1174d0ba74b085371a0746b9c21eb131`。
  - `design.md`: `60bc86c26812aef2fc806ca3df4cf4a1ec9421dd0015e4d0edc0ab6ae24df3fd`。
- 现场已有其他 unit 的 staged/dirty 内容；本轮只创建本文件，未修改设计、产品、测试或 index，未提交、启动服务或运行产品验收。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**。

单遍瞬时归属投影的职责、真实接线和核心语义均成立；阻断项是完整栈验收所需的失败/恢复驱动仍以未落实的“已有 mock 配置”代替。需要补齐可执行的验收设计后复审，不要求在设计阶段先完成产品实现。

### Coverage and evidence

#### 现状及真实装配

- `apps/node/src/main.ts:88-132` 通过公开 `@nano/dsh-integration/client` 创建 `RuntimeSupervisor`、调用 `prepareProfile` 并 initialize。`packages/dsh-integration/src/client.ts:39-50` 启动官方 DSH CLI 和 stdio RPC；`src/index.ts:123,183` 装配 ModelPolicy 并 attach；`src/model-policy.ts:35,48` 实例化并 attach ModelFallback。因此受审 `model-fallback.ts` 是产品实际路径，不是测试专用替身。
- `model-fallback.ts:256-269` 在有未完成 run 的 turn/end 上先提取所有历史 inbox 插入 ID，再为每个 ID 调用 `inputEvidence(history,id)`，之后才判断候选与失败类型。普通成功、未配置备用也负担该循环；重复插入 ID 会重复回放。现状表述“每个 turn/end”应理解为通过上述 run guard 的事件。
- `model-fallback.ts:130-158` 的 attach 恢复路径会把已持久化 terminal 送回 observe；helper 必须依照传入完整快照的最终归属筛选，不能偷换为“截止目标 turn 的前缀”。设计的完整快照重放保留了这一点。
- 本轮未重跑首文档引用的旧审计 benchmark，因此旧毫秒数仅为作者历史证据，不作为本轮实测结果。源码足以确认重复全量回放存在；性能目标需在实施实验兑现。

#### 语义、接口与架构判断

- `input-evidence.ts:5-45` 独立核实了两条 queue、原生 splice、`removedCount=0`、claim 未出现 user/message 时即归属 turn、canceled removal 不覆盖 turn、user/message 覆盖归属、turn/end 清空当前 turn 的规则。设计对这些事件顺序的处理与旧投影相同；重复 ID 共享最后归属，首次插入 Set 保持 ModelRun 既有筛选顺序。
- 历史只出现 user/message、没有 inbox 插入的 ID 不进入旧 `ids`，设计明确继续排除；`nano-fallback:` 排除与 `run.inputs` 去重仍由消费者维持。返回的是 ModelRun 的候选输入列表，不是完整 accepted/consumed/terminal 证据，职责没有扩张。
- 归属投影属于 `packages/dsh-integration` 的原生持久事件解释，放在现有 `input-evidence.ts` 中由 ModelFallback 使用合理。对比继续逐 ID 复用完整 inputEvidence，新 helper 避免重复构建相同 queue；对比常驻索引，瞬时投影无需额外生命周期、恢复和缓存一致性。保留单 ID API 的少量重放规则重复由差分测试保护，其维护成本小于本项引入统一常驻索引。
- `SPEC.md` 的 Node→公开 client→DSH 边界不变；PA、Channels、IM 不新增 DSH 依赖，无 private import、第二套 loop 或持久 schema。其他 unit 无须消费新 API；单 milestone 所有权闭合。
- O(E+S+I) 的时间界限已显式包括原生 splice 成本，避免把队列移动错误宣称为常数。该界限是 helper 的界限，不是整个 observe/schedule 或整场会话的界限；既有 fallback 故障路径的逐输入 lookup 保持范围外。临时空间的记号有一处可精确化，见 R1-R1。

#### 需求、current 契约与 delta

- `motivation.md` 保留原始授权、范围、指标与用户场景。`design.md:18-20,42` 覆盖普通成功、无备用失败、备用成功、多 attempt、恢复和取消；不会借优化变更错误重试、逻辑 turn 或安全边界。
- current target 为 `docs/specs/gateway/agent-capabilities.md:40` 起模型备用链，包含无备用、耗尽、上下文、已发表内容阻断、切换提示、粘性及推理强度。设计仅替换内部计算，`session.lookup` 在 `index.ts:362-366` 仍经 fallback.evidence；后者保留 logical run 的 turn/turns/terminal 投影，故 `no spec delta` 判断合理。没有 MODIFIED Scenario 被删，也无新前端平台设计或 must-match。
- 现有 `tests/input-evidence.test.ts` 覆盖 claim、pending 和取消；`tests/model-fallback.test.ts:11-295` 使用真实 DSH RuntimeClient，已有 prepare/finish/exhausted/context/published/tool/cancel/new-input/restart/pre-step。新增逐前缀差分矩阵及正常无备用路径有必要，不要求为本次纯内部变化泛化测试基础设施。

#### Milestone、性能验收与产品前置

- M1 的源码边界、依赖、worker/reviewer 退出标准明确；目录中仅 `.gitkeep` 符合设计阶段要求，没有预填实现记录。
- 500/1000/2000 历史输入及单个末轮输入实验与 O(inputs×events) 痛点对应；旧 oracle 等价、访问计数至少减少 95%、同机中位数至少 5 倍分别验证正确性、工作量和实际收益。墙钟只作实验结果，不设跨机器 CI 硬阈值，合理。后续还须报告临时状态大小，不能用事件访问减少推断总内存已减少。
- 接口驱动完整 IM/Gateway/DSH 栈符合无客户端变化的验收方式；隔离权限和资源所有权已写明，无须生产凭据。`scripts/e2e-up.sh` 确有隔离配置、端口和进程启动，以及 IM health、节点 online 检查；但其默认配置连本机 4000 模型服务，不自动提供 deterministic mock，备用/恢复可控条件亦未落实，见 R1-W1。

### Historical issue closure

无历史 Round，无待继承 issue。

### Issues

#### R1-W1 — 必验完整栈旅程的失败、恢复与取消驱动尚未落实

- 位置：`design.md:32-36,42`。
- 证据：runbook 声称可使用“仓库已有 deterministic mock LLM 配置”，并把具体配置及命令推迟到实施自检。但 `config/e2e/gateway.yaml` 的默认模型指向 `http://127.0.0.1:4000`；`scripts/fixtures/anthropic_sse_ok_recording.py:94-119` 仅返回 200/ACK，没有按 primary/backup 控制失败或停留在切换窗口的能力。已有 `model-fallback.test.ts` 虽覆盖取消和重启，却是在 runtime 层以 `client.rpc.handle('model.check', ...)` gate 驱动，不能原样代替设计承诺的真 IM/Gateway 产品验收。
- 后果：实施者/产品 reviewer 仍需自行决定怎样稳定触发“主模型失败→备用成功”和切换中的取消/重启、怎样观察完整栈最终结果；可能退回 runtime 单测，或临时依赖未声明的外部模型。这使 M1 的必验资源及方法未收口。
- 修订要求：在 design/runbook 中明确复用的完整栈 fixture 入口与必要的最小新增场景能力（如果需新增，明确归入 M1 验收辅助范围），列出构建、启动/停止、health/online 入口及本地测试账号来源；说明 primary/backup 失败控制、切换窗口的可观察等待条件与重启/取消驱动方法。可采用临时、仅本 unit 所有的本地 fixture，不要求新建通用框架或在 Gate 2 前实现它；但不能再把选择本身全部推迟。修改后局部复审此项即可。

### Recommendations

#### R1-R1 — 让空间边界涵盖未插入 inbox 的 user/message ID

`design.md:13` 将 I 定义为不同 inbox 插入 ID 数，但最后归属 Map 按 `design.md:9` 也会遇到只出现 user/message 的 ID；例如 `model-policy.ts` 的 model-selection notice 在 pre-step 直接追加。若 Map 无条件记录它们，瞬时空间应写 O(I+U+Q)，U 为额外 user/message ID 数；或在实现中采用等价且已验证的投影约束。它依然是随历史线性、调用后可回收的状态，不影响所选方案，建议准确记录而不为节省这一项引入复杂预扫描/索引。

### Author Resolutions (Round 1)

- R1-W1 accepted：已在 design Runbook 明确临时 HTTP fixture 的 fail/ok/backup/slow、可观察等待点、取消指令、重启入口、构建与隔离清理命令。fixture 本地冒烟 fail=401、ok/backup=200 SSE。产品恢复场景具体化为已成功备用会话重启后续聊；切换中强制中断继续由现有原生 runtime restart gate 保护，避免凭空加强 current 恢复保证；motivation 同步消歧，原始授权原文不变。
- R1-R1 accepted：空间边界修正为 O(I+U+Q)，U 覆盖仅 user/message 出现的 ID。无新增索引/预扫描。

## Round 2

### Metadata

- reviewer: `/root/design_review`，沿用 Round 1 独立 reviewer，未参与设计修订或 fixture 编写。
- target: `docs/changes/perf-649-fallback-input-replay/`。
- review_mode: `full`。
- mode_reason: 除 R1 问题闭环，本次首文档“恢复或取消”Scenario 的 WHEN 有实质修订，重新覆盖需求、实现边界、契约与 milestone，不能只做文字 closure。
- started_at: `2026-10-23T23:16:17+08:00`。
- completed_at: `2026-10-23T23:17:02+08:00`。
- duration: `45s`。
- inspected_base: `15063908dc738f6485d7255c5798430d4f1841ab`；受审 `input-evidence.ts`、`model-fallback.ts`、`model-policy.ts` 和原生 fallback tests 相对开工基线仍无变化。
- reviewed snapshot SHA-256:
  - `motivation.md`: `66689672755532f4d3bd4cd91c67b19243e5c70326221e1e4999293152221f8a`。
  - `design.md`: `7c7c2be88aa3ca74d63ca7977796b5c3c42cb068e33f10b74819ed2207fa4e08`。
  - 本地验收辅助 `/tmp/perf649-environment/stub.py`: `08507bef7f79a7b9bab934ce58eacb8b9c0b8dee661e40a3cf215f48959201df`。
- 本轮只追加本报告，未启动产品或模型 fixture，未改其他文件，未提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

### Coverage and evidence

- **需求与用户约束**：重新核对首文档全文及其 git diff。原始用户分工仍要求“关键恢复/取消场景正确”，没有要求所有中间故障点都通过客户端驱动；原文、性能指标、持久输入语义、不扩大其他 unit 依赖的约束均保持。修订将产品层恢复场景明确为成功备用会话重启后续聊，同时设计明确保留切换中强制中断、claim/pre-step/new-input 的原生 runtime 测试，未删除这些正确性要求。两层证据的范围现在清楚；不能在最终交付中把成功后重启说成完整栈切换中重启已实测。
- **现状与接线**：复核相关源码相对开工基线无 diff，Round 1 的 Node→RuntimeSupervisor→ModelPolicy→ModelFallback 装配、turn/end 热点和 attach→observe 恢复证据仍有效。算法仍完整重放事件、维护双队列和最后归属，按首次插入顺序返回，未换为只看 user/message 的近似计算。
- **职责与复杂度**：helper 继续仅承担 integration 内输入归属投影，inputEvidence/session.lookup 和 ModelRun 持久格式不变；不引入常驻增量索引或跨包消费者要求。O(E+S+I) 时间包含 splice 工作；O(I+U+Q) 空间现已包含未插入 inbox 的 user/message ID，修正没有增加机制。
- **current 与 delta**：模型备用链 current target、逻辑 turn/attempt 与失败/粘性输出不变，no spec delta 仍成立。首文档的验收场景细化不创造新 current 保证。没有前端变更，无原型或双端 must-match 缺口。
- **milestone 与测量**：M1 仍单组、无依赖；差分矩阵、真实 runtime 回归、500/1000/2000 历史实验、95% 访问减少和 5 倍同机耗时目标不变。临时 fixture 现明确归入 M1 验收辅助准备与清理，未形成新的产品服务或长期框架。
- **验收前置**：runbook 现提供构建、独立配置来源、测试账号、随机模型端口、HTTP fixture/完整栈的启动与停止、健康检查、IMClient 路径与结果观察方式。读取本地 stub 确认 fail=401、ok/backup SSE 和 slow-release 分支，以及 ThreadingHTTPServer；`prerequisite.jsonl` 有 fail/ok/backup 的请求记录。作者的状态码冒烟结论作为作者证据引用，本 reviewer 未重复执行 HTTP 冒烟；脚本静态能力已足够证明设计资源与方法落实，不表示真栈旅程已验收。
- **恢复/取消驱动**：`tests/e2e/critical_paths/_im_client.py:108-141,174-212` 提供新一代节点等待及带 profile_version 的配置更新；`_im_gateway.py::restart_gateway` 实际调用 Node CLI stop，再以相同隔离 config 重启并返回 generation floor。`packages/personal-assistant/src/single-thread.ts:75-87` 识别用户 `/stop`，经 taskStop 或 session.cancel 返回可见确认，证明所选命令是真实产品入口。slow 请求记录→发送 `/stop`→观察确认→release→不出现旧成功正文的顺序有可观察条件，不依赖猜测 sleep 时长。此处通过的是验收设计，实际恢复及取消效果仍由实施后独立产品 reviewer 观察。

### Historical issue closure

| ID | Author Resolution | 本轮核实 | Status |
|---|---|---|---|
| R1-W1 | 补齐本地 fixture、完整栈命令、失败/备用/取消驱动与恢复分层 | 资源脚本存在、分支语义可读；启动/隔离/停止与现有 helpers 对接；原先未决定的 fixture 和等待点已决定，关键中间恢复保留 runtime 覆盖 | closed |
| R1-R1 | 空间界限补充 U | design 的 U 明确为仅 user/message 出现的 ID，瞬时 Map 状态解释与算法一致 | closed |

### Issues

无。

### Recommendations

无新增建议。临时 fixture 及配置由本 unit owner 在实施验收期间保有并清理；交付记录须区分模型前置冒烟、原生 runtime 回归和真实产品旅程结果。

### Author Resolutions (Round 2)

已核实 R2 Approved 与闭环证据，无实质异议、无新增修订。后续分别报告切换中恢复的 runtime 回归与备用成功后重启续聊的真栈观察，不互相替代。

# feat-563 Design Review

## Round 1

### Metadata

- reviewer target: `design_review_563`
- review_mode: `full`
- mode_reason: 首轮独立 Gate 2，覆盖全部需求、设计决定、接口、delta 与单 M1；没有前轮可继承证据。
- started_at: `2026-09-16T10:27:30+08:00`
- completed_at: `2026-09-16T10:28:03+08:00`
- duration: `33s`（计时自首次读取墙钟起；此前已进行的文档和代码阅读未计入，非完整审查耗时。）
- baseline: `/Users/czj/Repos/nano-multiagent`，`main`，`10647f236`。
- inputs: 已冻结的 `spec.md`、`design.md`、四份 `specs/**` delta、`M1-delivery/.gitkeep`；design/delta/M1 为本次未跟踪受审文件。保留 checkout 中其他 dirty/untracked 内容。
- scope: 独立设计审查；没有运行产品验收、修改实现、启动服务、发送外部消息或部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案给出了足以指导实施的真实组装、权限、候选恢复与提交边界；未发现会使下游实质走偏的未解决决定。此结论不是实现正确性或真实渠道验收通过的声明。

### Coverage 与证据

#### 1. 现状、Runtime 与真实产品组装

- 核对 `product.py:294` 的 `prompt_for` 与普通/global 分支：现有图片段确实受 `workspace is not None and not global_main` 限制，且混有当前聊天路由命令。design 的共用图片语法、保留 `pa.routing`/`pa.global_routing` 分支可消除冲突，不把普通回复命令注入 global main。
- 核对 `gateway/composition.py:273` 的 PA Kernel 工厂、`:427` 的 `ReplyImages`、`:515` 的 `ImageReplyConnection`，以及 `session_composition.py:52` 的运行配置投影。设计明确从这些真实组装面接入；新 SDK/PA owner 没有被误写为已有 API。
- `config/local_store.py:150`、`:282` 区分 NodeConfig 与 IM 连接配置；`IM/ws/gateway/sessions.py:404` 当前认证注册 ack 返回 node/token，`personal_assistant/ws/im_connection.py:936` 当前在 ack 后置 registered 并触发后续收敛。design 明确新增 IM 部署值并在 ready/reconcile 前捕获，未把客户端 payload 或内部连接地址当作用户入口。
- Runtime 保留 Platform、避免重复 cwd，不写死机器/IP；明确逐消息 channel 与 Web IM 页面 URL 的不同作用、执行地址可选且不证明用户网络可达。普通/global 消息来源格式及历史时间不重写，覆盖需求的已知入口、未知可达性与换节点场景。
- 新进程注册前、重连、下一轮 runtime 配置刷新、global/cron/heartbeat/preview 接线都有明确决定；部署配置升级及旧协议报错已列入风险和验证范围。

#### 2. 权限、接口与架构边界

- `tools/send_message.py:131` 的 classifier projection 当前保留完整 target/text；`:155` 后为真实工具执行，`:204` 后传递 origin session、source Agent 与 tool-call 身份。design 保留一次工具权限判断，要求分类语义明确本地 Markdown 图片会被读取并发送，执行侧不追加 read/外发审批，也不接受 HTTP 自报已授权。
- `agent/core/tools/registry.py:200` 后的真实执行路径经 intercept，`agent/platform/hooks/builtins/auto_mode_gate.py:522` 后覆盖工具检查、模式、规则与交互分支；`agent/core/agent/runtime.py:1584` 后的 `can_use_tool` 是交互环节。设计正确指出不能仅调用该回调就声称复用完整权限链，而是抽出共享判断能力，避免触发工具 run、tool_start/end 或虚构模型 tool_call。
- 普通含图候选使用内核绑定的活动 run/control、真实 `RunDeliveryContext` 和完整目标正文，纯文字不新增权限判断；global Work 与 subagent 内部输出排除外发。候选修改后重新判断、普通/显式发送不互相偷渡授权，目标访问资格仍由 Gateway/IM 检查。
- 读取方案保留普通文件、大小/格式/数量及符号链接约束；授权等待与实际读取绑定描述符，allow 后才读字节，形成不可变快照。工作区外不因目录位置自动拒绝，读取成功也不等于外发授权。没有新增目录策略引擎或第二套审批。
- SDK 只暴露产品无关候选/control/result；PA owner 留在 Gateway，core 不依赖 PA/IM 或 platform。现有 `ReplyImages`、渠道回执与同一 SQLite 被复用；抽象新增有普通回复授权/恢复这一实际需求支撑，未发现需要阻断的额外架构复杂度。

#### 3. 草稿恢复与提交边界

- 核对 `agent/core/agent/loop.py:675` 后的候选聚合、`:707` 的 `try_commit_output`、`:725` 后的 reminder 与 durable output metadata、`:785` 后无工具调用时结束 run 的分支。设计不仅追加反馈，还明确要求 withheld 无新输入时继续模型循环，覆盖当前实现无法靠 reminder 自动继续的实际缺口。
- design 的共享模板使用既有完整群聊文案；新输入填充值展开保留时间关系、从未送达、此前成功消息仍可见与补全必要信息四项语义。图片失败使用不同原因与恢复动作；partial/unknown 不套用从未送达模板。
- `send_message.py:228` 后的 held 简短文本与设计引用一致；当前一般 `ok=false` 会抛错、`internal_dispatch.py:661` 会统一选择 HTTP 状态，设计已明确同步改两端以保留新的结构化失败结果和具体图片错误，不将它退化成 503 或用户正文。
- 核对 OpenAI provider `client.py:162` 后 finish 时 yield 完整 text buffer、Anthropic provider `client.py:174` 的 block-stop 输出。设计据此选择模型轮正文候选而非声称已有逐 token 产品流式；多 text block 的前半段不会抢先公开，工具/权限/运行状态仍独立处理。
- `runtime_delivery/image_connection.py:108` 后和 `composition.py:470` 后目前分别准备图片；设计明确交由单一 owner，已交付结果抑制 observer 二次读取/上传/发送。内部失败不经公开正文或新增 Process 文案泄露，诊断数据须编码而非直接拼接指令。
- `internal_dispatch.py:226` 后现有同步 enqueue 与短锁模式可复用。设计将授权/文件 IO/上传放在锁外，在准备之后、实际发布之前再次检查 revision/Inbox，并保留取消/reset admission；已准备私有资源不被冒充公开送达。

#### 4. 渠道、幂等与恢复

- 当前 `internal_dispatch.py:484` 后存在准备失败替换正文、`image_connection.py:121` 后存在上传失败替换正文；设计明确移除这两类退化路径，并覆盖普通与 global 显式发送，非只修一个 helper。
- 设计区分准备失败修正后的新候选与传输未知时同一 delivery 重放；稳定 call/candidate 身份、正文摘要、原 manifest 与各渠道回执闭合，未要求模型重发一份来恢复 unknown。
- 普通飞书的影子 saga 与显式双渠道发送分别处理：前者 IM 离线可后补，后者部分成功仅补缺失侧，不声称能回滚已送达消息。支持 UUID 的飞书 API 透传、卡片沿用已知 message_id、超出去重窗口停止自动重放均已收口；这不是跨服务 exactly-once 承诺。
- 成功快照、目标会话资源保护、历史回看和非成员读取边界保留；旧失败历史不被自动改写。客户端对已送达图片的读取失败仍是客户端重试，不混入发送前失败恢复。

#### 5. Delta、需求与 milestone

- 四份 delta 均指向存在的 canonical 文档；Gateway/IM 的 MODIFIED Requirement 标题与 current 完全匹配。
- 逐项对照 `docs/specs/gateway/routing-delivery.md:14` 的七个 Scenario 与 `docs/specs/im/web-chat-ux.md:14` 的四个 Scenario：未丢失未改变场景；有意更改权限/失败正文/准备展示语义，保留路由、飞书离线影子、示例不读取、放大、账号切换与图片上限。
- Kernel delta 从 SDK 消费者视角定义可选输出处理、权限、恢复、取消、部分/未知与默认消费者行为；Gateway relay delta 定义认证下发和配置错误，没有把内部实现细节写成用户 UI 契约。
- spec 的全部场景已映射到设计与 M1：访问已知/未知与节点切换；工作区内外发送、拒绝与长期回看；五图单错、不同来源错误、无法恢复；普通/显式和 Web IM/飞书一致性。M1 的 reviewer R1–R4 与 worker W1–W4 覆盖这些结果，并另列多块、旧 reminder、stale/cancel、unknown/部分成功/ACK-loss 边界。
- 单 M1 将宽路径读取、权限门禁、上下文与恢复共同交付，有明确依赖理由；没有互相冲突的并行写入范围。M1 目录当前只有 `.gitkeep`，符合受审骨架身份，不将未开始的实施记录视作缺失验证。

#### 6. 资源、真实验收与 must-match

- 没有前端组件/布局改动，故不要求凭空补 prototype；但方案明确用真实浏览器验 Web IM 单聊/群聊/global 的顺序、无占位、放大与刷新，不以 helper 单测替代用户旅程。
- 核验 `scripts/e2e-up.sh` 的 `--wt`/`--feishu` 路由及专用 listener lock，`scripts/e2e_feishu_config.py` 的测试 App/Bot 身份检查；本轮只检查专用 `feishu-e2e.env` 可读，未输出凭据、未运行外部发送，也未独立重复作者记录的在线身份 probe。
- design 已明确真实模型/真实飞书、隔离端口/config/node/workspace/data、资源失效时报阻塞而不拿 mock 代替、清理命令及 IM_PUBLIC_URL fixture 更新。验收前置与 must-match 范围足够明确；是否真正兑现留待实施后的产品门禁。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

无额外建议。实施直接按受审设计完成并执行已列验证，不为假想边界增加机制。

### Author Resolutions (Round 1)

- 已核实首轮覆盖与结论，无 issues/recommendations，无需实质修订。
- 收尾检查发现两份 delta 的末尾各多一个空行，已仅删除多余空行；spec、design、其他 delta 和 milestone 未变。交回同一 reviewer 核对最终受审文本。

## Round 2

### Metadata

- reviewer target: `design_review_563`
- review_mode: `closure`
- mode_reason: Round 1 已 Approved 且无 findings；本轮仅核对 Author Resolutions 所述两份 delta 的 EOF 空行清理，没有需求、接口、职责或 milestone 变化。
- started_at: `2026-09-16T10:30:21+08:00`
- completed_at: `2026-09-16T10:30:29+08:00`
- duration: `8s`（最终文本核对时间，不含报告追加。）
- baseline: `main`，`10647f236`；受审文档已 staged、未提交。
- retained_from: `Round 1`

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

### Coverage 与证据

- 已读取 Round 1 末尾的 Author Resolutions，并重新完整读取 `specs/gateway/routing-delivery.md` 与 `specs/im/web-chat-ux.md`。Requirement/Scenario 标题、内容和语义与本 reviewer 首轮读取的文本一致；末尾空行清理不改变 canonical target、场景保留或交付契约。
- 受审目录工作区与暂存内容无未暂存差异；`git diff --cached --check` 通过。暂存范围为本 unit 的 design、review、四份 delta 和 M1 骨架，与本轮输入说明一致。
- 现状、Runtime、真实入口、权限链、草稿恢复、提交、幂等、资源与 M1 的实质判断均 `retained_from: Round 1`：此次没有触及这些受审决定，无需重复 full 审查或新增实现验证。
- 本轮只追加本报告，不修改其他文件、不暂存、不提交、不执行产品实现或部署。

### 历史问题闭环

- 原 issue ID：无；Round 1 为 0 CRITICAL / 0 WARNING。
- Author Resolution：无实质修订，仅清理两份 delta EOF 多余空行。
- 本轮证据：两份最终 delta 全文复核及暂存 diff whitespace check。
- 状态：无未解决问题；收尾核对完成。

### Issues

无。

### Recommendations

无。

### Author Resolutions (Round 2)

- 已核实 closure 结论；无实质问题或建议，Gate 2 通过。最终受审 spec/design/delta/milestone 自本轮后不再修改。
- 文档 whitespace 检查通过；全仓 docs-check 的两处失败来自既有研究索引引用未跟踪目录，与本 unit 无关，未修改这些用户文件。

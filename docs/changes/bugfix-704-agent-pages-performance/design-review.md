## Round 1

- reviewer: Codex 独立设计审查
- target: bugfix-704-agent-pages-performance
- review_mode: full
- mode_reason: 首轮 Gate 2，覆盖全部需求与共享接口。
- started_at: 2026-11-03T16:08:00+08:00
- completed_at: 2026-11-03T16:13:00+08:00
- duration: 约 5 分钟
- verdict: **Issues Found — 0 CRITICAL / 4 WARNING**

### Coverage 与证据

阅读 incident、design、两份 delta、原型源文件及 current spec；核对 `apps/im-server/src/work.ts` 的产品路由和 `packages/dsh-integration/src/trajectory.ts`、`trajectory-stream.ts` 的实际组装与流实现。现有队列确有两批限制和五秒期限；follow 将 snapshot cursor 和 event seq 写入 observer，page 受该 cursor 限制，但现方案没有建立重接时的连续性契约。保留既有完整 Work 路由和在 adapter 内解决流控的职责方向合理；不需要 fork DSH 或第二套运行时。配置保存沿用已有版本及 operation 校验的方向合理。无一次性迁移；诊断不记录正文的边界合理。设计不改变 Agent 消费链，未触发完整 Context 审查。

原型独立渲染尝试被浏览器安全策略拒绝：本地 file URL 禁止访问，且策略明确禁止绕过。故未能独立观察画面、交互或窄屏，不将作者的走查当作独立通过；作者记录的桌面与 390×844 观察仅是作者证据。真实产品和真实网络性能均未由本轮验证。以下问题不依赖视觉判断。

### Issues

**R1-W1 — 轨迹恢复方案尚未闭合。** design 的关键决策 3 和接口部分将 live 背压能力、无游标情况下 snapshot 重接可行性留到实施时证明，却同时要求自动去重、无跳漏和保持位置。现有 `follow` 的 snapshot 是最多 500 条的窗口，`page` 以 observer cursor 作历史 cut；设计未说明重接前已展示边界与新 snapshot cut 如何衔接、覆盖窗口之外事件、处理瞬态 assistant stream 和 generation 变化，也未明确不能证明时的用户可见失败行为与资源闲置上限。实现者无法判断怎样满足不丢事实及有界资源，可能遗漏 burst 或重复记录。请先基于公开接口证明恢复算法及边界，或确定可诚实呈现的中断与手动恢复契约，并明确空闲清理规则。

**R1-W2 — Work 分层接口未定义可实施的数据形状。** design 只列身份、状态、计数等笼统字段，要求展开轮次首批过程但既有 `items` 路由返回完整 item，而又要求展开具体工具才传完整 payload；未指定轻量 items 的请求、响应、分页/游标及详情标识、非工具项正文和错误语义。直接复用旧 items 会再次下载大 payload，另行设计则会让实现者自行决定关键协议及前端展示。请明确摘要、过程列表与单项详情的各自形状和访问路径、分页、兼容与空/缺失语义，确保所有可见类型和旧客户端能力可达。

**R1-W3 — 必验双机公网资源尚未落实。** design 明确 Mini SSH 超时，独立公网 HTTPS/WSS 入口、测试身份及跨机启动清理命令均未建立或验证；runbook 把命令和入口留给 M1。用户要求的真实拓扑是退出条件，且技能要求必验资源在 Gate 2 前落实；目前不能确认环境可用或该验收可执行。请先核实 Mini 可达性、隔离测试入口与凭据来源，并提供可复查的启动、停止和健康检查；不可用时明确阻塞，不能以替代链路声称通过。

**R1-W4 — 原型验收证据和 must-match 约束不足。** design 只记桌面及单一窄屏状态，没有可复查截图，也没有覆盖窄屏配置、工作详情及关键恢复交互的走查证据；must-match 只写状态和结果，未明确具体信息层级、位置与交互关系。独立审查亦因上述浏览器策略阻止而无法完成实际画面判断。请补齐代表性可复查证据、覆盖受影响桌面/窄屏路径，写明关键布局与交互约束，并重新完成独立视觉走查；未观察内容保持未验证。

### Recommendations

无。

### Author Resolutions

- R1-W1 accepted：方案改为有界慢读和明确中断重试；未证实连续性时不声称无缝恢复，补充 snapshot、历史、瞬态事件、generation 和闲置释放边界。无损自动衔接仍不宣称已证明。
- R1-W2 accepted：补充 Work 摘要、轻量 items、完整 item 的路径、字段、游标、权限与错误语义；旧接口缺省行为不变。
- R1-W3 accepted, open：Mini 已连通且固定文字的临时 Cloudflare HTTP 探测成功并清理，但 WSS、隔离 IM、测试身份和真实启动清理命令尚未落实；公网业务验收未完成，不能视为通过。
- R1-W4 superseded：用户明确要求不做原型或界面改版，已移除原型；仅针对性能和故障相关的真实交互验收，不再将原型作为门槛。

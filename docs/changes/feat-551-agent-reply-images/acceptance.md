# feat-551 — 验收报告

> 对齐: [spec.md](spec.md) 的验收标准

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → 89986aa1a804f86cd569cd9ce5081015e085dd6f`

> Review round: 1 · 2026-09-10 · full revalidation

## Verdict

**pass**

**Highest Required Action: pass**

在从零重建的隔离 IM + Gateway、真实 Web IM desktop/mobile 视口及专用飞书测试用户/Bot 中，11 个 Scenario 均通过。两条 `must-match` 原型契约均以真实产品截图完成对照；未发现阻塞、major 或 minor 产品问题。

## 用户旅程体验

1. **内部 IM 主路径（R1-S1、R1-S2、R4-S1、R4-S2）**
   - 真实 Agent 用工具生成 480×240 与 240×360 两张 PNG，并在一个回复中按“前文 → 图 A → 中间文字 → 图 B → 后文”输出。1280×900 桌面视口分别显示为 320×160、240×360；390×844 移动视口保持 390px 页面宽度和原始比例，未出现横向溢出。
   - 图片放大后可审阅，按 Escape 关闭并把焦点还给原图片。纯图片回复没有增加无意义正文。
   - 延迟真实带认证图片 GET 时，已到达正文保持可读，图片原位显示 loading；中断 GET 时每张图片独立显示错误与 Retry。解除中断并点击 Retry 后，目标图片恢复，另一张失败图片不受影响。
   - 证据：`output/playwright/feat551-accept-r1/webim-desktop-two-images-ready.png`、`webim-mobile-two-images.png`、`webim-desktop-zoom.png`、`webim-desktop-pure-image.png`、`webim-desktop-retry-success.png`；loading/error 四张正式证据见 `M1-reply-images/evidence/web-im-{desktop,mobile}-{loading,error}.png`。

2. **飞书原聊天与内部影子会话（R2-S1、R2-S2）**
   - 专用飞书测试用户发送成功请求 `om_x100b651c2664b8b4b3f3a94b88071bd`。Bot 的真实运行信息卡片 `om_x100b651c271fc0b4b1c9d137baf5276` 依次显示“飞书成功前”、480×270 的 `FEISHU-R1-SUCCESS` 图片、“飞书成功后”和运行信息页脚；真实飞书客户端中可见并可放大。内部 IM 影子会话出现等价图文，blob 自然尺寸同为 480×270。准备阶段的中间可见说明也按既有规则出现在飞书与影子会话。
   - 随后从该影子会话内部入口请求生成 360×180 的 `SHADOW-INTERNAL-ONLY` 图片；Web IM 正常显示，而请求前后飞书最近消息 ID 集合完全相同，新增飞书消息数为 0。
   - 证据：上述飞书 message ID；`output/playwright/feat551-accept-r1/feishu-success-messages.json`、`feishu-before-shadow-internal.ids`、`feishu-after-shadow-internal.ids`、`webim-shadow-feishu-success.png`、`webim-shadow-internal-only.png`。

3. **失败、权限与会话切换边界（R4-S2、R4-S3、R5-S1、R5-S2）**
   - 飞书请求 `om_x100b651c324beca8b1b3154beff9384` 同时引用一张有效 exports 图片、一个不存在的 exports 文件和工作区外文件。Bot 卡片 `om_x100b651c33ea78a0b1ceaf16f8ce4` 按原顺序显示有效图片、两条“图片未能展示：图片来源不可用”及其余正文；失败说明未泄露完整路径，影子会话等价呈现。
   - Web IM 纯文字回复与代码围栏中的 `![CODE-EXAMPLE](/etc/passwd)` 均保持原文；代码示例没有变成图片或失败占位。
   - 对本次私有图片 URL，未带 Authorization 的 GET 返回 401；新注册的隔离第二测试用户携带其 Bearer token 返回 404；会话 owner 在浏览器中正常得到 200 并渲染 blob。
   - `/new` 边界额外实测：旧请求先进入 60 秒等待，约 2 秒后测试用户发送 `/new`；只收到确认 `om_x100b651cccb798b0b2aaaa93130a243`，继续等待超过 80 秒也没有 `FEISHU-R1-LATE` 晚发图片，影子会话一致。
   - 证据：上述飞书 message ID；`output/playwright/feat551-accept-r1/webim-shadow-feishu-partial-failure.png`、`webim-text-code.png`、`webim-shadow-new-ack.png`、`feishu-failure-messages.json`、`feishu-new-after-wait.json`。

4. **持久回看与离线恢复（R3-S1、R3-S2）**
   - 先停止隔离 IM，Gateway 保持运行。飞书请求 `om_x100b651cc2e118a4b04ce0cebfd6ec3` 仍收到 Bot 卡片 `om_x100b651cc38678b0b27b93af419ed00`，其中 400×220 的 `FEISHU-IM-OFFLINE` 图片位于“离线前”和“离线后”之间。恢复同一隔离 IM 数据后，重新登录 Web IM，影子会话只出现一张对应图片和一份气泡内容。
   - 将原始 `feishu-im-offline-400x220.png` 移离原路径后停止隔离 Gateway，再刷新影子会话。图片仍以 400×220 blob 完整显示；浏览器读取到的 SHA-256 `062f232912c2da9c33b0ec1cf9f3526ceeb022c6f12ab6ed2ae0bfcd75c8e843` 与移动前源文件完全相同。
   - 证据：上述飞书 message ID；`output/playwright/feat551-accept-r1/webim-shadow-after-im-recovery.png`、`webim-shadow-source-moved-gateway-offline.png`、`feishu-im-offline-messages.json`。

### 验收环境与启动可信度

- 工作目录：`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-551`，分支 `unit/feat-551`，验收前 HEAD 与 `validated_at` 一致。
- 按 runbook 停止旧隔离栈、重新构建前端并启动本 worktree 的隔离 IM + Gateway；IM 端口为 60712，未触碰生产 `:8011`、ref-550 或已停止的 feat-546 测试栈。
- IM 实际托管的 `index-Bv5mGb_t.js` 与本轮 build 产物 SHA-256 相同，且包含本 unit 的图片加载、错误和 Retry 标记；Feishu probe 在业务旅程前通过。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html#reply` ready/zoom；`prototype-desktop-zoom.png`、`prototype-mobile-ready.png` | 图文顺序、成功图片、保持比例、移动适配与放大 must-match | `webim-desktop-two-images-ready.png`、`webim-mobile-two-images.png`、`webim-desktop-zoom.png`、`webim-desktop-pure-image.png` | 1280×900 / 390×844；ready、zoom、pure-image | **match**：顺序、气泡内宽度约束、原始比例、移动无溢出、放大和纯图片形态均与原型契约一致；正式主题按 may-adapt 保留。 |
| `prototype.html#reply` pending/error；`prototype-desktop-loading.png`、`prototype-desktop-error.png` | pending/error 必须在图片引用原位展示，正文可读，desktop/mobile must-match | `M1-reply-images/evidence/web-im-desktop-loading.png`、`web-im-mobile-loading.png`、`web-im-desktop-error.png`、`web-im-mobile-error.png`；Retry 现场证据 `output/playwright/feat551-accept-r1/webim-desktop-retry-success.png` | 1280×900 / 390×844；loading、error、retry-success | **match**：状态留在原引用位置，正文不被遮挡；错误可独立重试，未出现本机路径或破图图标。 |

pending/error 四张正式证据位于 `M1-reply-images/evidence/`；其余 Round 1 reference 与实际产品现场证据位于 `output/playwright/feat551-accept-r1/`。原型状态选择器和示例图按 design 明确为 out-of-scope，未要求进入正式产品。

## 问题清单

无。

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| — | — | 未发现问题 | — | pass | 11 个必验 Scenario 与两条 must-match 原型契约全部通过。 |

## 验收标准覆盖

### Requirement: 当前会话能够接收 Agent 图文回复 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R1-S1 跨机器查看本地截图 | `spec.md` R1-S1；`prototype.html#reply` ready must-match | 真实 Agent 工具生成两种尺寸 PNG；Web IM 1280px/390px 视口显示 | `webim-desktop-two-images-ready.png`、`webim-mobile-two-images.png`；自然尺寸与页面宽度实测 | pass | 两端保持比例，无需浏览器访问 Agent workspace 或手工上传。 |
| R1-S2 保持图文顺序与纯图片回复 | `spec.md` R1-S2；`prototype.html#reply` ready/zoom must-match | 同一回复验证两图及三段正文顺序；另发纯图片回复并放大、Escape 关闭 | `webim-desktop-two-images-ready.png`、`webim-desktop-pure-image.png`、`webim-desktop-zoom.png` | pass | 每个引用位置一次；纯图片无额外无意义正文，焦点可恢复。 |

### Requirement: 飞书和内部 IM 保持既有路由与呈现规则 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R2-S1 飞书原聊天与影子会话 | `spec.md` R2-S1；`specs/gateway/routing-delivery.md` | 专用飞书测试用户真实请求；原聊天、运行信息卡片、可见中间说明与影子会话对照；客户端放大图片 | Feishu `om_x100b651c271fc0b4b1c9d137baf5276`；`feishu-success-messages.json`；`webim-shadow-feishu-success.png` | pass | 最终图文顺序和 480×270 图片等价；页脚与正文共处同一卡片，中间普通 Post 沿原聊天投递。 |
| R2-S2 影子会话内部入口不回写飞书 | `spec.md` R2-S2 | 在飞书影子会话从 Web IM 请求图片；比较操作前后飞书最近 20 条 ID 集合 | `webim-shadow-internal-only.png`；`feishu-before-shadow-internal.ids`、`feishu-after-shadow-internal.ids` | pass | Web IM 新增 360×180 图片；飞书新增消息数 0。 |

### Requirement: 已交付图片稳定可回看 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R3-S1 历史不依赖原文件和节点在线 | `spec.md` R3-S1；`specs/im/conversations-messages.md` | 移离原文件、停止隔离 Gateway，再刷新影子会话；比较源文件与浏览器 blob SHA-256 | `webim-shadow-source-moved-gateway-offline.png`；SHA-256 均为 `062f2329…8e843` | pass | 图片仍为 400×220，交付字节不依赖源路径或节点在线。 |
| R3-S2 IM 暂不可用时飞书继续工作 | `spec.md` R3-S2；`specs/gateway/routing-delivery.md` | 停 IM、从飞书真实请求图片、恢复 IM、重新登录检查影子历史及重复数 | Feishu `om_x100b651cc38678b0b27b93af419ed00`；`webim-shadow-after-im-recovery.png`；`feishu-im-offline-messages.json` | pass | 飞书先收到；恢复后 Web IM 仅一张对应图片、无重复气泡。 |

### Requirement: 图片准备和失败不破坏正文 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R4-S1 图片加载过程 | `spec.md` R4-S1；`prototype.html#reply` pending must-match | 对真实认证图片 GET 加延迟，分别在 desktop/mobile 观察正文和图片原位状态 | `M1-reply-images/evidence/web-im-desktop-loading.png`、`web-im-mobile-loading.png` | pass | 正文先可读；无本机路径或破图图标，随后进入 ready。 |
| R4-S2 单图失败或超限 | `spec.md` R4-S2；`prototype.html#reply` error must-match | 真实 Agent 同时引用有效、缺失和工作区外来源；另在浏览器中断两张图片 GET 并逐张 Retry | Feishu `om_x100b651c33ea78a0b1ceaf16f8ce4`；`M1-reply-images/evidence/web-im-desktop-error.png`、`web-im-mobile-error.png`；`output/playwright/feat551-accept-r1/webim-desktop-retry-success.png` | pass | 可用图片与正文继续；两处失败原位可读且无完整路径；无无限 loading。 |
| R4-S3 原有消息行为不回归 | `spec.md` R4-S3 | Web IM 请求纯文字并把 Markdown 图片语法放入代码围栏 | `webim-text-code.png` | pass | 文字正常；代码原样显示，未发起图片或生成失败占位。 |

### Requirement: 图片遵循会话访问范围与文件权限 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R5-S1 私密图片不可通过地址越权查看 | `spec.md` R5-S1；`design.md` 私有 GET 契约 | 同一真实图片 URL 分别以 owner 浏览器、无 Authorization、隔离第二用户 Bearer 访问 | owner 200 并渲染 blob；无认证 401；跨 owner 404 | pass | 地址本身不授予读取权限。 |
| R5-S2 图片语法不能额外取得文件权限 | `spec.md` R5-S2；`design.md` exports 来源边界 | 真实 Agent 回复引用缺失 exports 文件和 `/etc/passwd`，未把外部文件复制进 exports | Feishu `om_x100b651c33ea78a0b1ceaf16f8ce4`；`webim-shadow-feishu-partial-failure.png` | pass | 两者均未展示/发送；assistant 失败说明不包含完整路径。用户请求中自行写出的路径不计为回复泄漏。 |

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 没有改变跨包依赖方向或系统顶点职责。
- [x] `docs/specs/gateway/`、`docs/specs/im/`（长青行为契约层）：**需要更新**。当前 unit 已提供 `specs/gateway/routing-delivery.md`、`specs/im/web-chat-ux.md`、`specs/im/conversations-messages.md` 三份 delta；应由 orchestrator 在最终实现校正后归并 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。本 unit 不改变仓库协作规则或 Agent 约定。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：**无需更新**。本 unit 未修改文档体系。

> 长青契约层的写回是 orchestrator 根据最终实现校正 delta-spec 并归并 canonical 的职责；本报告不改写契约层。

---

# Round 2 — 2026-09-10

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → b147c61698852879d16fba105c56c99a5ea6e1db`

> Mode: Fast-lane targeted revalidation

> Focus: R4-S1 pending state；R4-S2 per-image error 与稳定失败说明；可持久引用的 reference 证据路径

## Verdict

**pass**

**Highest Required Action: pass**

R4-S1、R4-S2 在当前 validated head 上保持通过；Round 1 其余 9 个 Scenario 均继承 `pass`。本轮没有上一轮 `fail` / `inconclusive` 项需要关闭，也未观察到新的同屏副作用。

## Fast-lane 定向旅程

1. **当前 head 的 public limit/type 失败旅程**
   - 仅启动隔离、非飞书的 IM + Gateway，在真实 Web IM 1280×900 视口中让 Agent 按 `ROUND2-LIMIT-TYPE-START → 15,483,160-byte 公网 JPEG → ROUND2-LIMIT-TYPE-MIDDLE → image/svg+xml 公网 SVG → ROUND2-LIMIT-TYPE-END` 输出；两个来源均在旅程前确认可访问。
   - 回复准备期间，两张图片各自在原引用位置显示 `Image loading…`，前、中、后正文已经可读。26.7 秒后，大图收敛为 `（图片未能展示：超过图片数量或大小限制）`，不支持类型收敛为 `（图片未能展示：图片来源不可用）`；正文顺序不变，没有破图、路径泄漏或“已经发送”的误导表述。
   - 完整刷新页面后，最终段落仍逐字保持这两处失败说明，且 `loadingCount=0`、`imgCount=0`；说明不是无限 pending，也不会因 reload 丢失或改变失败结果。
   - 本轮现场证据：`output/playwright/feat551-accept-r2/web-im-limit-type-final-reload.png`。

2. **Round 1 pending/error 证据持久化核验**
   - 逐张重新目视检查 unit 内四张正式证据；desktop 为 1280×900，mobile 为 390×844。loading 与 error 均在两个图片引用原位，周围正文持续可读；error 有独立 Retry，未显示本机路径或破图。
   - 四张 unit 证据与 Round 1 实际验收截图逐一进行 SHA-256 对照，全部字节完全一致。因而下表中的 unit 路径正式替代 Round 1 临时 `output/` 路径，作为 pending/error must-match 的长期证据。

## Reference Artifacts Reviewed

| Reference | Required contract | Durable actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html#reply` pending | R4-S1：正文可读，图片原位 pending，desktop/mobile must-match | `M1-reply-images/evidence/web-im-desktop-loading.png`（SHA-256 `c733b7d6…91849`）；`M1-reply-images/evidence/web-im-mobile-loading.png`（`fa6da24e…7d24c5`） | 1280×900 / 390×844；loading | **match**：两张图片均原位 loading，前/中/后正文持续可读；两文件分别与 Round 1 原始验收截图字节一致。 |
| `prototype.html#reply` error | R4-S2：失败原位可读、正文继续、可独立 Retry，desktop/mobile must-match | `M1-reply-images/evidence/web-im-desktop-error.png`（SHA-256 `549b22c2…000ad`）；`M1-reply-images/evidence/web-im-mobile-error.png`（`f27f58ab…0a8b4`） | 1280×900 / 390×844；error | **match**：两处失败均在各自引用位置，Retry 独立可见，正文未丢失；两文件分别与 Round 1 原始验收截图字节一致。 |

上述相对路径均位于 `docs/changes/feat-551-agent-reply-images/`，随 unit 提交并可持久引用。Round 1 的 ready/zoom must-match 未受本次 delta 影响，继续继承通过。

## 问题清单

无。

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| — | — | 未发现问题 | — | pass | 两个 focus Scenario 在当前 head 上通过，四张 reference 证据已有稳定 unit 路径。 |

## 验收标准覆盖（Fast-lane 更新）

### Requirement: 图片准备和失败不破坏正文 — 定向组结论: pass

| Scenario | 期望来源 | 本轮验证方式 | 本轮证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R4-S1 图片加载过程 | `spec.md` R4-S1；`prototype.html#reply` pending must-match | 当前 head 真实 Web IM 观察两张公网图片从 pending 收敛；重新目视检查 desktop/mobile durable evidence | `M1-reply-images/evidence/web-im-desktop-loading.png`、`M1-reply-images/evidence/web-im-mobile-loading.png`；Round 2 现场 loading 截图 | pass | 正文先可读，两个位置独立 loading；随后都进入明确失败状态。 |
| R4-S2 单图失败或超限 | `spec.md` R4-S2；`prototype.html#reply` error must-match | 当前 head 引用 15,483,160-byte JPEG 与不支持类型 SVG；观察分类后的最终失败并刷新复核稳定性 | `M1-reply-images/evidence/web-im-desktop-error.png`、`M1-reply-images/evidence/web-im-mobile-error.png`；Round 2 `web-im-limit-type-final-reload.png` | pass | 大图与不支持类型分别得到稳定、可读的限制/来源失败说明，正文继续；reload 后无 loading 或破图。 |

### Round 1 其余覆盖继承

R1-S1、R1-S2、R2-S1、R2-S2、R3-S1、R3-S2、R4-S3、R5-S1、R5-S2 均继承 Round 1 的 `pass`。本次 fix delta 未触及这些已验用户旅程，也没有上一轮失败或存疑结论需要重跑。

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`：**无需更新**；Round 1 结论不变。
- [x] `docs/specs/gateway/`、`docs/specs/im/`：**需要更新**；继续由 orchestrator 将 unit delta 归并 canonical，本轮没有新增产品契约。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

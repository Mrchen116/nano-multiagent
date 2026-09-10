# Verification Report: feat-551

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → 89986aa1a804f86cd569cd9ce5081015e085dd6f`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 0/1 M1 fully evidenced |
| Correctness | 7/11 scenarios fully proven |
| Coherence | 有偏离 |

## Completeness

- Tasks: N/A；M1 没有 `tasks.md`，按 design 退出标准直接核对。
- Milestone: 0/1 fully evidenced。代码、专项测试、真实 Web IM/Feishu 主旅程与 ready/zoom 原型对照已存在，但 pending/error 的 must-match 要求没有按 desktop/mobile 和 loading/error 完整留存可复查证据（V1-C1）。
- Spec 覆盖: 5/5 Requirement 均有实现；11 个 Scenario 中 7 个具有完整实现+回归证据，R1-S1、R4-S2、R4-S3 及 design 的 provider-receipt 退出项存在偏离或测试缺口。
- Current-snapshot checks: 受影响 Python 测试 193/193 通过；架构契约 7/7 通过；前端 `message-image` 6/6 通过；前端 production build、Ruff、`git diff --check` 和 docs-check 通过。前端命令在同一 `89986aa` 实施 worktree 中复用已安装 lockfile 依赖运行；未安装或修改依赖。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| R1-S1 跨机器查看本地截图 | `src/personal_assistant/gateway/reply_images.py:78-120,158-234`; `src/personal_assistant/gateway/composition.py:328-423`; `src/IM/frontend/src/features/chat/components/message-image.tsx:46-105` | PNG 真实旅程与快照回归已有；IM API 有 JPEG/WebP，但 Gateway 本地 JPEG/WebP 分支无永久回归 | partial (V1-W2) |
| R1-S2 保持图文顺序与纯图片回复 | `src/personal_assistant/gateway/reply_images.py:168-214,244-261`; `src/IM/frontend/src/features/chat/components/message-image.tsx:28-105` | `tests/unit/personal_assistant/test_reply_images.py:18-30`; `src/IM/frontend/src/features/chat/components/message-image.test.tsx:48-87` | covered |
| R2-S1 飞书原聊天与影子会话 | `src/personal_assistant/gateway/runtime_delivery/observer.py:316-380`; `src/personal_assistant/channels/feishu/adapter.py:211-298`; `src/personal_assistant/gateway/shadow_sync.py:314-384,430-501` | `tests/unit/test_feishu_adapter_send.py:250-329`; `tests/integration/test_shadow_reply_images.py:74-263`; `M1-reply-images/progress.md:49-56` | covered |
| R2-S2 影子会话内部入口不回写飞书 | `src/personal_assistant/gateway/runtime_delivery/observer.py:260-284`; `src/personal_assistant/gateway/runtime_delivery/image_connection.py:73-148` | `tests/unit/personal_assistant/test_external_visible_delivery.py:600-634`; `tests/unit/personal_assistant/test_im_reply_image_delivery.py:48-108` | covered |
| R3-S1 历史不依赖原文件和节点在线 | `src/personal_assistant/gateway/reply_images.py:123-157,195-234,236-242`; `src/IM/infra/repositories/message_images.py:34-127` | `tests/unit/personal_assistant/test_reply_images.py:18-30`; `tests/im_service/integration/test_message_images_api.py:42-84`; `M1-reply-images/evidence/web-im-gateway-offline.png` | covered |
| R3-S2 IM 暂不可用时飞书继续工作 | `src/personal_assistant/gateway/shadow_sync.py:314-384,478-540`; `src/personal_assistant/gateway/shadow_saga.py` | `tests/integration/test_shadow_reply_images.py:146-263`; `tests/unit/personal_assistant/test_inbound_pipeline_session.py:863-948` | covered |
| R4-S1 图片加载过程 | `src/personal_assistant/gateway/reply_image_stream.py:13-115`; `src/personal_assistant/gateway/runtime_delivery/image_connection.py:73-129`; `src/IM/frontend/src/features/chat/components/message-image.tsx:32-86` | parser/IM-frame/frontend 永久回归已有；原型指定的跨 viewport 持久证据不完整 | code covered; evidence incomplete (V1-C1) |
| R4-S2 单图失败或超限 | `src/personal_assistant/gateway/reply_images.py:64-75,168-210`; `src/personal_assistant/channels/feishu/adapter.py:211-298` | 丢失/越界/本地格式/第六来源/provider 部分失败已测；本地 10 MiB 无回归，公网/data 格式或超限原因会被误折叠为 source | 偏离 (V1-W1, V1-W2) |
| R4-S3 原有消息行为不回归 | `src/personal_assistant/gateway/reply_images.py:181-194`; `src/personal_assistant/gateway/reply_image_stream.py:42-115`; inbound 链路未改 | 旧 Feishu client 有 public/data/code 回归，新 `ReplyImages.prepare` public/data 接线无永久回归 | partial (V1-W2) |
| R5-S1 私密图片不可通过地址越权查看 | `src/IM/api/routes/message_images.py:19-27,41-117`; `src/IM/infra/repositories/message_images.py:34-167` | `tests/im_service/integration/test_message_images_api.py:42-84,127-197` | covered |
| R5-S2 图片语法不能额外取得文件权限 | `src/personal_assistant/gateway/reply_images.py:78-120`; `src/personal_assistant/product.py:356-382` | `tests/unit/personal_assistant/test_reply_images.py:33-58`; `tests/integration/test_personal_assistant_prompt_integration.py:68-81` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. Markdown 引用 + `.nanoassistant/exports/` 可交付边界 | 是 | `src/personal_assistant/product.py:356-382`; `src/personal_assistant/gateway/reply_images.py:78-120` |
| 2. 一个 ReplyImages module，IM/Feishu 两个真实 adapter | 是 | `src/personal_assistant/gateway/reply_images.py:123-363`; `src/personal_assistant/channels/feishu/adapter.py:211-298`; `src/IM/api/routes/message_images.py:41-117` |
| 3. 快照先于发送，output_key 与 shadow 恢复复用同一资源 | 是，但缺回执重入退出测试 | `src/personal_assistant/gateway/reply_images.py:158-234,270-313`; `src/personal_assistant/gateway/shadow_sync.py:478-501` |
| 4. IM 新图片是会话私有资源，fork 重绑 | 是 | `src/IM/api/routes/message_images.py:41-117`; `src/IM/infra/repositories/message_images.py:129-167`; `src/IM/application/web_im_service.py:475-501` |
| 5. 单图局部失败，prepare/receipt/admission/publish 两阶段，`/new` 只 drain admitted | 部分 | `src/personal_assistant/gateway/composition.py:345-445,852-931`; `src/personal_assistant/gateway/session_run_coordinator.py:735-765`; public/data 失败原因偏离见 V1-W1 |
| 6. 复用气泡，私有图 authFetch，blob/account 生命周期与放大 | 是 | `src/IM/frontend/src/features/chat/components/message-image.tsx:9-105`; `src/IM/frontend/src/features/chat/components/message-pane.tsx:1739-1826`; `src/IM/frontend/src/styles/global.css:2488-2561` |

架构自洽性通过：IM 没有 import `agent`/`personal_assistant`，Gateway 仅通过 HTTP/WS 向 IM 交付 bytes/URL；`personal_assistant` 的 agent 依赖继续只走 `agent.sdk`；没有新建图片 HTTP server 或第二聊天投递状态机。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| `#reply` 图文顺序、成功图片与放大；1280px/390px ready | M1 / R1-S1, R1-S2（`design.md:225-229,267-269`） | `message-image.tsx:89-105`; `global.css:2488-2561` | `M1-reply-images/evidence/web-im-1280.png`; `web-im-390.png`; `web-im-zoom.png`; progress `:42-45` 有尺寸/比例/焦点对照结论 | covered |
| `#reply` pending/error 原位状态；desktop/mobile loading/error | M1 / R4-S1, R4-S2（`design.md:225-229,267-269`） | `message-image.tsx:32-42,46-86`; DOM 测试 `message-image.test.tsx:48-87` | `web-im-feishu-partial-failure.png` 只记录 1280px error；无 loading 截图，无 390px loading/error 截图，progress `:45-47` 也未声明这些组合 | critical (V1-C1) |

## Issues

### CRITICAL（提 PR 前必须修）

- [V1-C1] **M1 尚无法证明 pending/error must-match 在 desktop/mobile 全部成立。** `docs/changes/feat-551-agent-reply-images/design.md:225-229` 明确要求该行在 desktop/mobile 的 loading/error 状态必验，M1 退出标准 `design.md:267-269` 又要求两条 must-match 在 desktop/mobile 成立并保留真浏览器截图。当前 `M1-reply-images/progress.md:42-47` 与 evidence 只完整留下 ready/zoom 两个 viewport，另有一张 1280px 部分失败图；没有 loading 状态、也没有 390px 的 loading/error 证据。请在真实 Web IM 中以可控延迟保留 desktop 1280px 与 mobile 390px 的 loading 原位截图，再保留两个 viewport 的 error 原位截图；在 progress 逐项记录与 `prototype.html#reply` 的顺序、宽度/无溢出、状态替换对照结论。

### WARNING（提 PR 前必须修）

- [V1-W1] **公网/data 图片的格式与大小失败丢失了真实原因，偏离 R4-S2 和 design 决策 5。** `src/personal_assistant/gateway/reply_images.py:181-188` 复用 safe reader，但 `:203-207` 只将异常文字恰好等于 `limit`/`type` 时保留分类；`read_outbound_image` 在 `src/personal_assistant/channels/feishu/client.py:1024-1055,1120-1140` 抛出的是带描述的 ValueError，因此超过 10 MiB 或非支持 raster 都被折叠为 `source`，用户只看到“图片来源不可用”。请让 safe reader 向 ReplyImages 返回/抛出稳定的 `limit` 与 `type` 类别（或在共享边界做明确映射），保持安全的不含 URL/路径文案；增加 public/data 超限与格式失败回归，断言正文/其他图不受影响且原因分类正确。
- [V1-W2] **`ReplyImages` 的永久边界测试没有完成 spec/design 明列矩阵。** `tests/unit/personal_assistant/test_reply_images.py:18-109` 只有 PNG 正向、目录/最终符号链接/格式失败、第六来源和 parser；没有本地 JPEG/WebP 正向、本地 10 MiB 边界、无读权限/父目录符号链接，也没有新 `ReplyImages.prepare` 的 public/data 正向。旧 `test_feishu_rich_messages.py` 验证的是旧 client 复合路径，不会经过现在的 `reply_images.py:181-194`。请在该测试文件补齐这些显式分支：10 MiB 精确边界和 >10 MiB 局部失败，JPEG/WebP 快照，父目录 symlink/权限拒绝，以及 mocked HTTPS 或 data 来源经新 module 固定快照。
- [V1-W3] **provider 上传回执的“公开发送失败后重入复用”退出标准没有永久回归。** design 在 `docs/changes/feat-551-agent-reply-images/design.md:90-100,207-213` 要求部分上传成功先于公开发送落盘，聊天发送失败后重入复用 key。`tests/unit/personal_assistant/test_outbound_image_delivery.py:41-84` 只证明 router 在 publish 前调用一个列表 callback；`tests/unit/test_feishu_adapter_send.py:250-329` 只证明 adapter 会复用输入的 `img_existing`；没有测试 `ReplyImages.record_provider_receipts` / restart load / `outbound_images` 这条真实持久化链。请增加一个跨 ReplyImages+router/adapter 边界的失败重入测试：第一次部分 upload 成功、公开 send 失败，重建 ReplyImages 后同 output_key 继续时不再上传已有 key，且不同 App ID 不复用它。

### SUGGESTION（可以修）

无。

1 critical issue(s), 3 warning(s) found. Fix before PR.

# Round 2

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → b147c61698852879d16fba105c56c99a5ea6e1db`

## Summary

Mode: targeted-closure
Delta range: `89986aa1a804f86cd569cd9ce5081015e085dd6f..b147c61698852879d16fba105c56c99a5ea6e1db`
Focus issues: V1-C1, V1-W1, V1-W2, V1-W3
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 0/1 M1 fully evidenced and matched |
| Correctness | 3/4 focus issues closed |
| Coherence | 1 related deviation remains |

## Targeted Closure

| Focus issue | Delta evidence | Verification | Status |
|---|---|---|---|
| V1-C1 pending/error desktop/mobile 持久证据 | 新增 `web-im-{desktop,mobile}-{loading,error}.png`；`M1-reply-images/progress.md:48` 链接四张图 | 四张文件与 Round 1 acceptance 原始产物 SHA-256 逐一相同，尺寸为 1280×900 / 390×844；desktop 的 loading/error 均在原位且正文可读。但两张 mobile 图均显示水平滚动条，320px 状态卡越出 Agent 气泡右边界，不符合 `prototype.html#reply` 的同一气泡结构及 `design.md:213,226-230` 的移动端无溢出约束 | **open (CRITICAL)** |
| V1-W1 public/data 大小与格式失败分类 | `client.py:1009-1019,1038-1075,1096-1162`; `reply_images.py:181-213`; `test_reply_image_public_sources.py:26-78` | `OutboundImageReadError` 仍是 `ValueError`，直接 probe 确认 `limit` / `type` 的稳定属性与旧人类可读异常文本均不变；data 与 mocked HTTPS 的 ready/limit/type 六个分支均断言好图/正文保留。安全解析、公网 IP 判定、连接地址钉扎和超时代码未改，对应既有安全回归通过 | **closed** |
| V1-W2 ReplyImages 永久边界矩阵 | `test_reply_images.py:39-104`; `test_reply_image_public_sources.py:26-78` | 本地 JPEG/WebP、10 MiB 精确边界与超限、无读权限文件和父目录 symlink，以及 data/mocked HTTPS 的成功快照均在长期 unit 套件中经过真实 `ReplyImages.prepare` seam | **closed** |
| V1-W3 provider 回执在失败公开发送后重入复用 | `test_outbound_image_delivery.py:94-174`; `reply_images.py:274-317`; `outbound_router.py:156-206` | 测试跨 `ReplyImages` + `OutboundRouter` + provider seam：回执先持久，公开 send 再失败；删除原图并重建 store 后同 App 不重传，不同 App 单独上传 | **closed** |

## Validation

- Focused permanent suite: **46 passed** (`test_reply_images.py`, `test_reply_image_public_sources.py`, `test_outbound_image_delivery.py`, `test_feishu_rich_messages.py`, `test_feishu_adapter_send.py`).
- Downloader security plus architecture contracts: **7 passed**; typed-error direct probe confirmed stable codes and unchanged exception text.
- Changed Python files: Ruff check and Ruff format check passed.
- Fix commit `b147c6169^..b147c6169`: `git diff --check` passed.
- Visual evidence: all four committed screenshots inspected at original resolution and matched byte-for-byte with the acceptance run originals.

## Issues

### CRITICAL（提 PR 前必须修）

- [V1-C1] **desktop 证据已补齐，但 mobile loading/error 证据显示状态卡和页面横向溢出，因而 must-match 仍未成立。** `docs/changes/feat-551-agent-reply-images/M1-reply-images/evidence/web-im-mobile-loading.png` 与 `web-im-mobile-error.png` 中都可见页面底部水平滚动条，状态卡从气泡内部延伸到浅色气泡右侧之外。对应 CSS 在 `src/IM/frontend/src/styles/global.css:1975-1980,2012-2025,2510-2519` 同时给外层 Agent 气泡 `max-width: 72%` 和状态卡 `width: 320px; max-width: 100%`，而 ready 图片的 390px 证据没有该水平滚动条。请将 loading/error 状态卡约束在实际 `chat-bubble-card` / Markdown content 可用宽度内；在真浏览器 390px 复验状态卡 bounding rect 不超过气泡且页面/聊天滚动容器 `scrollWidth === clientWidth`，再更新两张 mobile 证据与 `M1-reply-images/progress.md:48` 的对照结论。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

无。

1 critical issue(s), 0 warning(s) found. Fix before PR.

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

# Round 3

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → d79a82d78dbe403438ac206c450ab9b98f56f2b1`

## Summary

Mode: targeted-closure (Fast-lane)
Delta range: `fbf9415dac41fb430dac9ea3c389368b87faa6de..d79a82d78dbe403438ac206c450ab9b98f56f2b1`
Focus issues: V1-C1
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 M1 fully evidenced and matched |
| Correctness | 1/1 focus issue closed |
| Coherence | Followed |

## Targeted Closure

| Focus issue | Implementation and evidence | Verification | Status |
|---|---|---|---|
| V1-C1 mobile pending/error 气泡边界与水平溢出 | `src/IM/frontend/src/styles/global.css:2307-2317,2516-2528`; `M1-reply-images/progress.md:48-49`; `acceptance.md:189-251`; `M1-reply-images/evidence/web-im-mobile-{loading,error}.png` | `4862b53f6` 将 `.im-md` 直接 grid item 的自动最小宽度降为 `0`，使状态块既有 `max-width: 100%` 按真实气泡内宽收缩。两张新证据均为原始 390×844，SHA-256 分别为 `6bed79ae…8c07ac` / `85d3b684…cb488`；原像素目视显示两个状态位于同一 Agent 气泡内，无底部水平滚动条。Acceptance 实测 loading 的 state/card 为 `x=65,width=256.078` / `x=52,width=282.078`，error 为 `x=65,width=250.797` / `x=52,width=276.797`；左右边界均被 card 包含。消息滚动区 loading `390/390`、error `384/384`，根文档均 `390/390` (`clientWidth/scrollWidth`) | **closed** |

## Validation

- Frontend focused suites: **99 passed** (`message-image.test.tsx`, `message-pane.test.tsx`). The commands reused the already-installed lockfile dependencies in the implementation worktree at the exact same `d79a82d78` tree because the detached verifier worktree has no `node_modules`; no dependencies were installed or changed.
- Frontend production build passed on that same tree: 509 modules transformed; emitted `index-yMRqOR1_.js`, matching the asset recorded by the real-product acceptance run.
- Documentation integrity passed: 242 maintained Markdown sources and 70 required routes.
- `4862b53f6^..4862b53f6` and the current worktree passed `git diff --check`.
- Both durable screenshots were inspected at original resolution; recorded dimensions and full SHA-256 hashes match the checked-in files.

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

无。

All checks passed. Ready for PR.

## Corrected Delta Reconciliation

> Validation snapshot: `6ec610be5d43a085a44c80518150dd91cafa61bd → 320bc117e8450b0d35c7a7cf4ff586f409989a07`

Mode: corrected-delta

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/routing-delivery.md` Requirement: 当前会话的 Agent 图片回复具有统一交付语义 | `src/personal_assistant/product.py:356-382`; `src/personal_assistant/gateway/reply_images.py:78-120,158-238,248-367`; `src/personal_assistant/gateway/composition.py:322-425` | `tests/integration/test_personal_assistant_prompt_integration.py:68-81`; `tests/unit/personal_assistant/test_reply_images.py:24-184`; `tests/unit/personal_assistant/test_reply_image_public_sources.py:26-78` | aligned |
| gateway Scenario: 本地产物跨机器查看 | Gateway 先在持久 state 中固定 bytes，再经 IM 私有 URL 或 Feishu image key 投影：`reply_images.py:158-238,319-367`; `src/IM/api/routes/message_images.py:41-117`; `src/personal_assistant/channels/feishu/adapter.py:211-298` | `test_reply_images.py:24-56`; `tests/im_service/integration/test_message_images_api.py:42-84`; `M1-reply-images/evidence/web-im-{1280,390,gateway-offline}.png`; Feishu request `om_x100b6513bf9ff8a0b283de3b6cf5e87` | aligned |
| gateway Scenario: 图片语法不绕过权限 | 只用 directory descriptor + `O_NOFOLLOW` 读取 workspace `.nanoassistant/exports/` 中的普通文件：`reply_images.py:78-120`; 产品提示要求先经既有受控工具复制：`product.py:356-382` | `test_reply_images.py:84-132`; `test_personal_assistant_prompt_integration.py:68-81` | aligned |
| gateway Scenario: 图文投递保持入口路由 | external-triggered 气泡保留原 channel metadata 并同时进入 provider/shadow，`trigger_source=im` 则不组造外部投影：`src/personal_assistant/gateway/runtime_delivery/observer.py:260-380`; `src/personal_assistant/gateway/shadow_sync.py:430-501`; Post/card 共用 `adapter.py:239-298` | `tests/integration/test_shadow_reply_images.py:74-263`; `tests/unit/personal_assistant/test_external_visible_delivery.py:600-634`; `tests/unit/test_feishu_adapter_send.py:250-329` | aligned |
| gateway Scenario: IM 离线不阻塞飞书图片 | provider 投递不依赖 IM；shadow output 保留 `output_key`，恢复时从 Gateway 快照上传私有资源后幂等写回原气泡：`reply_images.py:274-367`; `shadow_saga.py:96-167`; `shadow_sync.py:430-540` | `test_shadow_reply_images.py:146-263`; `M1-reply-images/progress.md:53-58` | aligned |
| gateway Scenario: 局部图片失败 | prepare 为每个 ordinal 保留 `limit/type/source/missing/upload` 局部结果，Feishu prepare 逐图上传并保留部分成功回执：`reply_images.py:64-75,168-238,274-317`; `adapter.py:211-298` | `test_reply_images.py:59-184`; `test_reply_image_public_sources.py:26-78`; `test_feishu_adapter_send.py:250-329`; Feishu request `om_x100b6513b96924b8b2c08d7c59339df` | aligned |
| gateway Scenario: 普通文本和示例保持原语义 | 共用流式/完整 Markdown 解析器仅处理 code/escape 之外的 inline image：`src/personal_assistant/gateway/reply_image_stream.py:13-115`; 无图回复保留原文：`reply_images.py:216-238` | `tests/unit/personal_assistant/test_reply_image_stream.py:9-77`; `test_reply_images.py:135-184`; `src/IM/frontend/src/features/chat/components/message-image.test.tsx:119-127` | aligned |
| `specs/im/conversations-messages.md` Requirement: Agent 新托管图片按会话保护且稳定可回看 | 新 `message_images` 表和独立私有存储与旧 `/im/uploads` 分离，POST/GET 先做会话 owner 校验：`src/IM/infra/db.py:158-169`; `src/IM/infra/repositories/message_images.py:34-127`; `src/IM/api/routes/message_images.py:19-117`; `src/IM/app.py:286-289,438-441` | `tests/im_service/integration/test_message_images_api.py:42-124` | aligned |
| IM Scenario: 已交付图片持久回看 | IM 持久不可变 bytes/metadata，正文只存稳定相对 URL：`message_images.py:57-127`; Gateway 原图删除后不再重读：`reply_images.py:144-157,240-246` | `test_message_images_api.py:42-84`; `test_reply_images.py:24-36`; `M1-reply-images/evidence/web-im-gateway-offline.png` | aligned |
| IM Scenario: 地址不授予访问权限 | Bearer 身份来自 `current_user`，不信任请求 owner；跨 owner/不存在会话统一 404：`message_images.py:19-26,41-117` | `test_message_images_api.py:42-84` 同时断言 owner 200、未登录 401、其他 owner 404 | aligned |
| IM Scenario: 会话 fork 保留图片 | fork 在新会话复制资源引用并改写正文 URL，可共享不可变存储文件：`message_images.py:129-167`; `src/IM/application/web_im_service.py:475-501` | `test_message_images_api.py:127-197` 删除原会话后原 URL 404、fork URL 仍返回原 bytes | aligned |
| `specs/im/web-chat-ux.md` Requirement: Agent 图片在正文中按顺序展示 loading/ready/error | ReactMarkdown `img` 只在原位置接入 `MessageImage`，不改 attachment renderer：`src/IM/frontend/src/features/chat/components/message-pane.tsx:1594-1621,1740-1743`; 私有 URL/pending/remote 分流：`message-image.tsx:9-44` | `src/IM/frontend/src/features/chat/components/message-image.test.tsx:48-127`; `M1-reply-images/evidence/web-im-{1280,390,desktop-loading,mobile-loading,desktop-error,mobile-error}.png` | aligned |
| Web Scenario: 成功和纯图片回复 | 成功图使用气泡内原比例按钮和 Dialog，未合成任何占位正文：`message-image.tsx:88-105`; `src/IM/frontend/src/styles/global.css:2497-2514,2532-2561` | `message-image.test.tsx:48-61,77-87`; ready/zoom 证据与 `M1-reply-images/progress.md:42-49` | aligned |
| Web Scenario: 图片准备与加载 | Gateway 在语法闭合前缓冲 destination，仅发 pending ordinal，完成帧在 IM 上传后才替换 URL：`reply_image_stream.py:13-115`; `src/personal_assistant/gateway/runtime_delivery/image_connection.py:73-148`; 前端 pending/private-fetch loading 均是文本状态：`message-image.tsx:28-42,46-86` | `test_reply_image_stream.py:9-77`; `tests/unit/personal_assistant/test_im_reply_image_delivery.py:48-108`; `message-image.test.tsx:48-61`; desktop/mobile loading 证据 | aligned |
| Web Scenario: 图片失败 | 准备/上传失败在原 ordinal 投影为可读原因；私有 GET/decode 失败则在原位显示可重试按钮：`reply_images.py:64-75,207-238,319-367`; `message-image.tsx:46-86` | `test_reply_images.py:59-184`; `test_reply_image_public_sources.py:26-78`; `message-image.test.tsx:63-87`; desktop/mobile error 证据 | aligned |
| Web Scenario: 登出和切换账号 | 私有图组件以当前 user + URL 为生命周期 key，卸载时 abort fetch 并 revoke Object URL：`message-image.tsx:28-39,46-75` | `message-image.test.tsx:90-117` | aligned |
| 跨契约核对：`/new` 对图片投递的撤销 | 这不是本 unit 新增的 `/new` 语义；canonical `docs/specs/gateway/routing-delivery.md:178-206` 已要求旧 run 的 stream/final/external mirror 不得在确认后晚到。图片作为普通 assistant delivery 继承该约束：`src/personal_assistant/gateway/runtime_delivery/context.py:318-417`; `task_tracker.py:97-135`; `src/personal_assistant/gateway/session_run_coordinator.py:671-805`; `image_connection.py:82-148`; `src/personal_assistant/gateway/outbound_router.py:146-206` | `tests/unit/personal_assistant/test_session_reset_delivery.py:29-217`; `test_runtime_delivery_task_tracker.py:19-94`; `test_im_reply_image_delivery.py:110-165`; `test_shadow_reply_images.py:146-263`; 真实飞书等待 run + `/new` 证据见 `M1-reply-images/progress.md:58` | aligned |

### Unit Diff Coverage Audit

| 可观察增量 / 支撑机制 | Delta 承接 | 审计结果 |
|---|---|---|
| Agent 可交付目录和产品提示 | gateway 统一交付 Requirement + 本地跨机器/不绕过权限 Scenarios | 只建立 `.nanoassistant/exports/` 明确边界，没有扩大工具读权或新建截图工具。 |
| Gateway 快照、output identity、provider receipt、shadow recovery 与 public admission | gateway 路由、IM 离线恢复、局部失败 Scenarios；`/new` 部分继承既有 canonical reset 契约 | 都是为声明的图片交付结果服务的内部实现与恢复边界；没有新运行时路由或跨 provider exactly-once 承诺。 |
| IM 私有上传/GET、幂等错误和 fork URL 重绑 | IM conversations/messages Requirement 与三个 Scenarios | 只覆盖新托管资源；旧 `/im/uploads` 保持现状，与 delta 的不追溯迁移边界一致。 |
| 流式 pending、完成 URL、侧边栏/回执摘要隐去 destination、响应式状态和账号 blob 销毁 | Web UX Requirement + loading/failure/account Scenarios；gateway 权限/普通文本 Scenario | `src/IM/infra/_helpers.py:7-15,57-91` 和 `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:50-123` 只将图片 destination 降为安全标签，确保声明的“不闪现本地路径”在气泡外的同一 Web IM 可观察摘要面也不被破坏。 |
| 既有 public/data 安全下载器增加稳定 `limit/type` 分类 | gateway 局部失败 + 普通文本/既有示例不回归 Scenarios | delta 只承诺“既有可获取网络图片”不回归，没有把 data/GIF 提升为新的本地格式承诺。 |

Current-snapshot reconciliation checks: Python mapping suite **75 passed**; Web IM `message-image` suite **6 passed** at the same `320bc117e` tree. Earlier full and targeted verification remains the authority for product completion; this reconciliation does not replace it.

### Uncovered Observable Behavior

None. The final unit diff's user-observable image delivery, persistence, routing, failure, loading, responsive, preview-safety and account-lifecycle changes are covered by the three deltas. `/new` image suppression is correctly inherited from the unchanged canonical session-reset and external-mirror contracts rather than duplicated as a new feat-551 rule.

Outcome: aligned

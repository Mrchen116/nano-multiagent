# feat-804-human-user-avatars: Review

## 范围与版本

- 本次问题与需求/设计位置：[`spec.md`](spec.md)、[`design.md`](design.md)、[`prototype.html`](prototype.html)、[`M1-human-user-avatars/evidence/verification.md`](M1-human-user-avatars/evidence/verification.md)
- 实际 `executed_base` / `validated_at`：`953eeb86ecedadd590e7975a5709a2a1ca4cf739` -> Round 1 `fe736052370e9686efcc795fa2b45564e1ebfc9b` -> Round 2 `52eceae80c84676ab3d6af76878652493ff8a79a`
- 最终 `effective_base` / `effective_through` 与保留依据：`effective_base = 1bdc4646c4a66de7cf925c05137ccbd631ce9918`（合入上游 `refactor-800` 与 `feat-803` 后的 `origin/develop`），`effective_through = fae40d6bcbfeaac66a576e01e797525924f333fc`。合入仅在 `apps/im-server/src/gateway.ts`、`apps/im-server/src/messaging.ts` 与 `src/IM/ios/NanoIM/Features/Chat/ChatStore.swift` 产生 3 处纯正交叠加冲突（保留上游 `notification_hint` / `conversation.read` / `project` 范围事件，同时保持人类出口 `attachHumanAvatars` 与 `user.profile_updated` 增量消费），未改变任何受审头像权限、存储、前端体验或 Agent Context 不变量，且经合入后全套本地 CI 等价检查与契约门禁复核通过，故完整保留两位独立审查员在 `52eceae80c84676ab3d6af76878652493ff8a79a` 的 `Approved` 结论。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 服务端静态图片校验、EXIF 剥离、256×256 WebP 归一化、同账号互斥锁、可见性鉴权矩阵、三端缓存隔离与草稿正交正确性 | `change-code-review` · 独立子代理 `38550e55` · Round 1 `full` + Round 2 `closure/patch` | `pass` | 独立核查 66 个变更文件并运行 `user-avatar.test.ts`、`tool-references.test.ts`、`test_runtime_dependency_contract.py`；Round 1 检出的 `F-1` 与 `F-2` 在 `52eceae80` 已独立验证关闭 |
| `avatar_version` 仅出现在人类出口，零进入 Gateway RPC、PA `authorizationGuard` SHA-256、`pa.observations`、SingleThread、`pa.review`、工具返回与 LLM Context Cache 前缀 | `agent-context-review` · 独立子代理 `38550e55` · 独立实施模式（Round 2 `retained`） | `pass` | 审查员亲自逐行核查 `message-records.ts`、`messaging.ts`、`gateway.ts`、`work.ts`、`personal-agent.ts`、`personal-actions.ts`、`task-graphs.ts`、`sources.ts`、`personal-security.ts`、`prompt-assembly.ts`、`tool-references.ts`，并运行真实 Fastify+WS+PA 哈希/观察字节级恒等测试；因未改模型提示词/工具 schema，未额外发起外部 `LLM_PROXY` 会话 |
| 桌面端左下角 `88px` 导航轨头像基线、次级结构零头像克制（引用块/待引用条/外置双勾/`@mention`）、裁剪弹窗去冗余与首帧绘制、`1280×800` / `390×844` / `320×680` 中英文排版与原型 `must-match` 对齐 | `frontend-experience-review` · 独立子代理 `3ada24b5` · Round 1 `full` + Round 2 `closure/patch` | `pass` | 独立驱动真实隔离栈 Chromium 多视口双语测量与截图（含 18 字符 `@alexandra_chen_dev` 长用户名验证），Round 1 检出的 `F-3` 在 `52eceae80` 独立验证关闭，`Prototype Alignment Matrix` 全项 `PASS` |
| Web 与 iOS 原生模拟器完整选图裁剪上传、非法文件原位报错保旧、显示名草稿正交保留、跨路由实时同步、弱网回退、登出释放及 iOS 沙盒零图片字节落盘 | `product-journey-review` · 独立子代理 `3ada24b5` · Round 1 `full` + Round 2 `patch` | `pass` | 隔离真栈双浏览器并发实时同步 + 专用 iOS 26.4 模拟器（`iPhone 17`）端到端相册选图裁剪/冷启动/沙盒容器全盘扫描（`schema.version=9`，0 个头像图片或 `URLCache` 落盘）；限制：未覆盖物理 iPhone 真机相册系统弹窗与 AltStore 续签 |
| 最终契约增量与实现一致性（`specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md`） | `change-code-review` (`corrected-delta`) · 独立子代理 `38550e55` + 主 Agent 合入 `feat-803` 基线对齐 | `pass` | `F-1` 修复后实现与增量契约完全一致；合入 `origin/develop`（`feat-803`）后同步将 `im/spec.md` 的 `Auth and Tenancy` 计数更新为 `18` 并保留 `web-chat-ux.md` 的项目级助手条款及同目录链接 `agents-nodes.md` |

## Findings 与关闭

1. **`F-1`（`WARNING` / `confirmed`，`change-code-review`）— `canReadUserAvatar` 遗漏未加入公开群读取者与无发言历史回执成员**
   - **位置**：`apps/im-server/src/human-avatar-projection.ts:28-60`
   - **触发条件与影响**：非管理员有效成员在未加入公开公司群时预览群内已停用成员，或查看曾留有已读回执（无发言）后退群并被停用成员的历史回执时，`GET /im/v1/users/:id/avatar` 返回 `404` 并写入客户端当次会话负缓存。
   - **Resolution**：在 `52eceae80` 中为 `hasSharedReadableConversation` SQL 补齐 `UNION SELECT conversation_id FROM conversation_participation_history WHERE user_id=?`，并将 `canReadUserAvatar` 放宽为 `Boolean(conversationAccess(...))`，同时对 `broadcastUserProfileUpdated` 保持 `{ requireSubscribedAccess: true }`；在 `apps/im-server/tests/user-avatar.test.ts` 新增双向回归单测。
   - **独立关闭依据**：子代理 `38550e55` 在 Round 2（`@ 52eceae80c84676ab3d6af76878652493ff8a79a`）核实源码与单测通过，状态 **`closed`**。
2. **`F-2`（`SUGGESTION` / `confirmed`，非阻塞，`change-code-review`）— iOS `NanoIMApp.body` 在非激活分支同步写 `@Observable` 属性**
   - **位置**：`src/IM/ios/NanoIM/App/NanoIMApp.swift:19-23`
   - **触发条件与影响**：`MembershipView` 分支在 `body` 求值期间调用 `ensureAvatarImages(for:)` 写入 `model.avatarImages`，后续若顶层读取易引发冗余状态刷新告警。
   - **Resolution**：在 `52eceae80` 中移至 `AppModel.apply(_:from:)` 与 `bootstrapLocal()` 预初始化，`body` 改为纯读取。
   - **独立关闭依据**：子代理 `38550e55` 在 Round 2（`@ 52eceae80c84676ab3d6af76878652493ff8a79a`）核实关闭，状态 **`closed`**。
3. **`F-3`（`Major / Blocking` / `confirmed`，`frontend-experience-review`）— `390×844` 窄屏 Web `/settings/account` 身份行 `min-width` 被覆盖导致姓名竖排折断**
   - **位置**：`src/IM/frontend/src/features/settings/settings-surfaces.css:110-113, 286-288`
   - **触发条件与影响**：`.settings-identity > div { min-width: 0 }` 覆盖 `.account-identity-meta`，使 `390×844` 英文已设头像态下姓名与 `@username` 被挤压为 `11px` 宽逐字符竖列。
   - **Resolution**：在 `52eceae80` 中使用 `.settings-identity.account-identity-editor > .account-identity-meta { flex: 1 1 160px; min-width: 160px; }` 并配合 `@media (max-width: 520px)` 下操作按钮组 `flex-basis: 100%; padding-left: 72px;` 对齐换行。
   - **独立关闭依据**：子代理 `3ada24b5` 在 Round 2（`@ 52eceae80c84676ab3d6af76878652493ff8a79a`）通过 `1280×800`、`390×844` 与 `320×680` 中英文真栈复验确认 `width=240px` 横向完整可读且零横向溢出，状态 **`closed`**。

无存活 findings（`0 surviving findings`）。

## 流程收口

- **重要目标和关键设计覆盖**：全部覆盖（真人静态头像上传/圆形裁剪/替换/移除/首字母柔和色回退、服务端 `sharp` 256×256 去 EXIF WebP 与同账号互斥锁、`selfManagedAuth` 可见性矩阵、三端实时同步与登出清理、iOS 纯内存缓存与 SQLite v9 元数据、桌面端左下角导航轨基线、引用块等次级结构零头像克制、Agent/PA 零上下文污染、五端对齐矩阵）。
- **开放问题 / pending / inconclusive**：无（`0`）。
- **最终 delta 校对**：已由独立代码审查校对通过，并按最新 `origin/develop` 基线完成 canonical 归并（`docs/specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md`）。
- **版本变化后保留 / 补验的判断与依据**：`52eceae80` 合入 `origin/develop`（`1bdc4646c`）至 `fae40d6bc` 的三处冲突消解均为正交保留，并在全量前端 141 文件回归中恢复 `contacts-api.ts` 的 `contactActor` 纯 `{ type, id }` 创建会话入参（全局头像目录由 `providers.tsx` 直接读取 `Contact` 字段，不依赖 `contactActor`），经合入后全套契约检查、后端 98 文件与前端 141 文件单测及构建验证无回归，保留全部独立审查 `pass` 结论。
- **测试资源回收结果**：4 类本轮临时资源全部已回收，0 个遗留：
  1. 隔离真栈（`WT_ROOT` 下的 `im-server` 与 `gateway` 进程、SQLite 与临时上传目录）已执行 `./scripts/e2e-down.sh` 并删除目录，确认无残留监听进程；
  2. 本轮新建专用模拟器 `NanoIM feat-804 E2E`（`A6025E88-5CCD-4D39-9243-AAAF71CE832D`）已 `shutdown` 并 `simctl delete`，宿主机原有模拟器均保持初始 `Shutdown` 状态；
  3. 临时 Xcode DerivedData 与归档目录 `/tmp/nano-ios-build`、`/tmp/nano-ios-journey-804` 已删除；
  4. 本地构建缓存产物 `src/IM/frontend/dist`、`src/IM/ios/NanoIM/Resources/IntelligentUI`、`.cache/e2e-ui` 已清理。
- **交付范围与剩余事项**：完成 canonical spec 归并、`docs/changes/archive/feat-804-human-user-avatars` 归档与本地 CI 等价检查后，推送分支并创建面向 `develop` 的 Pull Request（开发 worktree 按项目约定在 PR 合入前保留）。

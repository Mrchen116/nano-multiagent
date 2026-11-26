# feat-794-wechat-channel: Review

## 范围与版本

- 本次问题与需求/设计位置：
  - [spec.md](spec.md)、[design.md](design.md)、[prototype.html](prototype.html)、[design-review.md](design-review.md)
  - 4 份 delta-spec：[external-channels.md](specs/gateway/external-channels.md)、[routing-delivery.md](specs/gateway/routing-delivery.md)、[spec.md](specs/gateway/spec.md)、[agents-nodes.md](specs/im/agents-nodes.md)
  - 里程碑证据：[m1-verification.md](M1-wechat-binding-and-text-channel/evidence/m1-verification.md)、[m2-verification.md](M2-wechat-rich-media-forwards-and-approvals/evidence/m2-verification.md)
- 实际 `executed_base` / `validated_at`：
  - `executed_base`：`3fafe61c545e89aee6ff6977ed3d082c21a23de2`
  - Round 1 `validated_at`：`60a6648e7a433ebe00c746db9be0e554e44cd4f3`
  - Round 2 `validated_at`：`8c8828dd509f9634193499828dc1ce2ff67cc296`
  - Round 3 `validated_at`：`406bb70eae6c37b2ed9ce0599ef4df52acf35855`
- 最终 `effective_base` / `effective_through` 与保留依据：
  - `effective_base`：`3fafe61c545e89aee6ff6977ed3d082c21a23de2`
  - `effective_through`：`406bb70eae6c37b2ed9ce0599ef4df52acf35855`（`406bb70ea` 相对 `8c8828dd5` 仅补齐 `specs/gateway/routing-delivery.md` 末尾 14 行既有 Scenario 纯文档内容，运行时/前端/测试源码 `git diff` 为空，因此 Gate 2/3/4 在 `8c8828dd5` 上的通过结论对 `406bb70ea` 继续有效，Gate 1 已在 `406bb70ea` 上完成 Round 3 终审通过）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 代码正确性、架构边界、离线自治、幂等回执与最终 delta-spec 对齐 | `change-code-review` · 独立子代理 `39dc966e` · `full` + `closure` + `corrected-delta`（R1 `60a6648e7` → R2 `8c8828dd5` → R3 `406bb70ea`） | **`pass`** | 核销全部 9 项代码问题（`CR-F1`～`CR-F9`）与 `D1`（`CR-Delta`）；4 份 delta-spec 全部 `aligned`；实跑 `packages/personal-assistant`（350 passed）、`apps/im-server` + `packages/channels`（551 passed）、`file-transfer.test.ts`（2 passed）、`wechat-channel-panel.test.tsx`（4 passed）、`test_runtime_dependency_contract.py`（14 passed） |
| 模型可见上下文、`<= 8` 字符短 `attachment_id`、防注入包裹与静态前缀缓存零退化 | `agent-context-review` · 独立子代理 `eff76cd0` · 隔离真栈轨迹原件审查 + `closure`（R1 `60a6648e7` → R2 `8c8828dd5`） | **`pass`** | 隔离真栈 `/tmp/feat-794-ctx-r2` 读取真实 `session.v4.jsonl`：`SingleThread`（`ctx-st-r2`）与非 PA `Global`（`daily-engineering`）均分配 `a_xxxxxx` 并端到端调用 `download_attachment` 落盘 PDF 与 `voice.wav`；非光栅附件已剥离 57 字符原始 `external:...` 键；同条多段文本以 `\n\n` 分隔；PA 观察链 `latest_message_at` 稳定呈现 ISO 时间；`packages/dsh-integration/` 0 改动，`fork-prefix-provider.test.ts` 3/3 通过且真实会话 `cacheReadTokens` 稳定命中 |
| Web 桌面（`1280×800`）与移动（`390×844`）扫码/PIN/状态卡片视觉交互及原生 iOS 通道契约 | `frontend-experience-review` · 独立子代理 `0af37057` · 隔离真栈双视口目视走查 + iOS 源码契约审查（R1 `60a6648e7` → R2 `8c8828dd5`） | **`pass`** | 隔离真栈 `/tmp/feat-794-ux-r2` 在 `1280×800` 与 `390×844` 逐态实测：同节点飞书失败不再污染微信绿色 `已连接`；微信卡片隐藏飞书专属「权限状态暂时无法确认」面板；高频列表刷新下重新扫码确认可靠关闭弹窗、被动卸载自动触发 `cancel`；`-14` 失效文案去重、已扫码遮罩均衡折行、双视口零横向溢出；iOS `xcodebuild build-for-testing` 与 `AgentContractsTests`（12/12）通过 |
| 真实入口端到端旅程（扫码/PIN、`PA` 与普通 Agent 收发、内部影子隔离、富媒体/引用、纯文本审批、`/stop`、`-14` 恢复） | `product-journey-review` · 独立子代理 `d4b28ce2` · 隔离真栈全链路验收（R1 `60a6648e7` → R2 `8c8828dd5`） | **`pass`** | 隔离真栈 `/tmp/feat-794-pj-r2`（`e2e-wechat-twin` + `codexOAuth:gpt-6.2-sol`）实测：微信 `/stop` 在 `SingleThread`、`PA`、启用 `task_graph` 的 `Global` 三路径均立即回执并释放会话继续对话；Web IM 内部 `PA · wechat` 与 `Global · wechat` 影子会话回复零泄漏至微信（`sent_messages` 不变），切回微信后 `local_images`（64×64 PNG）与 `download_attachment` 双向正常；多段卡片+合并转发 `\n\n` 分隔清晰 |
| 连接真实腾讯公网 `ilinkai.weixin.qq.com` 的手机微信真机扫码验收 | 用户本人（按 `spec.md` Q2 约定，PR 前隔离真上游预览） | **`pending`（待用户扫码确认）** | 本地可控 iLink twin 已覆盖全部协议状态机；归档与创建 PR 前启动不带 `NANO_WECHAT_E2E_BASE_URL` 的隔离预览栈，由用户本人用手机微信完成真机扫码与实发验收 |

## Findings 与关闭

Round 1 共识别 16 项问题（合并跨门禁同源项），加上 Round 2 识别的 1 项纯文档漏粘 `D1`，均已修复并由对应独立审查者验证 **`closed`**，当前 **0 存活 findings**：

- **`PJ-F1`（`high` → `closed` at `8c8828dd5`，Gate 4 + Gate 1 独立关闭）**：`apps/node/src/main.ts`、`packages/personal-assistant/src/{task-execution,external}.ts`、`apps/im-server/src/task-graphs.ts`。微信 `/stop` 此前未走 `external` 镜像转换且 `pauseExecution` 仅认 `relay_tasks`，导致抛 `Stop is pending until Task state can be confirmed` 并挂死 `task.execution.block`。修复后 `TaskExecution` 接入 `external`（未启用 `task_graph` 或纯离线未建影子会话时安全短路并释放锁，在线先补镜像并转换 `control_message_id`），`pauseExecution` 支持已验权外部影子主人消息与 `PA` 主人观察消息；三类 Agent 端到端实测通过。
- **`CTX-F1`（`high` → `closed` at `8c8828dd5`，Gate 2 + Gate 4 独立关闭）**：`packages/personal-assistant/src/tool-references.ts`。`attachmentRef` 此前仅匹配 `/im/v1/conversations/...`，导致普通 `SingleThread` 与非 PA `Global` 的 `external:<agentId>:...` 附件缺少短 `a_xxxxxx` 引用且无法调用 `download_attachment`。修复后为入站 `external:<agentId>:...` 分配 `a_xxxxxx`，并对非光栅外部附件剥离长 `url`；真实轨迹验证 `SingleThread` 与 `Global` 均成功落盘外部文件与 `voice.wav`。
- **`FE-F1`（`high` → `closed` at `8c8828dd5`，Gate 3 + Gate 1 独立关闭）**：`apps/im-server/src/channels.ts:177-205`。`view()` 此前未按 `channel_id` 过滤 `last_apply_error_json` 且强绑整节点 `applied_manifest_revision`，导致同节点飞书失败连坐污染健康微信卡片为红色失败态。修复后按单通道过滤错误并独立结算 `sync_state`，双通道并存实测互不干扰。
- **`CR-F1` & `CR-F2`（`high` / `medium` → `closed` at `8c8828dd5`，Gate 1 独立关闭）**：`packages/personal-assistant/src/{personal-assistant,global-agent,external,external-store}.ts`、`packages/channels/src/feishu.ts`。为 `PA` 外部 `send_message(local_images)` 补齐 `preparePublication` / `settlePublication` / `unknownScreenshotReceipt` 与 `ExternalChannels` 本地 `agent.message.status` 回执查询，并统一开放 `wechat` 与 `feishu` 1:1 外部私聊 `local_images`（不改 `dsh-integration` 静态提示词）。
- **`PJ-F2`（`medium` → `closed` at `8c8828dd5`，Gate 4 + Gate 1 独立关闭）**：`packages/personal-assistant/src/{inbox,personal-assistant,global-agent,external}.ts`、`packages/product-contracts/src/{chat,chat-codec}.ts`。Web IM 内部直接向 `PA · wechat` 或 `Global · wechat` 影子会话发消息时，此前因 `canonicalConversation` / `chat(target)` 映射被回写至微信。新增 `latestHumanTriggerIsInternalIm` 与 `internal_shadow_only: true`，确保内部 IM 触发的回复仅写入内部影子会话，外部触发或显式外部目标仍正常外发。
- **`FE-F2` & `FE-F3` & `FE-F4` & `FE-F5` & `CR-F8`（`medium-high` / `low` → `closed` at `8c8828dd5`，Gate 3 + Gate 1 独立关闭）**：`src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx`、`src/IM/frontend/src/styles/global.css`、`src/IM/ios/NanoIM/Features/Agents/AgentChannelsView.swift`。隐藏微信不适用飞书的未知权限诊断提示；将微信扫码弹窗 `wechatReadOnly` 与列表后台刷新 `isFetching` / `draftConflict` 解耦并优先结算 `confirmed`；补齐被动卸载 `cancelActiveWeChatSetup()`；去重 `-14` 失效底部文案并优化已扫码遮罩折行。
- **`CR-F3` & `CR-F4` & `CR-F5` & `CR-F6` & `CR-F7` & `CR-F9`（`medium` / `low` → `closed` at `8c8828dd5`，Gate 1 独立关闭）**：`packages/personal-assistant/src/{external,external-store}.ts`、`apps/node/src/main.ts`、`packages/channels/src/wechat/{inbound,connection}.ts`。补齐微信纯文本审批 `<= 300` 字符参数摘要；停用 Agent 时调用 `external.cancelAgent` 清理未决审批；纯不支持/纯超限入站消息同步可读提示至影子会话并标 `contextOnly: true` 防止二次回复；媒体下载遇 `abortSignal.aborted` 直接透传异常且在 `receive` 完成后才记 `seen_msgs`；移除未使用的 `mediaBufferCache`；剥离内联提取图片在影子会话正文中的原始 `data:image/` Base64 文本。
- **`CTX-F2`（同 `PJ-F3`）& `CTX-F3`（`low` → `closed` at `8c8828dd5`，Gate 2 + Gate 4 独立关闭）**：`packages/personal-assistant/src/{external,single-thread,attention}.ts`。同条微信多段文本统一以 `\n\n` 分隔；`sourceInstant` 仅对 `sender_type === 'user'` 要求外部时间戳，恢复外部影子会话内 Agent 回复的 `latest_message_at`。
- **`D1` / `CR-Delta`（`medium` → `closed` at `406bb70ea`，Gate 1 独立关闭）**：`docs/changes/feat-794-wechat-channel/specs/gateway/routing-delivery.md`。补齐 `PA 为每条真人消息固定模型侧发生时间与实际入口` 的 `MODIFIED` 块及其全部 8 个既有 Scenario。

## 流程收口

- 重要目标和关键设计覆盖：微信扫码/IDC 切域/数字 PIN 交互式绑定与 X25519 封存、单 poller 先停再起与 `-14` 自动停用、`PA` 与普通 Agent（`single_thread`/`global`）双向消息及触发源路由隔离、`<appmsg>` 卡片/`<recordinfo>` 递归合并转发/双层语音/16 MiB EXIF 图片/25 MiB 离线可下载文件/`partial_text` 引用定位、出站双阶段发图与代码块安全分片、`SingleThread` 纯文本互斥审批、Web 双视口与原生 iOS 端引导卡片均已完整实现并经独立验证通过。
- 开放问题 / pending / inconclusive：无代码或设计开放问题；唯一约定待办项为用户在 PR 前对隔离真上游预览环境的真机微信扫码实测（`spec.md` Q2）。
- 最终 delta 校对：4 份 delta-spec（`gateway/external-channels.md`、`gateway/routing-delivery.md`、`gateway/spec.md`、`im/agents-nodes.md`）均已通过 Gate 1 `corrected-delta` 终审（`aligned`）。
- 版本变化后保留 / 补验的判断与依据：`406bb70ea` 相对 `8c8828dd5` 仅含 `specs/gateway/routing-delivery.md` 14 行纯文档增量，Gate 2/3/4 实测证据完整保留有效，Gate 1 已对 `406bb70ea` 完成增量终审。
- 测试资源回收结果：Round 1 与 Round 2 全部临时目录（`/tmp/feat-794-*-rt`、`/tmp/feat-794-*-r2`）、`e2e-wechat-twin` 进程、Gateway/IM 进程与浏览器实例均已销毁并核实零残留。
- 交付范围与剩余事项：当前保持 `feat-794-wechat-channel` 处于 active 状态，启动连接真实腾讯微信上游的隔离预览栈交用户亲自扫码实测；待用户确认后立即回收预览栈、将 4 份 delta-spec 归并入 `docs/specs/`、归档 unit 至 `docs/changes/archive/`、跑齐 CI 本地门禁并向 `develop` 提交 PR。

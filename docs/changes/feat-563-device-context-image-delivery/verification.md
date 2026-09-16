# Verification Report: feat-563-device-context-image-delivery

## Round 1 — full

- Validation snapshot: `0014ee0b0 → c8586a42969c12e3265286cec8b5e9648e3c802a`
- Unit branch: `codex/feat-563`
- Verification mode: `full`
- Independent detached worktree: `.worktrees/verify-feat-563`
- Verdict: **FAIL** — 1 CRITICAL, 2 WARNING, 0 SUGGESTION.
- `requires_full_verification: false` — fixes can receive targeted closure plus their affected regression checks.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Runtime、普通候选授权与同 run 恢复、显式错误反馈均有实现；M1 R4 的 IM 离线飞书路径未满足 |
| Correctness | 本报告独立执行的首组 79 项相关测试通过；发现离线阻塞和两项设计明确要求的幂等边界缺口 |
| Coherence | SDK/core/product 依赖分层保持；准备/提交分离与私有反馈一致；跨渠道恢复仍有偏离 |

核对材料：首文档全部 Requirement/Scenario，design 的 Prompt、权限、候选、提交/恢复决策及 M1 退出标准；四份 delta-spec；对应 current `kernel/runs`、`gateway/routing-delivery`、`gateway/relay-protocol`、`im/web-chat-ux`；`SPEC.md` 架构边界与 `docs/development/testing.md`。

## Completeness and M1 evidence

| Exit criteria | Evidence and status |
|---|---|
| R1 / Runtime 与消息来源协同 | `product.py:332` 使用已批准精简文本；注册 ack 配置、可选执行地址、运行/preview 投影有实现与测试；真实两设备/渠道旅程由独立产品 reviewer 验收，报告时尚待证据 |
| R2 / 内外目录、权限、顺序与历史 | `reply_images.py` 保留格式/数量/大小、逐层 no-follow 打开和不可变快照；IM API 仍做成员检查；自动化覆盖存在；真实旅程证据待产品验收 |
| R3 / 私有失败与恢复 | 普通 callback withheld 进入同 run 下一模型轮；显式工具简短错误；旧 held/reminder 保留，自动化通过 |
| R4 / 飞书与影子离线恢复 | **未完成，V1**；新 recovery 消费者和 manifest alias 存在，但 IM 离线仍阻止普通飞书图片 |
| W1 / 接线测试 | 首组 SDK、PA compose、IM 配置和显式发送相关测试 79 passed |
| W2 / stale、取消、预算、部分成功、ACK 丢失 | 有直接回归覆盖；未决新调用/过期 provider 去重窗口无实现及回归保护，见 V2/V3 |
| W3 / prompt 与旧拦截协议 | `test_runtime_access_context.py` 检查普通/群/global 路由；`test_output_revalidation.py` 检查原 reminder；`test_send_message_tool.py` 保留 held |
| W4 / 完整检查与真实 Web IM/飞书证据 | 编排者并行执行完整检查、产品 reviewer 正在验收；本快照 M1 仅 `.gitkeep`，故此项 **pending separate gate evidence**，不将尚在执行的验收误报为源码缺陷 |

没有前端视觉 prototype/reference must-match；本 unit 未改布局，N/A。测试并非真实 Web IM/飞书验收的替代。

## Correctness mapping

| Requirement / Scenario | Implementation | Regression evidence | Status |
|---|---|---|---|
| 设备背景、用户界面 URL、可选执行地址、节点/配置变化 | `runtime_access.py`、`product.py:332`、`composition.py:268`、session/runtime/preview 投影 | `test_runtime_access_context.py`、`test_public_url_config.py`、`test_gateway_im_connection_behavior.py` | covered；模型真实使用效果待产品验收 |
| IM 认证注册提供用户 URL，缺配置明确失败 | `IM/app.py`、`IM/ws/gateway/sessions.py`、`ws/im_connection.py` | IM config 与注册行为套件 | covered |
| 工作区外原文件可发送、拒绝符号链接、权限前不读字节、授权后同 FD | `pa_reply_delivery.py:67`、`reply_images.py` 的 open/read/prepare | `test_pa_reply_delivery.py`、`test_reply_image_delivery_strict.py` | covered |
| 普通操作复用真实权限而不执行工具 | `sdk/output.py`、`core/agent/output.py`、`core/tools/registry.py:evaluate_permission` | `test_output_permission.py` | covered |
| 多块正文聚合、失败同 run 继续、预算/取消、默认消费者 | `core/agent/loop.py` output handler 分支 | `test_output_callback.py`、`test_output_revalidation.py` | covered |
| 缺图/上传失败不公开成品或占位 | `PaReplyDelivery`、`ReplyImages.ensure_ready/project_im`、`internal_dispatch.py` | `test_pa_candidate_delivery.py`、`test_global_dispatch_images.py` | covered |
| 纯文字、代码示例不触发图片权限 | parser + `PaReplyDelivery.__call__` | PA delivery、reply image、composed text tests | covered |
| 原图移除后历史资源与成员保护 | snapshot + protected IM images route | `test_shadow_reply_images.py`、`test_message_images_api.py` | covered |
| 已知成功渠道不重复发、unknown 不说全部未送达 | receipts + `ReplyDeliveryRecovery` + kernel partial/pending | `test_reply_delivery_recovery.py`、`test_output_callback.py` | 原身份重放 covered；新调用/超窗口缺口 V2/V3 |
| IM 离线时普通飞书先送、影子后补 | `composition.py:839-996` | 现有 compose tests 只有 Web IM 成功/缺图/文本/恢复 session；没有普通飞书离线接线保护 | **V1** |

## Coherence and earlier review closure

| Decision / earlier finding | Evidence | Result |
|---|---|---|
| PA 仅 import agent.sdk；core 不依赖 platform/sdk | 新 DTO 在 sdk，core structural control；相关 contract tests | aligned |
| Runtime 与每消息 channel/time 分工，不复写路由 | 精简 Runtime 与既有 human message prefix/inbox 保持独立 | aligned |
| 普通权限一次、显式沿用既有权限，不增加模型 tool call | permission-only intercept 路径；observer 被抑制 | aligned |
| 草稿私有 + 原 reminder 模板恢复 | `core/agent/output.py:withheld_reminder` 与 loop retry 分支 | aligned |
| 前次 finder：pending/partial 没有恢复消费者 | `reply_delivery_recovery.py` 持久 payload 重放，`composition.py:771` 接到现有恢复回调 | 原问题已修复；V1/V2/V3 是剩余明确契约边界 |
| 前次 finder：shadow 与候选 manifest 身份分裂 | observer `prepared_output_key` → `shadow_image_bind`，`ReplyImages.bind_output/load` alias | 原问题已修复，恢复可复用候选快照 |
| 普通飞书以原渠道优先，不被内部镜像离线阻塞 | 当前先 resolve_target/project_im，再要求 IM connected/confirmed | **V1** |
| 未决同正文对账与 provider 去重窗口 | 当前只有原调用 key / 固定 UUID，缺两项设计限定 | **V2/V3** |

## Issues

### CRITICAL

**V1 — 普通飞书图片仍依赖 IM 在线。**

- Contract: delta `specs/gateway/routing-delivery.md` “IM 离线不阻塞飞书图片”；current 同名 Scenario；design “提交、幂等与跨渠道失败”明确普通飞书为主渠道，IM 通过 shadow saga 后补。
- Evidence: `src/personal_assistant/gateway/composition.py:845` 无条件调用 `resolve_target`，`:858` 无条件 IM 上传，均在 external prepare 之前；`:918` 附近提交仍要求 IM connected，并先 await IM 确认再发送飞书。
- Scenario/consequence: 已认证 Gateway 的 IM 暂时断网，而飞书正常。新图片候选会因 IM lookup/upload 失败 withheld，或提交阶段 pending；原飞书用户无法收到图片，未保持原有离线能力。
- Action: 普通飞书从已验证来源目标独立准备/提交飞书，IM 镜像绑定同一快照入既有 shadow 后补；增加通过真实 compose seam 的 IM 离线 → 飞书先收到 → IM 恢复同图不重复回归。

### WARNING

**V2 — 新 tool call id 可以绕过同一未决图文的对账。**

- Contract: design “提交、幂等与跨渠道失败”第 3 条要求 Gateway 对同 session + target + 正文摘要的未决交付先对账，不能将新 call id 当作重复发送许可。
- Evidence: `src/personal_assistant/gateway/internal_dispatch.py:611` output_key 只以 Agent/session/call_id 构造；`_send_im_dispatch` 只查该 key；ReplyImages 没有未决正文/目标索引或等价查询。
- Scenario/consequence: 一次显式双渠道发送已到 IM、外部渠道未确认；Agent 下一轮以新调用 id 重发同正文，生成新 IM dispatch identity，从而重复已成功气泡，并与旧 recovery 并存。
- Action: 仅对未决交付做同 session/真实目标/正文一致性对账，返回/恢复原 delivery id；已确定完成后的有意再次发送不永久去重。补此跨调用回归。

**V3 — 飞书未知结果会超出去重保证窗口无限重放。**

- Contract: design “提交、幂等与跨渠道失败”Feishu UUID 条款要求超过 provider 可保证去重窗口仍未知时终止自动重放并保留未确认状态。
- Evidence: `src/personal_assistant/gateway/reply_delivery_recovery.py:105-117` 对每条 `external_prepared` 无条件重放；记录只有 payload/状态，没有首次提交时间或有效重放期限，`:134` 失败后保留到下一次恢复。
- Scenario/consequence: 飞书已接受请求但 ACK 丢失，Gateway 长时间离线后恢复；即使 UUID 相同，也不能依据本实现证明过期请求不会新增重复消息，而设计要求此时停止自动重放。
- Action: 持久化首次发送时间及基于 provider 保证的截止边界；过期 unknown 保留事实、停止自动重放。验证窗口内保留同 UUID，窗口外不发送。

### SUGGESTION

None.

## Direct validation

首组执行：SDK output callback/permission/revalidation、PA delivery/recovery/strict images/Runtime、composed ordinary delivery、global IM/external image dispatch、shadow images、完整 prompt、IM URL config、SDK surface contract，结果 **79 passed**（31.42s；仅两个既有依赖 DeprecationWarning）。

命令前缀为 `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q`；执行目录为独立 detached verification worktree。报告仅验证指定快照，不将编排者后续修复或未完成真实验收计为通过。

第二组独立执行 core/platform 依赖边界、IM 图片成员权限 API、Gateway 注册/重连、send_message、ReplyImages 套件，结果 **72 passed**（5.56s）。两组共 **151 passed**。这不覆盖上面的 V1/V2/V3 场景，不能据测试全绿关闭它们。

## Round 2 — targeted closure

- `validated_at: 8ffd1318a`
- `executed_base: 0014ee0b0`
- `fix_delta_range: c8586a429..8ffd1318a`
- `verification_mode: targeted-closure`
- Focus: V1/V2/V3，以及此前 pending recovery / immutable shadow manifest 修复保留。
- Verdict: **FAIL — V1 still open; V2/V3 closed.** 1 CRITICAL, 0 WARNING, 0 SUGGESTION。
- `requires_full_verification: false`。剩余问题属于已指定的普通飞书离线入口；无需扩大为全量重验。

### Closure evidence

| Finding | Result | Evidence |
|---|---|---|
| V1 普通飞书离线 | **partially fixed / still open** | composition 在 IM disconnected 时跳过 resolve/upload 并独立发送飞书；新增 composed offline test 证明已存在 shadow anchor 的分支可发送、删源后恢复原图。但没有 shadow anchor 的原有合法入口被 `_reply_destination` 排除，仍绕过候选图片授权与失败续轮，详见下文 |
| V2 未决新调用对账 | **closed** | `ReplyImages.dispatch_identity` 对 agent/session/target/text 做摘要并在未决回执存在时复用原 call id；handler 替换真实发送身份；全部渠道完成后新有意发送可用新 id。集成测试使用 `model-fresh-call` 重试，断言 IM 只发送一次并保留原 provider idempotency key |
| V3 provider 重放期限 | **closed** | `record_delivery` 保留 first_attempt_at；`external_retry_allowed` 检查一小时边界；恢复入口及 provider before_publish 均检查；过期保留 pending、不发请求，测试覆盖跨 restart 保留时间与到期不发送 |
| 原 pending recovery | retained | durable recovery payload 和原身份重放测试继续通过 |
| 原 immutable shadow manifest | retained | alias 接线未移除；已锚定 offline composed test 删除原文件后恢复原字节成功 |

### V1 remaining: pending shadow anchor skips ordinary image authorization

- Source: `src/personal_assistant/gateway/runtime_delivery/context.py:520` 在外部消息尚无 IM anchor 时产生 `RunDeliveryTarget.none(reason="external_without_shadow")`，但保留真实 `reply_channel_name`、`reply_target_chat_id` 与 saga；`src/personal_assistant/gateway/composition.py:832` 因 kind none 返回无 destination；`PaReplyDelivery.__call__` 随后返回 pass_through。
- Direct reproduction: 在独立 detached worktree 执行 `tests/integration/test_pa_offline_image_shadow.py` 的现有测试函数，仅在内存删除其 `record_anchor(...)` 预置，不修改仓库文件；给 callback 增加只读 trace。真实 composed pipeline 输出 `external shadow anchor pending ... IM offline`、`CANDIDATE_DESTINATION None`、`CANDIDATE_RESULT pass_through`。后续走旧外部发送路径；测试 adapter 首次发送后删除源文件，final fallback 再读原路径，抛出 `ImageDeliveryError`。
- Consequence: 第一次飞书消息在 IM 离线时仍是有真实外发目标的顶层 PA，但含图候选未进入新增 permission-only 检查和同 run 私有失败恢复；旧路径可以先发图、再因重复读取失败。不能只凭已有 shadow 的新测试关闭 V1。
- Required closure: 使用真实外部通道/聊天作为候选 target，即便 IM shadow anchor 尚未建立；保持 global Work/subagent 排除。新增未锚定 composed 场景断言一次普通图片授权、一次飞书发送、删源后同一快照补 IM；缺图场景必须私有反馈并由下一模型轮修正。

### Round 2 independent checks

`PYTHONPATH=src .../.venv/bin/python -m pytest -q` 执行 `test_pa_offline_image_shadow.py`、`test_pa_candidate_delivery.py`、`test_global_external_dispatch_images.py`、`test_reply_delivery_recovery.py`、`test_shadow_reply_images.py`、`test_reply_image_delivery_strict.py`：**28 passed**（19.97s，两个既有依赖弃用 warning）。另执行上述未预置 anchor 的一次性反证，失败来源已定位。真实 Web IM / 飞书体验仍由并行产品 reviewer 记录，不在此次 closure 冒认通过。

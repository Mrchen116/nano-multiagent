根因（按已澄清口径）：
1) 文本由 PA `withInteractionContext`（product-contracts/src/interactive.ts:35）拼进**模型输入**，仅 single-thread.ts:152 / inbox.ts:347 调用；Work 原生轨迹显示它=正确可观测性，不是缺陷。
2) 「每条都带」的真因是**没有消费语义**：Web 在卡片挂载时无条件登记（src/IM/frontend/src/features/chat/interactive/interactive-card.tsx:84-92，连从未动过的卡也进缓存），发送时按 editedAt 倒序取 3（src/IM/frontend/src/features/chat/components/message-pane.tsx:752-759），成功后只清发送尝试，不清背景缓存（同文件 :783）；设计原文 docs/changes/archive/feat-617-agent-interactive-responses/design.md:145「成功发送不清除背景缓存」。iOS 只在真实改动时登记（src/IM/ios/NanoIM/Features/Chat/InteractiveRuntime.swift:286-293）但同样永不删除（src/IM/ios/NanoIM/Features/Chat/ChatStore.swift:414-425）。两端语义不一致，且都无过期/失效/切换清理。

设计（一次性消费）：pending = 最新改动的草稿且 `draft.updated_at` 晚于该用户在该会话上一条消息；消息落库即消费。**推荐服务端派生**（interactions_drafts.updated_at + messages.created_at，无新表/列），客户端停发 interaction_contexts，服务端接受但权威忽略 → 旧客户端自动收敛；降级方案=客户端持久化 pending（多端/重装不共享，须写进验收）。已核实卡片提交不写 updated_at（interactions.ts:146-150），同一次显式提交走 interaction_reply，不同时传普通消息的 interaction_contexts（message-pane.tsx:1243）；现状仍会跨轮重复携带同一卡。一次性消费是本次调查的设计建议，消费时机和服务端派生方案待验证。

最易忽略风险：①重试指纹包含 contexts（message-attempts.ts:15-17，messaging.ts:517 不一致即 409），「重试去掉过期背景」会失败，正确规则是复用冻结 payload、消费发生在首次提交；②两端草稿保存都有 500ms 防抖（interactive-card.tsx:210-211、iOS changed()），服务端派生必须发送前 flush，否则「刚动卡就发」丢背景；③MessagePane 无 key（chat-workspace-page.tsx:1184），纯客户端方案切会话不会自动清；④成本约 700–1000 token/条消息（估算），改后每次动卡仅一次。

规模：**Full**（IM+Web+iOS+契约，含两个独立设计决策：pending 归属与重试语义，需独立回归矩阵）。Spec 需改：im/conversations-messages.md:571-603、im/ios-client.md:96-99、im/web-chat-ux.md:627-629；PA 与 im/personal-agent.md 不改。验收含「第二条不带」「不动卡不带」「提交不重复注入」「群聊/只读/被取代不带」「重试不产生第二条」。

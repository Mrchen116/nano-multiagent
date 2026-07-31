# M137 Progress - Web IM Token/Turn 与附件统一路径交付

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M137`
- 已确认 branch：`milestone/M137`
- 已确认约束：不创建新 worktree，不修改 `data/dev-tasks.json`。
- 当前基线判断：
  - Web IM 前端还没有真实 Token/Turn 展示。
  - `message-pane` 附件按钮仍是占位。
  - 后端消息附件仍主要依赖 metadata，没有真实上传入口与统一可访问路径。
  - `/im/v1/metrics/usage` 已存在，可直接复用为前端真实 usage 数据源。

## 执行策略
1. 先补红测，锁定 Token/Turn 可见展示与附件真实上传入口缺口。
2. 再做最小实现：前端 usage 展示、附件上传/预览/发送、后端统一上传路径。
3. 跑最小相关测试集与 build，整理产品证据。

## 进度

### R1 红测锁定缺口
- Context: 现有后端只接受附件 metadata，前端也没有真实 usage 卡片与上传发送链路，需要先用测试把缺口钉死。
- Decision: 直接在 `chat-workspace-page.test.ts`、`message-pane.test.tsx`、`tests/im_service/integration/test_messages_api.py` 补红测，分别覆盖 usage 可见性、composer 上传发送、IM-hosted 上传 URL 与可下载回读。
- Rationale: 这些入口已经存在且最贴近验收面，能以最小改动证明缺口来自真实产品入口而不是内部 helper。
- Evidence:
  - Tests: `python3 -m pytest tests/im_service/integration/test_messages_api.py`; `npm --prefix src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`
  - Entry: 前端测试先要求页面出现 This chat / Workspace total usage 和真实附件上传发送；后端测试要求 `/im/v1/uploads` 返回 `/im/uploads/*` 可访问 URL。
- Rollback: 保留当前里程碑分支现状，无需额外回退。
- Commits: C1=未提交（接手时红测草稿已在工作区）, C2=未提交, C3=未提交
- Next: 让红测对应实现最小落地，并补 build 校验。

### R2 Token/Turn 展示
- Context: `/im/v1/metrics/usage` 已可查询，但 Web IM 会话页尚未展示当前会话和 workspace 总 usage，群聊/单聊都缺少可见产品证据。
- Decision: 在 `ChatWorkspacePage` 拉取 conversation + owner 维度 usage，规整为 `UsageTotals` 后传给 `MessagePane`，由 usage strip 同时展示 This chat / Workspace total 两块卡片。
- Rationale: 复用现有 metrics API 比新增专用接口更小；展示绑定当前会话与 owner 聚合，天然兼容单聊和群聊。
- Evidence:
  - Tests: `npm --prefix src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`; `npm --prefix src/IM/frontend run build`
  - Entry: 活跃会话页可见 `This chat`、`Workspace total`、`3 turns / 18 tokens`、`8 turns / 44 tokens`，满足真实可见 usage 验收口径。
- Rollback: 回退到本次实现前的前端状态即可。
- Commits: C1=未提交, C2=未提交, C3=未提交
- Next: 收口附件真实上传、预览和消息发送链路的最终证据。

### R3 附件统一路径交付
- Context: 前端原本只有占位按钮，后端也没有原始上传入口，无法从真实用户入口形成“上传 -> IM-hosted URL -> 消息附件链接”的统一路径。
- Decision: 后端在 `POST /im/v1/uploads` 中直接落盘到 app upload dir，并通过 `/im/uploads/*` 静态路径暴露；前端 composer 支持选择文件、调用 `uploadAttachment`、显示 pending attachment、随 `onSend` 一并发送并在消息 bubble 中输出附件链接。
- Rationale: 维持本地落盘 + 静态托管的最小实现，不引入额外存储系统，同时能形成真实 URL 和消息回读证据。
- Evidence:
  - Tests: `python3 -m pytest tests/im_service/integration/test_messages_api.py`; `npm --prefix src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`; `npm --prefix src/IM/frontend run build`
  - Entry: `/im/v1/uploads?file_name=demo.txt` 返回 `http://.../im/uploads/<uuid>.txt`，GET 可下载原文件；composer 选择 `demo.txt` 后会显示 pending 芯片并把 attachment payload 带入发送动作。
- Rollback: 回退到附件上传入口接入前的 `messages.py` / `message-pane.tsx` 状态。
- Commits: C1=未提交, C2=未提交, C3=未提交
- Next: 更新 TASKS/PROGRESS 并汇总验收证据。

### R4 收口证据
- Context: milestone 需要给出测试命令、真实入口证据、是否已 merge main 与 blocker。
- Decision: 以当前 worktree 状态整理最终测试、入口证据与未完成项，并补齐 TASKS/PROGRESS。
- Rationale: 当前要求明确不要改 board / `data/dev-tasks.json`，因此只在里程碑 worktree 内完成代码与记录收口。
- Evidence:
  - Tests: `python3 -m pytest tests/im_service/integration/test_messages_api.py`; `npm --prefix src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`; `npm --prefix src/IM/frontend run build`
  - Entry: usage 和附件链路都已有前端/后端真实入口证据，可直接用于后续主 agent 验收。
- Rollback: 当前工作区可直接继续提交；如需回退，以里程碑上一个稳定提交为准。
- Commits: C1=未提交, C2=未提交, C3=未提交
- Next: 等待提交/merge main 或进一步真实环境联调。

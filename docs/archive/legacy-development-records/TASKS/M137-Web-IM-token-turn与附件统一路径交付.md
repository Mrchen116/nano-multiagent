# M137 Web IM Token/Turn 与附件统一路径交付

## 前置确认
- [x] 已确认 canonical worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M137`
- [x] 已确认 branch：`milestone/M137`
- [x] 已确认不要创建新的 git worktree。
- [x] 已确认不要修改 `data/dev-tasks.json`。
- [x] 已复核当前 Web IM / IM API 现状：
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx` 的附件按钮仍是 UI 占位。
  - `src/IM/frontend/src/features/chat/**` 尚无真实 Token/Turn 指标展示。
  - `src/IM/api/routes/messages.py` 仅接受/返回附件 metadata，后端还没有真实上传入口与统一附件交付路径。
  - `src/IM/api/routes/metrics.py` 已存在 `GET /im/v1/metrics/usage`。

## 目标
补齐 Web IM 真正可见的 Token/Turn 展示，以及真实可用的附件上传/发送/统一路径交付能力，避免只停留在后端占位字段或 CLI 侧能力。

## Scope
- Web IM 前端显示真实 Token/Turn usage，且在单聊/群聊下都成立。
- Web IM composer 附件按钮从占位改为真实上传入口。
- IM 服务提供真实上传入口与可访问的统一附件 URL 路径。
- 消息展示与发送链路能够携带附件 metadata，并形成真实产品证据。
- 保持最小改动，不扩展为新的存储系统或大型 infra。

## Roadpoints

### R1 先做红测，锁定两个产品缺口
- Acceptance:
  - 增加前端测试，明确要求页面可见 Token/Turn 展示。
  - 增加前端测试，明确要求附件按钮能真正选择/上传并把附件传给发送动作。
  - 增加后端测试，明确要求存在真实上传入口并返回 IM-hosted 附件 URL。
- Tests Plan:
  - Vitest: `chat-workspace-page.test.ts`、`message-pane.test.tsx`
  - Pytest: `tests/im_service/integration/test_messages_api.py`
- DoD:
  - 在当前基线上测试先失败，证明缺口真实存在。
- 状态: DONE

### R2 最小实现真实 Token/Turn 展示
- Acceptance:
  - Web IM 当前会话页可见真实 usage 信息，至少包含 turn 与 token。
  - 信息来自 `/im/v1/metrics/usage`，不是硬编码文案。
  - 既能覆盖单聊，也能覆盖群聊，因为展示逻辑绑定当前 conversation 与 owner/workspace usage 聚合。
- Tests Plan:
  - Vitest 覆盖 workspace 页面拉取 metrics 并渲染到 message pane。
  - `npm run build` 通过。
- DoD:
  - 页面可见“当前会话”和“workspace 总量” usage。
  - 0 值场景也有稳定展示，不依赖 mock copy。
- 状态: DONE

### R3 最小实现真实附件上传与统一路径交付
- Acceptance:
  - IM 服务提供真实上传入口，写入本地上传目录并生成可访问 URL。
  - Web IM 附件按钮可以从真实用户入口选择文件、上传、预览并随消息发送。
  - 消息渲染可见附件链接，形成标准路径交付证据。
- Tests Plan:
  - Pytest 覆盖上传接口、返回 URL、URL 可 GET、消息附件落库/回读。
  - Vitest 覆盖附件上传后进入发送 payload。
- DoD:
  - 不再只有 `url/content_type/file_name` 占位；真实上传路径已打通。
  - Message pane 可见附件 ready-to-send 与已发送附件入口。
- 状态: DONE

### R4 收口执行记录与交付证据
- Acceptance:
  - `TASKS/PROGRESS` 完整记录红->绿执行过程。
  - 输出测试命令、真实入口或等价产品证据、commit/rollback point。
- Tests Plan:
  - 聚焦本 milestone 相关 pytest/vitest/build 子集。
- DoD:
  - 最终汇总可直接用于 milestone 验收。
- 状态: DONE

# M129 Acceptance: 首次启动与默认路径产品化收口

## 结论
- 结论：Landed
- 范围：默认 IM/Gateway 首次启动路径、ready 信号、下一步提示、默认聊天页状态文案、产品化验收证据。
- 约束说明：本次没有新增浏览器自动化 harness；验收证据基于现有 Python acceptance/integration tests、前端 vitest、生产构建和文档/UI 实际改动形成闭环。

## 变更摘要
1. README 顶部 start-here 改为普通用户顺序：先启动 IM，再启动 Gateway，然后按页面/终端提示完成绑定并聊天。
2. operator runbook 增加显式 ready 信号：
   - IM ready = `http://127.0.0.1:8011/` 可进入 Web IM
   - Gateway ready = 终端出现绑定下一步或保持常驻等待消息
3. Web IM 默认 starter 卡片把 `Current route` 改为 `Gateway status`，并把在线状态文案改成 `Online and ready to chat ...`，让普通用户更容易理解当前是否已经可聊。
4. 新增 M129 TASKS / PROGRESS / ACCEPTANCE，记录本次实现与证据。

## Exit Criteria 对照

### 1) 默认 start-here 路径更清晰，减少 operator 术语
- 已达成。
- 证据：
  - `README.md` 顶部已改为单一路径和三步判断，不再让用户先理解 dev server、message API、kernel wiring。
  - `docs/operator-runbook.md` 顶部改为普通用户顺序和 ready signals，operator-only API 下沉为附录。
  - `src/IM/frontend/README.md` 继续明确 `4173` 仅为开发模式，不是默认用户入口。

### 2) 用户能判断 IM/Gateway 是否 ready，以及下一步做什么
- 已达成。
- IM ready 证据：
  - 文档中明确 `http://127.0.0.1:8011/` 可进入 Web IM 即为 ready。
  - 前端 build 成功，说明 IM-hosted dist 产物可生成：见测试结果章节。
- Gateway ready / next step 证据：
  - `tests/e2e/test_personal_assistant_main_e2e.py` 固定 `READY pid=...`、`RUNNING steady_seconds=... alive=true`、`SHUTDOWN exit_code=0`
  - `tests/unit/personal_assistant/test_main.py` 固定：
    - 未绑定时会打开 bind URL
    - 已绑定时不会再次打开浏览器
    - bootstrap 失败时终端输出 `NEXT ...`
- Web IM next step 证据：
  - `src/features/chat/chat-workspace-page.test.ts` 固定：
    - 未绑定时 `Chat unavailable` + `Next: Open bind flow`
    - 离线时 `Chat unavailable` + `Next: Bring Gateway online`
  - `src/features/chat/chat-layout.test.tsx` 固定 starter 卡片显示 `Gateway status` 和 `Online and ready to chat via OpsBot on node-app-01`

### 3) 文档与真实启动路径一致
- 已达成。
- 证据：
  - `tests/acceptance/test_im_gateway_real_acceptance.py` 证明绑定 URL、绑定确认、owned node 建立、消息往返链路真实存在。
  - `tests/im_service/integration/test_account_binding_api.py` 证明绑定完成后 `owned_node_ids == ["node-1"]`。
  - `tests/im_service/integration/test_gateway_websocket_api.py` 证明 `last_error` 可回写 actionable next step。
  - README / runbook 中关于 bind page、nodes board、chat unavailable 的描述均对应现有实现与测试。

### 4) 产品验收不再把过多 infra 细节当普通用户前置知识
- 已达成。
- 证据：
  - README / runbook 主链路中不再要求用户先学会 `curl /im/v1/bind`、`curl .../messages`。
  - `web_relay`、heartbeat、kernel.base_url` 等实现细节保留为配置说明或排障内容，不再作为“默认用户必须理解的知识”。
  - 默认聊天页将状态文案显式收口为 `Gateway status` 与 `ready to chat`，减少 operator-style 心智负担。

## 测试结果
### Python
命令：
```bash
python3 -m pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py tests/acceptance/test_im_gateway_real_acceptance.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_gateway_websocket_api.py
```
结果：`33 passed in 4.93s`

### Frontend
命令：
```bash
cd src/IM/frontend
npm run test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx
npm run build
```
结果：
- `3` 个 test files 通过，`13` 个 tests 通过
- `vite build` 成功

## 关键文件
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/README.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/src/IM/frontend/src/features/chat/components/message-pane.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/src/IM/frontend/src/features/chat/im-chat-api.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/src/IM/frontend/src/features/chat/chat-layout.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/TASKS/M129-首次启动与默认路径产品化收口.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M129/PROGRESS/M129-首次启动与默认路径产品化收口.md`

## 剩余边界
- 本次未新增真实浏览器级 acceptance harness；但已有 Python acceptance + 前端 vitest + build 已覆盖默认路径的关键产品状态与启动反馈。
- 由于 milestone 完成条件已满足，应同步更新 `data/dev-tasks.json`。

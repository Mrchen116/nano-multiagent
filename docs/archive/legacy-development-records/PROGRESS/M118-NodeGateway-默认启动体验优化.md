# M118 NodeGateway 默认启动体验优化

## 启动记录
- 已阅读：`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/docs/operator-runbook.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/main.py`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/config/local_store.py`、相关 IM / frontend / unit / integration / e2e 测试。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M118，`execution_mode=parallel`，`use_worktree=true`，当前 worktree 为 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118`，分支为 `milestone/M118`。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent && python -m pytest -q 2>&1 | tail -160`
- 基线结果：`739 passed, 4 skipped`。
- prevention / 注意事项：
  - 默认用户路径只能要求“启动 Gateway”，不能再让用户理解 `kernel.command` / `kernel.base_url`。
  - 默认启动必须后台化；前台阻塞只能保留给显式 `foreground/debug` 路径。
  - 未绑定时必须自动打开浏览器进入登录/绑定，而不是要求用户手动 curl。
  - 绑定完成后必须能直接在 Web IM 里聊天；验证要经过真实入口，而不只是假设 API 已通。
  - 不改 `ROADMAP.md`，不手改 `data/dev-tasks.json`，不做与本 UX 收口无关的重构。

## 计划摘要
- R1：把 `personal_assistant.main` 拆成默认后台启动与显式 foreground 两条入口，保证默认命令尽快返回但仍等待 ready/失败。
- R2：补 Gateway 侧 IM bootstrap client，基于节点 owner 状态自动触发 bind request + 浏览器打开，并把默认 kernel 入口收口成真实可运行的内部值。
- R3：补前端 bind 页面与 chat bootstrap 闭环，让 bind 完成后直接进入 `/chat`，聊天默认选择已绑定节点。

### R1 默认后台启动与前台模式分流
- Context:
  - 旧入口要求用户直接运行 `python -m personal_assistant.main --config ...`，命令会前台阻塞，默认用户路径既不符合“启动即返回”的体验，也让 smoke/debug 与默认路径混在一起。
- Decision:
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/main.py` 新增 `BackgroundLaunchResult`、`launch_gateway_in_background()`、后台 child argv/ready wait 逻辑，并让 CLI 默认走后台启动；仅 `--foreground` 保留前台常驻语义。
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/smoke_runtime.py` 显式传 `--foreground`，避免既有 smoke 被默认后台化破坏。
- Rationale:
  - 默认命令必须尽快把控制权还给用户，但不能把“已启动/未就绪/已失败”混成一类；因此父进程负责等待 ready 并输出 `pid/health_url/log`，而真正常驻的 runtime 仍在 detached child 中运行。
  - foreground 语义只对调试与进程级 smoke 有价值，保留为显式开关可以最小化用户心智负担。
- Evidence:
  - Tests:
    - `python -m pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
    - `python -m pytest -q`
  - Entry:
    - `tests/e2e/test_personal_assistant_main_e2e.py::test_main_default_command_returns_after_background_start`
    - `tests/e2e/test_personal_assistant_main_e2e.py::test_main_foreground_flag_keeps_process_attached_until_sigterm`
    - 全量 `python -m pytest -q` 结果：`750 passed, 4 skipped`
- Rollback:
  - 若后台启动路径后续在目标环境中出现稳定性问题，可先回退 `main()` 的默认分流到 `run_gateway()`，同时保留 `launch_gateway_in_background()` 作为后续 feature flag/实验入口，不影响 foreground smoke。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 进入 R2/R3 的提交拆分与记录收口。

### R2 内核默认内聚与未绑定自动浏览器绑定
- Context:
  - 旧默认配置把 `kernel.command` 指向仓库中不存在的 `python -m agent.server`，同时未绑定节点需要用户手工调用 IM bind API，默认用户路径仍暴露了不该暴露的系统细节。
- Decision:
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/config/local_store.py` 将默认 kernel 入口收口为真实可运行的 `python -m agent.platform.http_api.app`。
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/main.py` 增加 `_IMBootstrapClient` 与 `post_im_connect` 钩子，Gateway 连上 IM 后先检查 owner；未绑定时调用 `/im/v1/bind` 并通过 `webbrowser.open()` 打开绑定页。
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/api/deps.py`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/api/routes/account.py`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/application/bind_service.py`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/infra/repositories.py` 打通 `bind_token` confirm 与本地真实 `bind_url`，默认指向 `http://127.0.0.1:4173/bind/confirm`，同时允许 `IM_BIND_BASE_URL` 覆盖。
- Rationale:
  - 默认 kernel 入口必须是“仓库里真实存在且可启动”的实现，否则“省略配置即可启动”只是伪承诺。
  - bind 引导属于 Gateway/IM 边界职责，而不是用户的手工运维步骤；连接 IM 后立刻检查绑定状态，可以在最短路径上完成自动引导，同时已绑定节点不会重复打开浏览器。
- Evidence:
  - Tests:
    - `python -m pytest -q tests/unit/personal_assistant/test_local_store.py tests/im_service/contract/test_account_binding_contract.py tests/im_service/integration/test_account_binding_api.py tests/e2e/test_m112_real_process_roundtrip_e2e.py`
    - `python -m pytest -q`
  - Entry:
    - `tests/e2e/test_m112_real_process_roundtrip_e2e.py::test_gateway_runtime_opens_browser_bind_flow_for_unowned_node`
    - `tests/im_service/integration/test_account_binding_api.py`
    - 全量 `python -m pytest -q` 结果：`750 passed, 4 skipped`
- Rollback:
  - 若自动浏览器拉起需要按平台差异降级，可保留 `bind_token`/真实 `bind_url` 契约，临时去掉 `webbrowser.open()` 调用并仅记录 bind URL，不影响 IM API 与前端闭环。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 收口前端 bind→chat 闭环记录，并准备按 R1/R2/R3 拆提交。

### R3 Web IM 绑定页与绑定后直聊闭环
- Context:
  - 自动打开浏览器后，前端还缺真实可操作的 bind 页面与绑定后默认聊天节点选择；未绑定场景下 `/chat` 也会继续展示可发送输入框，用户无法明确判断当前状态。
- Decision:
  - 新增 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/frontend/src/features/chat/bind-confirm-page.tsx`，在 `/bind/confirm?token=...` 中调用 `confirmBindToken()`，成功后直接 `navigate("/chat")`。
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/frontend/src/features/chat/im-chat-api.ts` 与 `chat-api.ts` 增加 `ChatBootstrapState`、`getChatBootstrapState()`、`confirmBindToken()`、`resetChatBootstrapState()`，并让 `sendMessage()` 在无 bound node 时显式报错。
  - 在 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`、`components/message-pane.tsx`、`src/app/router.tsx` 中接入 bind route、chat bootstrap 默认会话跳转，以及未绑定禁发/提示文案。
  - 为 mock API 补齐同名导出，保证 mock/im 双模式下前端构建与测试都保持一致契约。
- Rationale:
  - 绑定页必须消费真实 token 并把结果写回 chat bootstrap，才能让“浏览器打开 → 完成绑定 → 直接去聊天”成为单一路径。
  - 未绑定状态下禁发与提示文案是为了消除 silent failure：用户应该明确知道是“尚未绑定”，而不是误以为消息已经发往某个默认节点。
- Evidence:
  - Tests:
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/frontend run test`
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/IM/frontend run build`
    - `python -m pytest -q`
  - Entry:
    - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
    - `src/IM/frontend/src/app/router.test.tsx`
    - `src/IM/frontend/src/features/chat/chat-layout.test.tsx`
    - 前端门禁结果：`13 passed`；构建结果：`vite build` 成功
- Rollback:
  - 若 bind 页面交互需要进一步产品化，可保留 `confirmBindToken()` 与 `/bind/confirm` 路由，仅回退未绑定禁发文案与默认跳转策略，不破坏已打通的 API 闭环。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 按 R1/R2/R3 组织提交；`data/dev-tasks.json` 仍保持不手改。

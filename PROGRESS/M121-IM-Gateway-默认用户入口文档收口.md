# M121 IM/Gateway 默认用户入口文档收口

## 启动记录
- 已阅读：`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`ACCEPTANCE/M120-acceptance.md`。
- 注释/文档规范承诺：文档只写用户可执行路径、约束与状态预期，不把 operator-only API 细节伪装成默认主链路。
- 当前处境：M121，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M121`，branch=`milestone/M121`。
- 测试门禁：`cd src/IM/frontend && npm run build`
- 基线结果：
  - 首轮即失败：`sh: tsc: command not found`
  - 判断：当前 worktree 尚未具备前端依赖，属于环境前置问题，不是 M121 文档行为回归；后续仍需把最终门禁结果记录为证据或阻塞。
- 当前确认的实现事实：
  - M122 已让 IM host 在 `dist` 存在时直接服务 `/`、`/chat`、`/settings/*`、`/bind/confirm`，不再要求用户先知道前端 dev server URL。
  - M123 已让 Gateway 默认本地启动补齐本地 kernel bearer token，并在未绑定/启动失败时输出 `NEXT ...` 指引，且把 actionable `last_error` 回写到 IM 节点板。
  - M120 的失败根因是默认入口不可发现、runbook 过度依赖 curl、用户无法理解未绑定/已绑定差异。

### R1 README 与 runbook 收口单一路径
- Context:
  - 现有 `README.md` 只给 Gateway 配置片段，把完整路径外包给 runbook；runbook 又以 operator API 手册展开，正常用户需要跨文档和 curl 才能拼出主链路。
  - 当前产品行为已具备更短默认路径：启动 IM host、启动 Gateway、打开 IM host `/`，未绑定时按 Gateway 给出的 bind 链接完成绑定，已绑定时直接进 Web IM。
- Decision:
  - 把 `README.md` 收口成单一 `start here` 入口，先给出最短默认链路，再把深度 runbook 作为补充。
  - 把 `docs/operator-runbook.md` 改写为“默认用户路径优先，operator/debug 次之”，明确未绑定/已绑定的分支行为与节点板反馈。
- Rationale:
  - 这能直接回应 M120 的 blocking 问题，同时不改任何实现；正常用户先完成主链路，operator API 再下沉到附录/排障即可。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run build` 当前基线失败于 `tsc: command not found`，说明先要解决 worktree 依赖复用问题，才能做最终门禁
  - Entry: `src/IM/app.py` 与 `tests/im_service/unit/test_app_factory.py` 已固定 IM host `/`、`/chat`、`/bind/confirm` 在 dist 存在时直接服务 Web IM 壳
  - Entry: `PROGRESS/M123-Gateway-默认启动与绑定反馈收口.md` 已记录 Gateway 对未绑定/bootstrap failure 输出 `NEXT ...` 并写回 `/im/v1/nodes.last_error`
- Rollback:
  - `74a6594`（计划提交）
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 提交 Red 基线后，更新 `README.md` 与 `docs/operator-runbook.md`

### R2 前端 README 与附录降级对齐
- Context:
  - `src/IM/frontend/README.md` 仍把 `http://127.0.0.1:4173/chat` 当作用户入口，和 M122 后的 IM-hosted 默认入口口径冲突。
  - runbook 中创建用户/会话/发消息的 curl 目前仍占据主链路，会误导正常用户以为必须手工打 API 才能聊天。
- Decision:
  - 将前端 README 收口为“默认用户入口 + 前端开发模式说明”，把 `4173` 明确标为前端开发/dev-server 路径，而不是默认用户入口。
  - 将 runbook 中 bind/message curl 降级为调试附录，只保留用户需要知道的 UI/状态路径。
- Rationale:
  - 文档要反映当前产品已有能力，而不是保留历史开发路径作为默认心智。
- Evidence:
  - Tests: `tests/acceptance/test_im_gateway_real_acceptance.py`、`tests/im_service/integration/test_account_binding_api.py`、`tests/unit/personal_assistant/test_main.py` 共同证明“绑定完成后 `owned_node_ids` 建立”“Gateway 未绑定时会打开 bind URL”“已绑定节点不会再次打开浏览器”
  - Entry: `PROGRESS/M122-Web-IM-默认入口恢复可达.md` 已记录 IM-hosted 入口在浏览器中会从 `/` 落到 `/chat`
- Rollback:
  - `74a6594`（计划提交）
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 在 README/runbook 收口后，再处理 `src/IM/frontend/README.md` 与最终一致性复核

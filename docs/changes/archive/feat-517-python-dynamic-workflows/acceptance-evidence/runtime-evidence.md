# feat-517 Round 1 runtime evidence

本文件只记录真实产品入口的可复查 locator 与脱敏结果摘要，不复制 LLM Proxy request/response payload。

## CLI：Workflow enabled

- 环境：`codexOAuth:gpt-5.6-luna`，`NANO_MULTIAGENT_WORKFLOW_SUBAGENT_MODEL=codexOAuth:gpt-5.6-luna`，`NANO_MULTIAGENT_REASONING_EFFORT=low`。
- 交互式入口：模型发起 `Workflow` 后立即得到 `blocked_by_hook=True` 与 `The user doesn't want to proceed ... can_use_tool raised`；终端未显示审批选项，也未生成 run/task。
- 非交互入口：session `sess_c4ac9aa271ddd664`，run `run_5ad4f65162a874e9`，workflow `wf_5625c26c39b2f7ab`，task `wt_a3e9dbc34795c375`。
- 固定结果：`WORKFLOW_LUNA_OK`；1 Agent；5.057s；child usage 3,901 input + 23 output tokens。
- 用户面：async launch 在约 9ms 返回；`/workflows` 的 list/detail 显示 completed、Agent、usage、duration、result、diagnostics 与 script；保存 project 得到 `.nanocode/workflows/acceptance-minimal.py`。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-12-51_171_sess_c4ac9aa271ddd664/`。首个 parent request 为 Luna，10 tools，其中 Workflow=1；child request 为 Luna，8 tools，其中 Workflow=0；continuation 仍为 Luna。

## CLI：Workflow disabled

- 环境：同上，另设 `NANOCODE_DISABLE_WORKFLOWS=1`。
- session：`sess_60ab0af350ac22f4`。
- 用户面：明确要求 Workflow 时未产生模型 Workflow 调用；但交互式 `/help` 仍列出 `/workflows`、`/config`、`/effort`，实际执行 `/workflows` 返回 unknown command。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-15-36_806_sess_60ab0af350ac22f4/`。Luna request 的 Workflow tool object=0。

## Web IM：Workflow enabled / disabled

- Enabled conversation：`7865ebf79aa440eaa5bd453eb0bdb95d`。
- Enabled provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-22-43_021_sess_1f5034b9521bacd0/`。parent 为 Luna，12 tools，Workflow=1；Workflow child request 实际为 `deepseek:deepseek-v4-flash`。
- Permission pending：桌面与移动 viewport 均只有既有 PermissionCard 与 raw script；Allow once 后出现 authorized async launch；Deny 后直接得到无 running history、无 duration 的 denied 终态。
- 完成结果：后台返回固定字符串 `WEB_WORKFLOW_LUNA_OK`，但后续普通回复的“过程”没有 Workflow background-return；刷新后和移动 viewport 同样缺失。
- Tool detail：展开后只看见 `WORKFLOW INPUT` / `LAUNCH RESULT` 标题，没有可读的脚本或 launch result 值。
- Disabled conversation：`cd5aa171660b4e8eaf7a57448488942b`。
- Disabled provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-27-46_879_sess_a1140dd52c10f086/`。Luna request 为 11 tools，Workflow=0；slash picker 不再出现 Workflow 命令。
- Browser console：本轮验收期间 0 error / 0 warning。

## 飞书专用测试 profile

- 前置：`feishu-e2e.env` mode 0600；非 default profile `e2e-feishu-testagent` 的 verify 通过；`e2e-feishu-probe.py` ingress probe 通过。
- 真实入口：测试用户向专用 `测试agent` 私聊；明确一 Agent Workflow 消息 `om_x100b68a363902ca8dd178a56549ca58`。
- 权限：收到既有通用 interactive card（Workflow / Allow once / Always / Deny），消息 `om_x100b68a3617fd8a4c2ec5ab9fd759d3`；在真实飞书页面点击 Allow once。
- 结果：`FEISHU_WORKFLOW_LUNA_OK`；workflow `wf_5ea23ce78ae78b2a`；1/1 Agent；4.108s；usage 4,132 input + 12 output；终态只投递一次。
- `/workflows` 显示 completed；对 completed run 请求 stop 后返回包含 result、usage、artifacts 的 completed 详情。
- Enabled/disabled provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-38-48_769_sess_02df23a562e19608/`。enabled parent 为 Luna，12 tools，Workflow=1；child 实际为 `deepseek:deepseek-v4-flash`，Workflow=0；disabled next turn 为 Luna，11 tools，Workflow=0。
- 取消 Workflow 后 `/workflows` 无回复；随后明确要求 Workflow 的消息没有产生 Workflow tool call，但模型转而请求 Bash 权限，已拒绝。

## 隔离与清理

- Web/Feishu 均使用 unit worktree 的隔离 IM/Gateway、空闲端口和专用 runtime data。
- 所有由 reviewer 启动的 Vite、IM、Gateway 与 Playwright daemon 已停止；隔离端口不再监听；运行态 `.nanocode`、receipts 与 runtime data 未入仓。

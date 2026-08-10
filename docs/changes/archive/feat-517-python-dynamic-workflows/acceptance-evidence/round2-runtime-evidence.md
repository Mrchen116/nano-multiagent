# feat-517 Round 2 targeted runtime evidence

本文件只记录真实入口结果与脱敏 request locator，不复制 LLM Proxy payload。

## CLI 默认交互与恢复

- 环境：parent/child 均配置 `codexOAuth:gpt-5.6-luna`，reasoning effort 配置 `low`，只运行一个无工具 Agent。
- session：`sess_5e77831ef574f1fb`；run：`wf_7f53bce070f65bb3`。
- 默认交互审批已出现：`Permission request: Workflow`，含 `Allow once / Always allow / Deny`；选择 `Allow once` 后返回 running，最终 completed 1/1。
- 最终结果：`ROUND2_CLI_LUNA_OK`；usage 3,900 prompt + 11 completion；23.249s。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_16-19-48_904_sess_5e77831ef574f1fb/`。parent 为 Luna、10 tools、Workflow=1；child 为 Luna、8 tools、Workflow=0。
- 退出进程后，以 `--resume sess_5e77831ef574f1fb` 恢复同一 session；`/workflows` 可列出 completed run，但 TTY `p` 返回 `Workflow control failed: unknown Workflow run: wf_7f53bce070f65bb3`。显式 `/workflows wf_7f53bce070f65bb3 resume` 在同 session 和新 session 都只返回 `Error: failed to run /workflows`、`Layer: input`、`Suggestion: check configuration and retry /workflows`。
- disabled：设置 `NANOCODE_DISABLE_WORKFLOWS=1` 后，`/help` 只列 `/help /new /use /session /tools /compact /history /exit`；`/workflows` 返回 unknown command，与发现列表一致。

## Web IM lifecycle、detail 与 background return

- 隔离入口：unit worktree 的独立 IM/Gateway/Vite；conversation `24869c5c5d25471591b499e5cfd52a80`；Web Agent profile 选择 Workflow、Luna、Low。
- run：`wf_10236bbc577388d4`；task：`wt_57ea441f27d828f4`；固定结果 `ROUND2_WEB_LUNA_OK`。
- Workflow launch detail 展开后可见完整 inline Python input，后接 `✓ async_launched`、name、runId、taskId、scriptPath、transcriptDir。
- 后续普通回复同时显示正文 `ROUND2_WEB_LUNA_OK` 和 `Process · 1 background return`。展开可见 completed、task/run、duration 5.257s、Raw result、usage 3,149 tokens、output_file、diagnostics 与 resume_hint。
- 浏览器 reload 后同一 task/run 仍附着在同一普通回复；desktop 与 390×844 mobile 均可展开看到相同 raw result/usage/artifacts。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_16-35-15_233_sess_0f67c32a3ca609c7/`。

## PA model / effort routing

- 第一条最小 Workflow：parent request 是 Luna + `output_config.effort=low`；child request 是 Luna，但没有 `output_config.effort`；terminal continuation 是 Luna + low。
- 第二条 one-child Bash smoke：parent request 是 Luna + low；child 及 child-after-tool requests 是 Luna，但均没有 `output_config.effort`；最终消费 background return 并生成可见综合回复的 request 切换为 `deepseek:deepseek-v4-flash` + low。
- 因此 child model 已从 Round 1 的 DeepSeek 修成 Luna，但 child effort 没有继承到 provider request，且 terminal continuation 仍可回落到 DeepSeek。

## Tagged child permission product smoke

- CLI 与 Web 分别运行一个 child；child 只调用一次 Bash：`printf ROUND2_*_CHILD_PERMISSION_OK`。
- 两个入口都无卡死并完成，provider 记录 child Bash tool call 与后续 Luna request；Web 最终正文与 background return 都显示固定输出。
- 当前测试权限策略自动处理该无害 Bash，未出现独立 child permission card；因此本轮证明单 child tool journey 不阻塞，但无法从用户面证明多 tagged request 的 stdin 精确归属。

## Screenshots

- `round2-web-agent-luna-low-workflow-enabled-desktop.png`
- `round2-web-workflow-completed-expanded-desktop.png`
- `round2-web-background-return-details-desktop.png`
- `round2-web-background-return-after-reload-desktop.png`
- `round2-web-background-return-after-reload-mobile.png`
- `round2-web-child-tool-completed-desktop.png`

## Isolation

- 没有打开或控制真实 Chrome / 真实飞书 UI，也没有向飞书发送消息。
- 只使用隔离 Web IM、独立 Playwright Chromium、CLI 与 LLM Proxy 日志。

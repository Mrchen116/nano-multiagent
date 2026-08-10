# feat-517 Round 3 targeted closure evidence

本文件只记录真实产品入口结果与脱敏 request locator，不复制 LLM Proxy payload。

## CLI restart、same-session replay 与 cross-session diagnosis

- 环境：parent/child model 均配置 `codexOAuth:gpt-5.6-luna`；只运行一个不调用工具、返回固定字符串的 Agent。
- 原 session：`sess_11fad28fc99861da`；原 run：`wf_c7d932d0b9f8a56a`；结果 `ROUND3_CLI_LUNA_OK`；usage 3,903 prompt + 24 completion；9.234s。
- 退出 CLI 后以 `--resume sess_11fad28fc99861da` 重启；`/workflows` 立即列出原 completed run，不再报 unknown run。TTY `p` 在 completed 项上保持 terminal 状态且不报错；completed rerun 使用显式 `/workflows wf_c7d932d0b9f8a56a resume`。
- 显式 resume 创建 `wf_a670ff738032712c`，用户面显示 completed、同一结果、2ms；诊断 artifact 显示 `resumed_from=wf_c7d932d0b9f8a56a`、child `replayed=true`、无新增 child usage。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_17-10-18_684_sess_11fad28fc99861da/`。原 run 只有一个 child request；resume 后只有消费 cached terminal notification 的 Luna continuation，没有第二个 child request。
- 新建 `sess_41cd839c64ede1d4` 后对原 run 执行 resume，得到精确用户诊断：`resume Workflow run belongs to a different parent session`；建议从 Workflow parent session 重试。

## PA 连续两个 one-child Workflow model / effort routing

- 隔离入口：unit worktree 独立 IM/Gateway/Vite + 独立 Playwright Chromium；Web conversation `9860a58c59b7413a90bda8d89482dda6`；Agent profile 为 Workflow enabled、Luna、Low。
- Provider locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_17-18-10_401_sess_884d41956f740fb2/`。
- 第一个 Workflow：parent request、permission 后 continuation、child request、terminal continuation 分别位于 `17-18-10_401`、`17-18-52_307`、`17-18-52_576`、`17-19-46_929`；四次均为 Luna + `output_config.effort=low`。
- 第二个 Workflow：parent request、permission 后 continuation、child request、terminal continuation 分别位于 `17-20-22_496`、`17-20-58_889`、`17-20-59_251`、`17-21-58_311`；四次均为 Luna + `output_config.effort=low`。
- 两个 child request 均只有 10 个 inherited tools、无 Workflow tool；可见结果分别为 `ROUND3_WEB_ONE_OK`、`ROUND3_WEB_TWO_OK`，各自附着一条 background return。该 session 的两次 Workflow 链路没有 DeepSeek request。

## 后台 Agent 最小补充旅程

- 同一隔离 conversation 以 `Agent(run_in_background=true)` 启动一个无工具 child，固定返回 `ROUND3_AGENT_BACKGROUND_OK`。
- 原 Agent launch 行保留 dispatch prompt、`async_launched` 与 output file；后续普通回复正文显示固定结果，并在同一“过程”中显示一条 Agent background return。
- 展开可见 task/agent identity、completed、12.210s、tool use count 0、Raw result、8,214 tokens 与 output artifact；reload 后同一返回仍附着且不重复。
- 此补充旅程用于关闭后台 Agent 展示的既有 inconclusive，不用于 R2-1 的 Workflow child effort 证明。它保持 Luna；direct Agent child request 未显式携带 effort 字段，因此不把它记作 Luna+low Workflow routing 证据。

## Screenshots

- `round3-web-two-workflows-completed.png`
- `round3-web-agent-background-completed.png`

## Isolation

- 没有打开或控制真实 Chrome / 真实飞书 UI，也没有发送任何外部消息。
- 只使用隔离 IM/Gateway/Vite、独立 Playwright Chromium、coding CLI 与 LLM Proxy 日志；没有进行多 Agent、并发或规模实验。

# bugfix-441 — 回归验证

> 对齐: `incident.md` / `design.md`
> Round: 1
> Date: 2026-06-27
> Reviewer mode: bugfix full

## Verdict

**Verdict: fail**

**Highest Required Action: fix-implementation**

本轮未能给出产品可交付的 pass。原因不是已观察到实现违反验收标准，而是必验的真实 Web IM 工具旅程未完成，关键 Scenario 仍为 `inconclusive`；按 change-reviewer 规则，任一必验 Scenario 未被真实 UI 证据关闭即不能 pass。

## 复现验证

### Environment takeover

- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-441`
- Branch: `unit/bugfix-441`
- Sync: `git fetch origin` + `git pull --ff-only origin unit/bugfix-441`，结果为 already up to date at `9e16a3a1`.
- IM: started isolated on `127.0.0.1:60615`, with temp DB `/private/tmp/bugfix441-review-30160/im.sqlite3`.
- Gateway: started isolated with temp config `/private/tmp/bugfix441-review-30160/gateway-config.yaml`, `--foreground --auto-bind`, node `bugfix441-review-node`.
- Frontend: Vite dev server started on `127.0.0.1:60616`, `VITE_IM_PROXY_TARGET=http://127.0.0.1:60615`.
- Browser path: real Web IM UI via Chromium/Chrome, not HTTP-only replacement.

### What was exercised

1. Registered and logged in user `nano` / `nano1234`.
2. Confirmed Gateway node `bugfix441-review-node` was online through IM node state before the browser journey.
3. Opened Web IM login page through Playwright at `http://127.0.0.1:60616/login`.
4. Logged in through the real UI and reached `/chat`.
5. Opened the real `default-agent` settings page, observed `default-agent` online, and opened the agent chat from the `Open chat` button.
6. Sent this real UI message to trigger a long bash tool call:

   ```text
   Use the bash tool to run exactly this command, then report the result: sleep 20 && echo BUGFIX441_REVIEW_BASH_DONE
   ```

### Blocking observation

The first run did not reach a tool call. The agent reply showed:

```text
模型调用失败:openai_compat: profile=kimiCoding 不支持协议 openai_chat
```

This was traced to the reviewer-created temp Gateway config selecting `openai_compat` for `kimiCoding:K2.6`. I stopped the Gateway, changed only the temp config under `/private/tmp`, and restarted Gateway with the `anthropic` profile shape from project instructions.

After restart, shell-based Playwright commands required elevated execution but Codex elevation was unavailable due the current usage limit. Node REPL Playwright could not launch its bundled browser, and launching local Chrome failed on macOS permission access. Computer Use could inspect Chrome, but its text input path stripped `:` characters from localhost URLs, making it unable to open the isolated `127.0.0.1:60616` page. I stopped the services I started and did not continue with API-only substitutes, because the acceptance standard explicitly requires the real Web IM UI.

## 验收标准覆盖

### Requirement: 工具执行中展示参数侧信息

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| Long bash running row shows collapsed summary and expanded command | `incident.md` 期望 + `design.md Runbook for Reviewer` | Real Web IM UI, send long bash command and inspect running tool row | Journey started, but first agent run failed before tool call; rerun blocked by browser tooling | inconclusive | Required UI state was not observed. |
| Agent subtask running row shows summary and expanded prompt | `design.md` M1 reviewer exit standard | Real Web IM UI, trigger agent subtask and inspect running tool row | Not reached | inconclusive | Required UI state was not observed. |
| web_search running row shows summary and expanded query | `design.md` M1 reviewer exit standard | Real Web IM UI, trigger web_search and inspect running tool row | Not reached | inconclusive | Required UI state was not observed. |

### Requirement: 执行中不出现伪完成态

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| Agent running card does not show completed marker | `incident.md` 不变量 + `design.md` 决策 1 | Real Web IM UI during agent tool running state | Not reached | inconclusive | Required UI state was not observed. |
| web_search running card does not show `No results` empty state | `design.md` 决策 1 / Runbook | Real Web IM UI during web_search running state | Not reached | inconclusive | Required UI state was not observed. |
| Running rows still keep running pulse/status until completion | `incident.md` 不变量 | Real Web IM UI during long-running tools | Not reached | inconclusive | Required UI state was not observed. |

### Requirement: 执行完展示参数 + 结果

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| bash completed row shows command plus stdout/result | `incident.md` 不变量 | Real Web IM UI after long bash completes | Not reached | inconclusive | Required UI state was not observed. |
| agent completed row shows prompt plus result | `design.md` tool table / Runbook | Real Web IM UI after agent subtask completes | Not reached | inconclusive | Required UI state was not observed. |
| web_search completed row shows query plus final result/error state | `design.md` tool table / Runbook | Real Web IM UI after web_search completes | Not reached | inconclusive | Required UI state was not observed. |

### Requirement: send_message / cron 结构化展示改善

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| send_message running/completed display is structured, not raw JSON | `incident.md` Q5 + `design.md` 决策 2 | Real Web IM UI with send_message tool allowed and triggered | Not reached | inconclusive | Required UI state was not observed. |
| cron running/completed display is structured, not raw JSON | `incident.md` Q5 + `design.md` 决策 2 | Real Web IM UI with cron tool allowed and triggered | Not reached | inconclusive | Required UI state was not observed. |

## Issues

### 1. Required Web IM tool journeys were not completed

- Severity: blocking
- Regression Relation: unclear
- Recommended Action: fix-implementation
- Action Rationale: The unit cannot be accepted while all required user-visible tool states remain inconclusive. This report does not prove a product defect in the implementation; it proves the reviewer did not obtain the required real-UI evidence. The next round should rerun the exact Web IM journeys from a working browser automation path and close each Scenario with screenshots or accessibility evidence.

## 回归测试

No product regression pass can be claimed from this round. The only completed product checks were setup-level:

- Web IM login worked against the isolated Vite/IM stack.
- Agent settings showed `default-agent` online.
- The `Open chat` UI created/opened an agent conversation.
- The chat composer accepted and sent a user message.

The core bugfix behavior was not observed.

## 自动化测试增量

Worker progress reports these automated gates, but this reviewer did not treat them as a substitute for the required product journey:

- `pytest -m "not e2e"`: reported green in M1 progress after R3.
- Frontend `npm run test`: reported green in M1 progress.
- Frontend `npm run build`: reported green in M1 progress.
- M1 progress also records prior worker-owned browser screenshots under `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/evidence/`.

Those artifacts are useful implementation evidence, but change-reviewer acceptance still requires independent real Web IM confirmation; this round did not complete it.

## Side Findings

- The reviewer-created initial temp config had an invalid provider/model pairing. This was corrected only in `/private/tmp/.../gateway-config.yaml` and is not a repository change.
- Computer Use text entry stripped `:` from localhost addresses in this environment, preventing navigation to `127.0.0.1:60616`.

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/<包>/spec.md`（长青行为契约层，本 unit 触及的包；通常由 orchestrator §7.0 收尾归并写入）：需要更新；`design.md` 已列出 kernel / im / gateway delta-spec，收尾归并应覆盖工具 running 参数展示与 Gateway tool_start payload。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新。

## Reviewer Handoff

Recommended rerun path:

1. Start isolated IM, Gateway, and Vite exactly as above, but use a known-good Gateway `llm` profile from the main user config or AGENTS sample.
2. Open `http://127.0.0.1:<vite_port>/` with a browser automation path that can reliably enter localhost URLs containing `:`.
3. Through Web IM, trigger long bash, agent subtask, web_search, send_message, and cron.
4. For each required tool, capture running expanded card and completed expanded card evidence.


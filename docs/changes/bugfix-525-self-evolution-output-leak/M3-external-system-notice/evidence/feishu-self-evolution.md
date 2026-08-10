# M3 专用飞书 self-evolution 验收证据

日期：2026-08-10。环境：`bugfix-525-M3` worktree、隔离 IM/Gateway/workspace、受控 OpenAI-compatible LLM、verified non-default 专用飞书 E2E profile。未使用生产 Bot、生产 chat 或用户生产 Gateway config。

## 命令与身份门禁

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$PWD" --feishu
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-feishu-probe.py --wt "$PWD"
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-feishu-self-evolution.py --wt "$PWD"
./scripts/e2e-down.sh --wt "$PWD"
```

- guard：env 存在、profile 非 default、profile verified、App identity 匹配、Bot identity verified 且匹配，全部通过。
- `e2e-up --feishu` 成功；`e2e-feishu-probe.py` 输出 `Feishu E2E ingress probe passed`。
- journey nonce：`bugfix525-m3-c2b69dd4f41b`。
- 专用 chat：`oc_3b9bdbedb101b1b9ccf6353ac68c4777`；shadow conversation：`28655f111be14b1bb22d9f8fc7966601`。
- route anchor：`om_x100b68a87b76eca4dd48f439f3b0e45`；no-save seed/trigger：`om_x100b68a878e7e0a0de09fa146298cbe` / `om_x100b68a878b6cca4c07bd44935fe3b0`；受控失败 trigger：`om_x100b68a8798118a0de3e569ad53835a`；Skill trigger：`om_x100b68a8790760a8c2371f5fa761b73`。

## 产品观察

- no-save：两轮真实飞书入站均完成前台回复；受控 fixture 另行确认 private review 真执行。飞书与 shadow IM 均无 self-evolution notice，页面窗口内无 `Nothing to save.` 或 raw review 输出。
- 失败：真实 review 执行 `memory(add)` 到受控非法 target，ToolResult 失败；前台回复完成，两端均无 update notice，也无 tool error/stack 泄漏。
- Skill：真实 review 执行 `skill_manage(create)`；前台 terminal 后，原飞书 chat 只出现一次 `· background self-evolution review: skills updated` 普通 Bot 文本，shadow IM 只出现一次 `updated_targets=["skills"]` structured system notice。`deterministic-review-c2b69dd4f41b/SKILL.md` 存在，Agent 保持 explicit allowlist 且自动包含该 Skill。
- 来源切换：同一 shadow conversation 从内部 IM 触发真实 `memory(add)` 后，只出现一次 `updated_targets=["memory"]` structured notice；飞书 chat 的 Skill notice 总数仍为一。
- 隐私：本次 nonce 对应的飞书与 shadow message window 均不含 `Saved:`、`Nothing to save.`、受控失败 raw reply、review prompt/tool/turn 或 traceback。

## 启动 blocker 与清理

- 首次真栈暴露稳定 baseline blocker：macOS spawn child 在 `_worker_bootstrap` 前导入 lark SDK，超过原先 `max(5, join_timeout)` 的初始化等待。红测观察 short shutdown join 只得到 5 秒 startup budget；修复后 startup 独立为 30 秒，退出 join timeout 不变，focused worker regression 通过。
- 重复验收时发现固定 Skill 名已由上一轮真实创建，新的 `create` 因无实际写入而被 production true-receipt 门禁正确静默。fixture control 改为按本轮 nonce 提供唯一 Skill 名后，重新跑通同一真栈；这只修复 harness 的可重复性，不改变生产事件分类。no-save/失败的 shadow 负面断言也在本轮直接通过。
- journey harness 只在 worktree 中改写生成的 Gateway config、重置其 session binding、启动受控 fixture；使用 production Gateway/Feishu adapter/IM relay/config-sync 和 external sender，不写用户配置。
- `e2e-down.sh` 后观测：IM PID stopped、Gateway PID stopped、IM port closed、Feishu listener lock removed、controlled fixture stopped；运行期 PID/config/log/LLM record 未提交。

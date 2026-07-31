# M121 IM/Gateway 默认用户入口文档收口

## 前置确认
- [x] 已阅读 `/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`
- [x] 已阅读 `/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- [x] 已阅读 `/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`
- [x] 已阅读 `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M120-acceptance.md`
- [x] 已阅读 `README.md`、`docs/operator-runbook.md`、`src/IM/frontend/README.md`

## 当前处境
- Milestone: `M121 / IM-Gateway 默认用户入口文档收口`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M121`
- branch: `milestone/M121`
- 测试门禁：`cd src/IM/frontend && npm run build`
- 允许改动：`README.md`、`docs/operator-runbook.md`、`src/IM/frontend/README.md`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json(only via script)`
- 禁止改动：`src/**` 实现代码、`tests/**`、无关文档、`ROADMAP.md`
- prevention_rules:
  - 文档必须围绕“正常用户默认路径”，不是 operator-only API 手册。
  - 不再让用户靠手工拼 `bind/message` curl 才能理解主链路。
  - 文档内容必须与当前真实行为对齐：M122 已恢复 IM-hosted 入口，M123 已收口 gateway 默认启动 token/bootstrap/bind feedback。
  - 只做文档收口，不改实现代码。

## 基线
- 命令：`cd src/IM/frontend && npm run build`
- 结果：失败
- 失败点：`sh: tsc: command not found`
- 当前判断：
  - 当前 worktree 缺少前端本地依赖，导致门禁停在环境前置层。
  - 该失败不属于 M121 文档范围，但会影响最终验证，需要在收口前处理或明确记录。

## Roadpoints

### R1 README 与 runbook 收口单一路径
- Acceptance:
  - `README.md` 明确给出单一 `start here` 路径，让正常用户先启动 IM、再启动 Gateway、再打开 Web IM，而不是在多个章节间跳转猜测。
  - 文档明确给出默认 Web IM URL、Gateway 启动命令，以及为何默认不需要手工补 kernel token。
  - 文档明确区分“未绑定”与“已绑定”两种状态下的预期行为，包括 Gateway 输出/浏览器动作/节点状态。
  - 主链路不再要求用户先学会 `curl /im/v1/bind`、`curl .../messages` 才能理解产品。
- Tests Plan:
  - unit: 不选；本 Roadpoint 为文档收口，无独立逻辑单元。
  - contract: 不选；不引入新协议。
  - integration: 选择，基于现有实现/测试与文档比对，确认默认入口、默认命令、状态反馈叙述不漂移。
  - e2e: 选择，使用 `npm run build` 作为当前唯一门禁，并结合既有 M122/M123/M120 证据核对文档主线。
- Expected Tests:
  - `cd src/IM/frontend && npm run build`
  - 证据核对：`ACCEPTANCE/M120-acceptance.md`、`PROGRESS/M122-Web-IM-默认入口恢复可达.md`、`PROGRESS/M123-Gateway-默认启动与绑定反馈收口.md`
- DoD:
  - README/runbook 已出现同一条默认路径
  - 主链路不再依赖隐藏 curl 知识
  - `PROGRESS` 写清证据、边界与回滚点
  - 完成 C1/C2/C3
- 状态: DONE

### R2 前端 README 与附录降级对齐
- Acceptance:
  - `src/IM/frontend/README.md` 从“独立前端开发说明”收口为“默认用户入口 + 开发调试补充”，不再把 `4173/chat` 写成唯一用户入口。
  - 文档解释 IM host 的 `/`、`/chat`、`/bind/confirm` 与 built dist 的关系，和 M122 当前行为一致。
  - 若保留 curl/API 内容，必须明确降级为调试/附录路径，不得作为正常用户主链路。
  - 三份文档之间的 URL、命令、状态说明保持一致。
- Tests Plan:
  - unit: 不选；纯文档工作。
  - contract: 不选；不改协议。
  - integration: 选择，逐份比对 README/runbook/frontend README 的 URL 与状态文案一致性。
  - e2e: 选择，延续 `npm run build` 门禁，并复用 M122/M123 的入口/反馈证据作为产品行为依据。
- Expected Tests:
  - `cd src/IM/frontend && npm run build`
  - 文档一致性复核：`README.md`、`docs/operator-runbook.md`、`src/IM/frontend/README.md`
- DoD:
  - 三份文档已统一默认入口口径
  - curl/API 仅保留为调试或附录
  - `PROGRESS` 已记录最终主线与残余风险
  - 完成 C1/C2/C3
- 状态: DONE

## 产出清单
- `TASKS/M121-IM-Gateway-默认用户入口文档收口.md`
- `PROGRESS/M121-IM-Gateway-默认用户入口文档收口.md`
- `README.md`
- `docs/operator-runbook.md`
- `src/IM/frontend/README.md`

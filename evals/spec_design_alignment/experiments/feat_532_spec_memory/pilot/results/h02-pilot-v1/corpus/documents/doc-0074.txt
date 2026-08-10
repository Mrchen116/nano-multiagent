# refactor-435: 据 bugfix-433 复盘加固 change-* SDD skills

## Relations

- Refs: `docs/changes/bugfix-433-image-multi-turn-persistence/retro-pipeline-rootcause.md`（本 unit 全部改动的依据，P4/P5/P6 三条发现 + 按-skill 改进清单都在那；该 retro 在 `unit/bugfix-433` 分支）
- Related: bugfix-433（复盘对象，本 unit 不改其代码，只改流程 skill）

## 背景 / 动机

bugfix-433 收尾做了取证式全链路复盘（见 Refs）。复盘出 5 条有效发现，其中 **3 条是 change-* SDD skill 自身的流程/机制缺陷**，与具体需求无关、会复发，故单独立 unit 把它们固化进 skill：

- **P4**：orchestrator 做 scope/严重性决策时，把一个「外部可查的事实」（某模型支不支持图片输入）靠 worker 一次 live 观察去反推，导致 scope B「拍板→撤回→保留」40 分钟三次翻车 + 最终 inconclusive。
- **P5**：change-verifier 报告 push 机制有真 bug——§1 用 `worktree add origin/unit/<id>`（detached HEAD）签出，§5.2 却 `git push origin unit/<id>`（推本地同名分支、不含 detached HEAD 上的报告 commit），三轮报告全静默 `Everything up-to-date`、没上 origin，靠 lead 手动捡回三次。
- **P6**：design 的 `Runbook for Reviewer` 只列旅程步骤、没钉死 review 驱动方式（端到端时客户端那层怎么驱动），reviewer 临场即兴——既花冗余功夫建了不浏览的前端、又留了「该真驱动客户端时偷懒走接口」的口子。

> 复盘另两条（P0 知识在 spec→design 边界蒸发、P1 入站校验判据欠规约）经判断**偏 bugfix-433 本需求**，不够通用，本 unit 不收。P2/P3 已在 retro 中撤回（非缺陷）。

## 目标状态 / 改了什么

三处改动，均**通用、不绑本 repo 词**（不提 IM / 浏览器 / 模型 vision），改的是 skill 指令文本、保留既有流程加防护。

| 发现 | skill / 位置 | 改动 |
|---|---|---|
| P4 | `change-orchestrator/SKILL.md` §3.1.1（接 worker 决策请求处） | 加一条：判断挂在「外部可查事实」（三方库/服务/平台/协议的能力、限额、行为约定）上时，去权威源（官方文档/搜索/项目 doc）查证，别靠一次 live 观察反推。 |
| P5 | `change-verifier/SKILL.md` §5.2（写完报告 commit/push） | push 改 `git push origin HEAD:unit/<id>`（推 detached HEAD 上的报告 commit，不推本地同名分支）+ 先 `fetch`/`rebase origin/unit/<id>` 避并发非快进 + push 后 `merge-base --is-ancestor` 校验真落地（别信 `up-to-date`）。§1 detached 签出保留不动（本地 unit 分支被 orchestrator worktree 占用，只能 detached）。 |
| P6 | `change-design-author/SKILL.md` §Runbook checklist + `assets/design.md` 模板 | `Runbook for Reviewer` 新增必填「Review 驱动方式」：一律端到端真栈；本 unit 不改客户端面 → 可用**客户端实际调用的同一接口**代驱动（替代点击，E2E 路径与真实用户一致），改了客户端面/只在该面可观察 → 必须真驱动客户端面 + 列关键界面。 |

## 范围与非目标

- 在范围：上表 P4/P5/P6 三处 skill 文本改动 + 本 motivation.md。
- 非目标：
  - P0/P1（偏本需求，不够通用，不收）；
  - 不改任何产品代码（`src/`）、不改 bugfix-433 的实现；
  - 不重构 change-* skill 的整体结构，只做点状加固（克制：不因一次问题在 skill 各处撒强调）。

## 验证

均为 skill 指令文本改动，验证即「下一次走 SDD 流程时这些防护生效」：
- P5：下次 verifier 出报告，`merge-base --is-ancestor` 通过、报告真出现在 origin/unit 分支（不再靠手捡）。
- P6：下次 design.md 的 Runbook 段含「Review 驱动方式」一行，reviewer 照其驱动而非即兴。
- P4：下次 orchestrator 遇外部事实型 scope 决策，先查证再拍板（无强制可断言的自动判据，属判断类防护）。

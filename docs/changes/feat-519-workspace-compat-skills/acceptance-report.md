# Feat 519 Product Acceptance Report

## Verdict

- **Verdict:** FAIL
- **Highest required action:** `fix-implementation`
- **Blocking issues:** 1
- **Non-blocking issues:** 0
- **Validated at:** 2026-08-10T02:26:36+08:00
- **Validated commit:** `57127841103db3c5510fa907e96a11bce76a42e5`
- **Executed base:** `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9`
- **Review round:** 1

兼容 Skill 的发现、同名优先级、分组呈现、批量交互、移动端布局、创建页隔离及默认态 SlashPicker 均已在真实产品入口观察到预期结果；但 Agent detail 对第一次 `default_discovery -> explicit_allowlist` 的保存会稳定返回 `409 invalid_agent_config`，显式空保存也同样失败。因此配置无法持久化，spec 要求的重开、下一轮生效、保留聊天历史与显式空 runtime/SlashPicker 旅程均无法成立。本轮不能验收。

## Blocking issue

### B1. Agent detail 无法保存任何显式 Skill 选择

- **Severity:** blocking
- **Recommended action:** `fix-implementation`
- **Affected requirements:** PA 候选选择与保存；显式选择后下一轮生效；新增兼容 Skill 不扩张已保存 allowlist；继续原聊天；显式空选择。

真实复现步骤：

1. 启动隔离 IM + Gateway 和 Vite，登录 `nano`，打开 `e2e` Agent detail。
2. 初始页面显示 `Using all currently discoverable skills`，Workspace 为 `6/6`、Global 为 `29/29`、Compatibility (Claude/Codex) 为 `12/12`。
3. 清空三个分组，仅选择 `ws-claude-only`，点击 `Save Agent`。
4. 页面显示：`The configuration changed before it could be saved. Refresh it, choose again, and retry.`，详情为 `409 ... invalid_agent_config`。
5. 按提示刷新页面、重新选择、再次保存，结果不变。
6. 再次刷新，清空全部三个分组以形成显式空选择，保存仍返回同一 409。

为排除前端陈旧状态，使用同一浏览器登录态直接读取 live mirror config，GET 为 200，当前 `profile_version=1`、`skills=[]`、`skills_selection_mode=default_discovery`；将同一 canonical profile PATCH 为 `skills=[]`、`skills_selection_mode=explicit_allowlist` 仍返回 409，错误码为 `invalid_agent_config`。这不是一次性的页面竞争，刷新重试也不能恢复。

用户可见证据：

- 保存失败：`/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-desktop-save-error.png`
- 显式空保存失败：`/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-desktop-explicit-empty-result.png`
- 浏览器 console 唯一 error 是失败 PATCH 对应的 `409 Conflict`；正常浏览、登录和读取请求为 2xx。

## User journey evidence

### 1. Coding CLI 与 PA kernel composition

在临时 workspace 以及真实 `e2e` Agent workspace 中分别放置 native、`.claude/skills`、`.codex/skills` 的同名和独有 Skill，并使用实际 `build_cli_kernel` / `build_pa_kernel` 产品 composition 观察公开 Skill 列表与 prompt preview。

观察结果：

- Coding CLI 同名 `priority-probe` 解析到 workspace `.nanocode/skills`；PA 同名解析到 workspace `.nanoassistant/skills`。
- native workspace 的 `playwright` 覆盖全局 `.codex/skills/playwright`；较低优先级重复项不再出现在候选或 prompt preview。
- `.claude` 与 `.codex` 独有 Skill 同时进入 CLI/PA 候选及 prompt preview。
- 当前用户目录不存在 `~/.claude/skills`，该缺失目录被正常跳过；仅有 `.claude` 的临时 workspace 仍可发现有效 Skill。
- 无 `SKILL.md` 的目录不进入候选，空/缺失兼容目录不报错。
- 真实 Coding CLI 通过受控 Anthropic SSE fixture 发起 `skill_view`，返回 `.nanocode/skills/priority-probe/SKILL.md` 及 native 正文。
- 真实 Coding CLI 在单次授权后以 `skill_manage` 创建 `writer-probe-cli`，落在 `.nanocode/skills`，未写入 `.claude/skills` 或 `.codex/skills`。
- 真实 PA kernel 在单次授权后先通过 `skill_view` 返回 `.nanoassistant/skills/priority-probe/SKILL.md`，再以 `skill_manage` 创建 `writer-probe-pa`，返回的 `skill_root` 为 `.nanoassistant/skills`；`.claude` / `.codex` 未出现该 writer 产物。

这里的 fixture 只替代 LLM 决策，Skill resolver、permission、tool execution、workspace 路径和产品 kernel 均为 validated commit 的真实运行路径；没有把 fixture 的结束文本当作真实模型回复成功。

### 2. Desktop Agent detail 与创建页

桌面 viewport 为 `1280x720`。

- 默认态明确显示当前全部可发现 Skill 生效，三个来源分组及计数与 live workspace 一致。
- 点击 Workspace 标题控制从 `6/6` 到 `0/6`；再勾选一个单项后为 `1/6`、checkbox 呈 mixed，并显示 `Complete group`；再次点击组控制恢复 `6/6`。
- 分组后再改单项、先改单项再操作分组均保持真实 none/partial/all 状态，没有额外的大型批量操作区。
- 同名 `priority-probe` / `playwright` 只显示胜出项，不向用户暴露失效重复项。
- 新建 Agent 页面只显示 Global 与 Compatibility，共享全局 Skill 可见；不存在 Workspace 分组，也没有泄漏 `e2e` repo 下的 `ws-claude-only` 等 fixture。
- 实际视觉层级、紧凑标题控制、默认态说明和 prototype 的契约一致，并沿用 current Agent detail 的控件语言。

证据：

- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-desktop-default.png`
- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-desktop-workspace-none.png`
- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-desktop-create-shared-only.png`
- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-prototype-desktop.png`

### 3. 375px mobile

mobile viewport 为 `375x812`。

- Agent detail 在默认、分组全不选及分组 partial 三种状态下均无水平溢出。
- 组标题、计数、三态 checkbox、辅助动作和 Skill pills 能自然换行。
- 实际点击 Workspace 组控制并选回 `ws-claude-only` 后，页面稳定显示 `Workspace 1/6`、mixed 及 `Complete group`。
- mobile 底部导航、保存区和配置内容没有互相遮挡。

证据：

- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-mobile-default.png`
- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-mobile-skills.png`
- `/tmp/nano-feat519-r1-review-artifacts-20260810/output/playwright/feat-519-r1-mobile-partial.png`

### 4. Live SlashPicker、保存后重开与会话延续

在真实 chat 页面输入 `/` 后，默认态 SlashPicker 显示 workspace native `pa-native-only`、native 胜出的 `playwright` / `priority-probe`，以及 `.claude` / `.codex` 独有的 `ws-claude-only`、`ws-claude-second`、`ws-codex-only`。默认态的 candidate projection 与 Agent detail、PA kernel list/prompt preview 一致。

但由于 B1，无法建立任何已保存的 explicit allowlist，也无法建立已保存的显式空状态。因此以下用户旅程在保存步骤直接失败：

- 保存后重开仍保持单项/none/partial/all；
- 同一聊天历史不丢并在下一轮按新 allowlist 生效；
- 显式空后 SlashPicker 不再列 Skill；
- 新增兼容 Skill 不自动扩张一个已保存的 explicit allowlist。

本轮没有声称真实 LLM 回复成功，也没有用默认态 projection 代替显式选择后的 runtime 结果。

## Spec scenario coverage

| Spec scenario | Result | Evidence / reason |
|---|---|---|
| PA 配置页看到并保存兼容 Skill | **FAIL** | 候选可见，保存稳定 409（B1） |
| Coding CLI 会话可使用兼容 Skill | PASS | 实际 CLI `skill_view` + composition list/preview |
| 原有 native 与既有根目录继续工作 | PASS | native、workspace compatibility、global compatibility 同时可见 |
| PA 同名 Skill 使用正确高优先级正文 | PASS | live capability/SlashPicker 与真实 PA `skill_view` 均返回 workspace native |
| Coding CLI 同名 Skill 使用正确高优先级正文 | PASS | 真实 CLI `skill_view` 返回 `.nanocode` native 正文 |
| 新增兼容 Skill 不扩张既有显式选择 | **FAIL** | 无法保存前置 explicit allowlist（B1） |
| 选择兼容 Skill 后继续原聊天 | **FAIL** | 保存步骤失败，无法进入下一轮/history 旅程（B1） |
| 分组批量操作与单项选择可组合 | PASS | 桌面与 mobile 均完成 group -> item / item -> group |
| 分组状态真实反映 none/partial/all | PASS | `0/6`、`1/6 mixed`、`6/6` 均现场观察；保存失败也明确呈现错误 |
| 分组交互在桌面和移动端自然可用 | PASS | 1280x720 与 375x812 真机浏览器操作和截图 |
| 可选兼容目录缺失时正常使用 | PASS | 当前 `~/.claude` 缺失及临时 workspace 缺 native 目录均正常 |
| 空/无效兼容目录不产生 Skill 候选 | PASS | 无 `SKILL.md` 目录被跳过，无报错 |

## Commands and environment

主要命令（敏感字段未写入报告）：

```bash
./scripts/e2e-up.sh --wt "$PWD"
cd src/IM/frontend && npm run dev -- --host 127.0.0.1 --port 64833 --strictPort
python -m http.server 49681 --bind 127.0.0.1 --directory docs/changes/feat-519-workspace-compat-skills
python -m coding_cli.main --provider anthropic --model fixture --llm-base-url http://127.0.0.1:65259 --api-key fixture --text '<skill tool request>'
python <public-product-factory probe>  # build_cli_kernel / build_pa_kernel list, preview, skill_view, skill_manage
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh open http://127.0.0.1:64833
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh resize 375 812
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh console error
```

隔离资源：

- IM: `127.0.0.1:64759`
- Vite: `127.0.0.1:64833`
- prototype: `127.0.0.1:49681`
- controlled Anthropic SSE fixture: `127.0.0.1:65259`
- Gateway node: `wt-review-feat-519-r1-50264`
- Agent workspace: `.gateway-workspace/e2e`
- CLI temp workspaces: `/tmp/nano-feat519-r1-cli-workspace-20260810`, `/tmp/nano-feat519-r1-missing-workspace-20260810`

浏览器记录：

- Viewports: `1280x720`, `375x812`
- Normal-path console: 0 errors, 0 warnings
- Defect-path console: 1 error，失败的 Agent config PATCH 返回 409
- Normal-path network: 登录、Agent/capability/config/chat 读取均为 2xx
- Defect-path network: `/im/v1/agents/e2e/config` PATCH 为 409

截图、fixture transcript、E2E logs 都是本地验收证据，不纳入提交；截图与临时数据库已移至 `/tmp/nano-feat519-r1-review-artifacts-20260810`。

## Reference artifacts reviewed

- `spec.md`
- `design.md`
- `prototype.html`
- `M1-workspace-skills-selection/progress.md`
- `verification-report.md`
- unit delta specs
- current kernel Skills、SDK boundary、Gateway Agent capabilities、IM Agents/Nodes、Coding CLI product-integration specs
- worktree runtime 与测试 runbook

## Document lifecycle check

- `SPEC.md`: 本轮不需要直接修改。
- `docs/specs/*`: unit 的 delta specs 已存在；在实现修复并重新验收前，不应合入 current behavior。
- `AGENTS.md` / `CLAUDE.md`: 本轮无新增开发约束。
- `docs/changes/feat-519-workspace-compat-skills`: 验收报告已补齐；unit 仍应保持 active，不能归档。

## Cleanup confirmation

Playwright、Vite、IM、Gateway、prototype server 与受控 SSE fixture 均已关闭；`64759`、`64833`、`49681`、`65259` 均已确认无监听。临时 `node_modules` symlink 已解除，运行时文件、截图、secret 和 fixture 数据未纳入提交。

---

# Round 2 — 2026-08-10

## Verdict

- **Verdict:** FAIL
- **Highest Required Action:** `fix-implementation`
- **Blocking issues:** 1
- **Major issues:** 0
- **Minor issues:** 0
- **Validated at:** 2026-08-10T02:56:01+08:00
- **Validated commit:** `449960cfdabf4fc265a0f54a8013d11fa16185ad`
- **Executed base:** `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9`
- **Fix delta observed:** `57127841103db3c5510fa907e96a11bce76a42e5..449960cfdabf4fc265a0f54a8013d11fa16185ad`
- **Review round:** 2

R1 的 B1 未关闭。全新隔离 IM、Gateway、Vite、数据库、workspace 和 node identity 下，`default_discovery` 第一次编辑为单项 explicit allowlist 仍不能保存；真正导航刷新后重新操作仍稳定返回 409。显式空保存也失败。错误码从 R1 的 `invalid_agent_config` 变为 `operation_conflict`，但用户仍无法完成同一主路径，因此继续路由 `fix-implementation`。这是一次 fix round 后的复验，不满足 `revise-design` 的轮次闸。

## Round 1 issue revalidation

### B1 — OPEN: Agent detail 仍无法保存显式 Skill 选择

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 直接违反“候选可选择并成功保存”以及“显式选择后下一轮生效”验收标准；新提交尚未让用户走通保存主路径。

独立复现：

1. 通过 runbook 启动全新 E2E 栈，以 `nano` / `nano1234` 登录，打开真实 `e2e` Agent detail。
2. 初始状态为 `Using all currently discoverable skills`，profile v1；Workspace `4/4`、Global `29/29`、Compatibility `13/13`。
3. 清空三个分组，只选 workspace `.claude` 来源的 `r2-claude-only`；草稿如实显示 `1 selected`、Workspace `1/4 mixed`。
4. 点击 `Save Agent`，收到 `409 operation_conflict` 和“refresh capabilities and choose again”提示。
5. 使用浏览器 `page.goto` 真正重新加载详情页，页面重新成为 default discovery；重复步骤 3，保存仍为同一 409。
6. 再次真正刷新，清空全部三个分组形成 `0 selected`，保存仍为同一 409。

live 可观察状态证明操作没有 applied，也没有部分写入：

- 登录态 GET `/im/v1/agents/e2e/config` 为 200，失败后仍是 `skills=[]`、`skills_selection_mode=default_discovery`、`profile_version=1`。
- 隔离 Gateway 的实际 YAML 仍记录 `skills_selection_mode: default_discovery`，没有保存 `r2-claude-only` 或 explicit empty。
- 页面刷新后也恢复 default discovery，而不是显示单项或显式空。
- 三次保存的 network 结果均为 `/im/v1/agents/e2e/config` PATCH 409；保存页面的 console error 对应该失败资源。

证据：

- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-explicit-one-draft.png`
- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-explicit-one-save-error.png`
- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-explicit-empty-draft.png`
- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-explicit-empty-save-error.png`

## User Journeys Exercised

### 1. B1 单项与显式空保存

完整执行 default → 只选 `r2-claude-only` → 保存 → 真刷新 → 重做 → 保存，以及 default → 全部分组清空 → 保存。两条路径均在 config operation 处返回 409，未产生 applied 状态；详情页、live config 与 Gateway YAML 三个可观察面保持 default。

### 2. 原聊天、下一轮 admission 与 SlashPicker

保存前先在真实 Agent chat `08219e634dc7465fb39a02493e9c96f6` 发送 `R2-HISTORY-MARKER`，真实 Gateway/配置上游返回可见回复 `acknowledged`。经历两次单项保存失败和一次显式空保存失败后，重新打开同一 chat，用户消息和模型回复均仍在，证明失败操作没有破坏历史。

但显式空从未成功保存，无法进入“下一轮新 session 不暴露 Skill”的目标状态。失败后输入 `/` 仍显示 `r2-claude-only`、`r2-codex-only`、`r2-native-only`、native 胜出的 `r2-priority`；这与仍为 default 的 live config 一致，只能证明失败操作没有部分应用，不能替代 explicit-empty SlashPicker / session admission 的验收。该主旅程继续 FAIL。

证据：`/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-after-failed-empty-default-slashpicker.png`。

### 3. R1 已通过能力的回归 smoke

- 候选与优先级：详情页同时出现 native、workspace `.claude`、workspace `.codex` 候选；同名 `r2-priority` 只显示 native 胜出项。
- 分组：Workspace 批量清空后再选择单项，显示 `1/4 mixed`，组操作与单项操作仍可组合。
- mobile：375x812 下三组、计数、三态控件和 Skill pills 正常换行，无横向溢出或遮挡。
- 创建页：只呈现共享 Global/Compatibility Skill；没有出现 `r2-*` workspace fixtures，未泄漏现有 Agent workspace。

证据：

- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-mobile-smoke.png`
- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-mobile-partial-smoke.png`
- `/tmp/nano-feat519-r2-review-artifacts-20260810/output/playwright/feat-519-r2-create-smoke.png`

## Round 2 Scenario Coverage

### Requirement: PA 与 Coding CLI 一致发现指定的 Claude/Codex 兼容根目录

| Scenario | Expected source | Verification | Result | Notes |
|---|---|---|---|---|
| PA 配置页提供工作区与用户主目录的兼容 Skill | `spec.md` | 新栈真实详情页候选 + 保存 | **fail** | 候选可见；单项与显式空均保存 409（B1） |
| Coding CLI 在同一项目中提供兼容 Skill 候选 | `spec.md` | 继承 R1 真实 CLI 证据；R2 PA 候选 smoke | pass | 修复 delta 未触及候选发现，smoke 无回归 |
| 原生与既有兼容来源保持可用 | `spec.md` | R2 live native/compatibility/global 候选 | pass | 三类来源仍同时可见 |

### Requirement: 同名 Skill 按统一、可预测的来源优先级解析

| Scenario | Expected source | Verification | Result | Notes |
|---|---|---|---|---|
| PA 中同名 Skill 选择最优先来源 | `spec.md` | R2 detail 与 default SlashPicker | pass | `r2-priority` 只显示 native 胜出正文/描述 |
| Coding CLI 中同名 Skill 选择最优先来源 | `spec.md` | 继承 R1 真实 CLI `skill_view` | pass | R2 fix delta 未触及 CLI resolver |

### Requirement: PA 配置显式选择兼容 Skill 后才在下一轮生效

| Scenario | Expected source | Verification | Result | Notes |
|---|---|---|---|---|
| 新发现的兼容 Skill 不静默扩大已保存 Agent 的能力 | `spec.md` | 尝试建立 explicit allowlist | **fail** | 前置 explicit allowlist 无法保存，不能验证后续新增 Skill |
| 开发者选择兼容 Skill 后继续既有聊天 | `spec.md` | 真实 history + 保存 + SlashPicker/session 路径 | **fail** | history 本身保留，但保存失败，下一轮 explicit admission 不可达 |

### Requirement: PA 配置支持按已显示的 Skill 分组批量选择

| Scenario | Expected source | Verification | Result | Notes |
|---|---|---|---|---|
| 开发者以一个分组为单位调整 Skill 选择 | `spec.md`; `prototype.html` | desktop/mobile group → item smoke | pass | 草稿更新正常，仍可改单项 |
| 分组状态如实反映单项选择 | `spec.md`; `prototype.html` | all → none → partial | pass | `4/4`、`0/4`、`1/4 mixed` 如实呈现 |
| 批量选择自然融入既有配置体验 | `spec.md`; `prototype.html` | 375x812 与 desktop 对照 R1 reference | pass | 无新独立批量区，布局无回归 |

### Requirement: 可选兼容目录缺失时保持正常使用

| Scenario | Expected source | Verification | Result | Notes |
|---|---|---|---|---|
| 工作区不含某个兼容目录 | `spec.md` | 继承 R1 缺失目录真实入口证据 | pass | fix delta 未触及 discovery；R2 候选 smoke 正常 |
| 兼容目录没有有效 Skill | `spec.md` | 继承 R1 空/无效目录真实入口证据 | pass | fix delta 未触及 discovery；无回归迹象 |

## Reference Artifacts Reviewed

| Reference | Must-match contract | R2 actual evidence | Viewport/state | Conclusion |
|---|---|---|---|---|
| `prototype.html` | 分组标题内紧凑三态控制、无笨重独立区 | `feat-519-r2-mobile-smoke.png`, `feat-519-r2-mobile-partial-smoke.png` | 375x812 default/partial | pass, no regression from R1 comparison |
| R1 accepted desktop/create behavior | 候选分组、native duplicate winner、新建页不泄漏 workspace | live R2 detail/create + `feat-519-r2-create-smoke.png` | 375x812 and desktop | pass smoke |

## Browser and Network Record

- Desktop viewport: 1280x720; mobile viewport: 375x812.
- 正常登录、Agent/config/capability/chat 读取、真实消息与模型回复均成功；最终干净页面 console 为 0 errors / 0 warnings。
- defect path 每次保存产生一个 `/im/v1/agents/e2e/config` PATCH 409；页面显示 `operation_conflict`，不存在伪成功。
- 未使用 LLM fixture。`acknowledged` 是隔离 Gateway 按 runbook 默认配置产生的真实可见回复；没有声称它证明 explicit allowlist 生效。

## Commands and Isolation

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$PWD"
source .e2e-ports.env
VITE_IM_PROXY_TARGET="$IM_URL" npm run dev -- --host 127.0.0.1 --port 52895 --strictPort
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh open http://127.0.0.1:52895
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh resize 375 812
/Users/czj/.codex/skills/playwright/scripts/playwright_cli.sh console error
```

- IM: `127.0.0.1:52853`
- Vite: `127.0.0.1:52895`
- Gateway node: `wt-review-feat-519-r2-59814`
- Agent workspace: `.gateway-workspace/e2e`

## Side Findings

None.

## Document Lifecycle Check

- `SPEC.md`: no direct update required by this acceptance round.
- `docs/specs/*`: delta specs remain the active target; do not merge into current behavior while B1 is open.
- `AGENTS.md` / `CLAUDE.md`: no new development constraint surfaced.
- `docs/specs/CONTRIBUTING.md`: no documentation-system change.
- Unit remains active and must not be archived.

## Round 2 Cleanup Confirmation

Playwright、Vite、IM 与 Gateway 均已关闭，`52853` 与 `52895` 已确认无监听；临时 `node_modules` symlink 已解除。截图和临时数据库/receipt 已移至 `/tmp/nano-feat519-r2-review-artifacts-20260810`，所有 runtime/config/secret/database/workspace artifacts 均未纳入提交。

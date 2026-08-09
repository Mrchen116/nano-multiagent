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

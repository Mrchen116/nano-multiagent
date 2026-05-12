# Web IM 新建 Agent 端到端产品收口（基于当前 main 复验）

- Scope ID: M146
- Verdict: fail
- Reviewed By: product-acceptance-reviewer

## Scope

本次仅验收当前 `main` 上的 Web IM Agent 创建/编辑/发现/直聊入口与 prompt 生效语义，并检查关键页面截图中的前端问题。验收依据要求文档、IM SPEC、M104 严格验收 playbook，以及 M205 / M164 / M161 的交付记录；本次明确不使用 `/Users/czj/Repos/nano-multiagent/.worktrees/M146` 作为被测源码树，只将其历史验收报告作为失败基线参考。由于本轮未建立来自当前 `main` 的新鲜真实浏览器运行证据，因此本次结论只能判定为未通过复验。

## Materials Read

- `/Users/czj/Repos/nano-multiagent/docs/需求.md`
- `/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`
- `/Users/czj/Repos/nano-multiagent/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M104-acceptance-playbook.md`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M205-acceptance.md`
- `/Users/czj/Repos/nano-multiagent/PROGRESS/M205-新建-agent-首聊与新会话收口.md`
- `/Users/czj/Repos/nano-multiagent/PROGRESS/M164-移除-New-direct-chat-并统一每-Agent-单聊窗口.md`
- `/Users/czj/Repos/nano-multiagent/PROGRESS/M161-Agent-设置页展示-Workspace-路径并支持配置.md`
- Historical reference only: `/Users/czj/Repos/nano-multiagent/.worktrees/M146/ACCEPTANCE/M146-acceptance.md`

## User Journeys Exercised

- 确认当前 `main` 是否已包含 M205 修复提交基线。
- 审核当前主仓库的 operator runbook 与现有运行态入口，确认本轮应以当前 `main` 为唯一被测源码。
- 审核当前 `main` 中与本范围直接相关的用户路径证据：Agent 创建后首聊闭环、新会话入口、allowlist 收敛、workspace 可见性。
- 审视当前仓库可获得的关键页面截图，检查前端/交互问题是否仍存在可信证据。
- 对照历史 M146 失败基线，判断当前 `main` 上哪些问题已被实现记录宣称修复、哪些仍未被 fresh real-browser evidence 重新证明。

## Passes

- 当前主仓库 `HEAD` 为 `8d6ae76`，且 `508996d41e3e8f8912c750e97f799ffd77496f37` 已是其祖先提交，说明本轮复验对象的 `main` 已包含 M205 所要求的合入基线。
- 当前 `main` 的交付材料明确宣称以下产品修复已经实现并有实现侧/测试侧自证：
  - 新建 Agent 后可进入真实 relay 路径，不再出现 `unknown agent_id` 的实现修复。
  - 聊天页提供 `Start fresh session`，用于在保留每 Agent 单一直聊入口的前提下创建新线程。
  - Agent create/edit 页的 allowlist 默认视图已收敛为面向产品用户的推荐项，并将高级/内部项折叠。
  - Agent 设置页已支持展示和配置 workspace 路径。
- 当前代码库文本检索能在主仓库中找到与上述路径一致的用户可见文案：
  - `Start fresh session`
  - `Open direct chat`
  - `Recommended for product users`
  - `Saved advanced items`
  - `Show advanced/internal options`

## Issues

### Issue 1 — 缺少来自当前 main 的新鲜真实浏览器验收证据
- Severity: blocking
- Type: reliability
- User Impact: 本 milestone 的核心要求是基于真实浏览器 + 真实 IM 前端入口完成 Agent 创建、发现、首聊往返、prompt 编辑与新会话语义验证；如果没有来自当前 `main` 的 fresh evidence，就无法确认这些路径在真实产品中现在真的可用，用户是否仍会遇到旧问题也无法判断。
- Reproduction: 1) 对照本次 scope 要求检查仓库内当前 `main` 的验收材料；2) 发现只有 M205 的实现侧 handoff 与旧的 `.worktrees/M146` 历史失败报告；3) 未找到基于当前 `main` 运行的真实浏览器截图、运行日志、会话证据或本次复验产出的 runtime 目录。
- Expected: 应存在来自当前 `main` 的 fresh real-browser evidence，至少覆盖 `/settings/agents`、`/settings/agents/new`、`/chat`、首条真实消息往返、prompt 编辑后旧/新会话语义，以及关键页面截图。
- Actual: 当前仓库只有实现侧自证和历史失败报告；未发现本次基于当前 `main` 的真实浏览器运行证据，因此无法完成严格产品验收要求的关键判断。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M205-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/PROGRESS/M205-新建-agent-首聊与新会话收口.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M146/ACCEPTANCE/M146-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/` 下无当前 `main` 对应的 M146 fresh runtime/browser 证据文件
- Basis: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M104-acceptance-playbook.md` 明确要求四个硬性场景只能由真实用户路径判定，测试、历史文档、进度记录不可替代最终真机复验；本次 caller 也明确要求“Only accept fresh real-browser evidence from current main.”

### Issue 2 — 首聊闭环与 prompt 新会话语义仍未被当前 main 真实路径重新证明
- Severity: blocking
- Type: flow
- User Impact: 即使实现记录宣称已修复，如果没有在当前 `main` 的真实浏览器环境中重新证明，用户仍可能在实际使用时遇到“Agent 创建成功但首聊不回复”或“保存 prompt 后无可发现的新会话入口”的历史阻塞问题。
- Reproduction: 1) 对照历史 M146 失败项；2) 再对照当前 `main` 中 M205/M164 的实现记录；3) 发现修复宣称存在，但缺少当前 `main` 的 fresh browser run 来证实用户路径现已闭环。
- Expected: 基于当前 `main` 的真实产品路径应重新证明两件事：一是新建 Agent 至少完成一条真实 IM ↔ Gateway ↔ Kernel ↔ IM 往返；二是修改 prompt 后旧会话不漂移、新会话体现新 prompt，而且“新会话”入口能被正常用户发现。
- Actual: 目前只能确认实现记录中已加入 `Start fresh session` 等文案和测试，但并未获得真实浏览器路径的重新证据，因此本轮无法把历史 blocking 问题视为已关闭。
- Evidence:
  - 历史失败基线：`/Users/czj/Repos/nano-multiagent/.worktrees/M146/ACCEPTANCE/M146-acceptance.md`
  - 当前实现自证：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M205-acceptance.md`
  - 当前实现进度：`/Users/czj/Repos/nano-multiagent/PROGRESS/M205-新建-agent-首聊与新会话收口.md`
- Basis: `/Users/czj/Repos/nano-multiagent/docs/需求.md` 要求用户可与任意配置级 Agent 直接对话；`/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md` 要求配置变更仅对新会话生效且 Web IM 可完成完整消息往返；本 milestone journeys 也明确要求真实首聊和真实新会话语义验证。

### Issue 3 — 关键页面截图证据仍不足以完成本次前端问题复核
- Severity: major
- Type: ux
- User Impact: caller 明确要求“Must inspect key page screenshots and explicitly call out frontend issues in the report”。如果缺少来自当前 `main` 的创建页、详情页、聊天页等关键截图，就无法对前端问题给出可信的现态判断，也无法确认历史上暴露给普通用户的大量内部项是否已经真正收敛。
- Reproduction: 1) 检查当前主仓库 `ACCEPTANCE/` 可用截图；2) 发现已有截图主要来自其他 milestone，如 M144 节点/账号页和 M170 群聊页；3) 未找到本轮要求的当前 `main` Agent 创建页、详情页、聊天页新鲜截图证据。
- Expected: 应提供当前 `main` 的 `/settings/agents`、`/settings/agents/new`、Agent detail、`/chat` 等关键页面截图，以便明确记录前端/交互问题是否仍存在。
- Actual: 当前仓库现成截图不足以支撑本次 M146 前端问题复核；只能根据实现记录知道文案可能已变化，但不能把它当作真实页面体验结论。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M144-settings-account.png`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M144-settings-nodes.png`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M144-settings-policies.png`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-20260316-home.png`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-20260316-alpha-settings.png`
  - 上述截图均不属于本次 M146 当前 `main` Agent create/detail/chat fresh acceptance evidence
- Basis: caller 额外要求必须检查关键页面截图并明确指出前端问题；产品验收标准要求以真实页面而非仅凭实现记录做判断。

## Retest Focus

- 基于 `/Users/czj/Repos/nano-multiagent` 当前 `main` 启动或复用一套可信的真实 IM + Gateway + Kernel + 浏览器运行态，并保留 fresh runtime 目录与浏览器证据。
- 在真实 `/settings/agents` 与 `/settings/agents/new` 创建一个新 Agent，保存创建页、详情页截图，并确认 allowlist 默认视图是否已从产品角度收敛。
- 在真实 `/chat` 中发现该 Agent，完成至少一条真实往返，明确确认不再出现历史 `unknown agent_id` 类问题。
- 修改该 Agent prompt，先验证旧会话不漂移，再通过真实可发现入口触发 `Start fresh session` 或等价新会话路径，证明新会话体现新 prompt。
- 补齐当前 `main` 的关键页面截图，并重新审视创建页、详情页、聊天页中是否仍存在内部术语暴露、信息层级混乱、入口不清晰等前端问题。

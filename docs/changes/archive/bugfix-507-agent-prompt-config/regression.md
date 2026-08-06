# bugfix-507 — 回归验证

> 对齐: incident.md
>
> Validation snapshot: `5bba0493f34bd5acc2343787f04a8e092d1309b4 → bdb7243484b776295fb32f69eccdafa1f7f710cd`
>
> Review round: 1

## Verdict

- **Verdict:** pass
- **Highest Required Action:** pass
- **Issues:** blocking 0 / major 0 / minor 0
- **验收目标:** worktree 隔离 IM、Gateway、Vite；测试用户 `nano`；隔离 Agent `e2e`、`e2e-peer`；仓库外一次性 legacy Gateway fixture。

Owner 能在配置页看到、编辑并清空 Custom Instructions；draft 和 saved preview 都如实包含稳定专属说明与已选能力，并明确排除 group chat / memory runtime segments。保存后，既有聊天的下一轮采用新说明且保留历史；另一 Agent 不受影响。旧 YAML 首次注册空 IM 后，legacy 说明在 Custom Instructions 中可见，preview 仅注入一次。

## 复现验证

修前问题是：Custom Instructions 为空或未包含 legacy 内容时，实际 Agent 仍可能带不可见的 profile 人设，preview 也无法审阅它。

修后通过真实产品入口验证：

1. 在默认隔离栈登录 Web IM，打开 `Agents → e2e → Config`；页面渲染 `Preview stable system prompt`，确认 Vite 来自 unit 源码而非 IM 的旧 bundle。
2. 在 `e2e` 已有聊天中先发送“Reply exactly with the single token BEFORE507.”，得到 `BEFORE507`。
3. 回到配置页，将 Custom Instructions 草稿改为“Begin every reply with ALPHA507...”，未保存即展开 preview：草稿已出现在 `# Custom Agent Instructions`，已选 features / tools / skills 仍在稳定预览中；页面同时显示 “Group chat and memory runtime segments are excluded from this preview.”。
4. 保存后回到同一聊天询问上一轮 token；页面保留此前消息与 `Agent 配置已更新` 边界，新回复为 `ALPHA507. You asked for the token "BEFORE507".`。
5. 打开 `e2e-peer` 的独立聊天询问是否有固定 prefix，回复明确为无 prefix；证明 `e2e` 的保存内容未影响另一 Agent。
6. 清空 `e2e-peer` Custom Instructions：草稿 preview 不再出现旧 peer 角色或 `# Custom Agent Instructions`；保存后新建聊天询问是否仍被明确要求承担旧 peer 角色，回复 `No.`。
7. 在最新 unit head 以仓库外旧 YAML fixture 无脑重启空 IM + Gateway + Vite。首次注册后的 `e2e` 配置页直接显示 `Custom Instructions = LEGACY507 visible role`；stable preview 中 `# Custom Agent Instructions` 只出现一次该文本，并保留 runtime exclusion 提示。

关键证据：

- unit marker 与初始可见配置：`.playwright-cli/page-2026-08-06T08-35-52-302Z.yml`
- draft preview、能力配置与 runtime exclusion：`.playwright-cli/page-2026-08-06T08-44-24-766Z.yml`、`.playwright-cli/page-2026-08-06T08-44-48-354Z.png`
- 既有历史 + 配置边界 + 新回复采用：`.playwright-cli/page-2026-08-06T08-46-20-764Z.yml`、`.playwright-cli/page-2026-08-06T08-46-40-195Z.png`
- 另一 Agent 不受影响：`.playwright-cli/page-2026-08-06T08-48-08-383Z.yml`
- 空值 preview 与新聊天无旧角色：`.playwright-cli/page-2026-08-06T08-49-34-735Z.yml`、`.playwright-cli/page-2026-08-06T08-49-55-093Z.png`、`.playwright-cli/page-2026-08-06T08-50-12-278Z.yml`
- legacy YAML 首次注册到空 IM：`.playwright-cli/page-2026-08-06T08-53-39-624Z.yml`、`.playwright-cli/page-2026-08-06T08-53-52-013Z.yml`、`.playwright-cli/page-2026-08-06T08-54-12-342Z.png`

## User Journeys Exercised

1. **Owner 审阅并保存专属说明**：配置页 → 编辑草稿 → stable preview → 保存 → 再次确认保存值和 preview。覆盖 preview 的两条 Scenario。
2. **既有聊天惰性采用且 Agent 隔离**：旧回复 → 修改 `e2e` → 同一聊天新回复 → `e2e-peer` 独立回复。覆盖后续新回复、历史连续和仅影响目标 Agent。
3. **空值无隐藏角色**：清空 `e2e-peer` → preview → 保存 → 新聊天确认旧角色消失。覆盖空值与唯一公开入口。
4. **升级迁移**：旧 YAML + 空 IM → first registration → 配置页 → preview。覆盖已有有效说明可见、可编辑、不丢失、不重复。

## Reference Artifacts Reviewed

无。本 unit 没有原型、reference screenshot 或 must-match 视觉契约；产品真值来自 `incident.md` 的 Requirement / Scenario 与 `design.md` 的 Reviewer Runbook。

## 验收标准覆盖

### Requirement: Agent 专属人设只有可见的 Custom Instructions 入口

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建或编辑 Agent 没有隐藏的第二份人设 | `incident.md` | 清空 `e2e-peer`，核对 draft preview 后保存，并在全新聊天确认旧角色消失 | `.playwright-cli/page-2026-08-06T08-49-34-735Z.yml`；`.playwright-cli/page-2026-08-06T08-50-12-278Z.yml` | pass | 空值 preview 无 Custom Agent Instructions；新聊天回答未被赋予旧角色 |
| 保存专属说明只影响该 Agent 的后续新回复 | `incident.md` | `e2e` 保存 ALPHA507 后继续既有聊天，并与 `e2e-peer` 对照 | `.playwright-cli/page-2026-08-06T08-46-20-764Z.yml`；`.playwright-cli/page-2026-08-06T08-48-08-383Z.yml` | pass | `e2e` 新回复采用 ALPHA507 且引用 BEFORE507；peer 明确无 prefix |

### Requirement: 预览如实呈现稳定的 Agent 配置

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 预览包含已保存或待保存的专属说明 | `incident.md`、`design.md` 决策 3 | 在保存前后分别展开 preview，核对自定义文本及已选 features / tools / skills | `.playwright-cli/page-2026-08-06T08-44-24-766Z.yml`；`.playwright-cli/page-2026-08-06T08-44-55-878Z.yml` | pass | draft 与 saved preview 均含 ALPHA507；保存后 profile version 从 v1 到 v2 |
| 预览明确边界而不冒充完整运行时上下文 | `incident.md`、`design.md` 决策 3 | 核对 stable 标题、完整稳定配置和 runtime exclusion 文案 | `.playwright-cli/page-2026-08-06T08-44-24-766Z.yml`；`.playwright-cli/page-2026-08-06T08-53-52-013Z.yml` | pass | 明确排除 group chat 和 memory runtime segments，其余稳定用户配置可见 |

### Requirement: 既有隐藏说明变为可审阅的公开配置

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 升级后保留已有 Agent 的有效专属说明 | `incident.md`、`design.md` 决策 2 | 以旧 YAML 启动最新 head 的空 IM/Gateway，首次注册后从配置页和 preview 检查 | `.playwright-cli/page-2026-08-06T08-53-39-624Z.yml`；`.playwright-cli/page-2026-08-06T08-53-52-013Z.yml` | pass | `LEGACY507 visible role` 可见可编辑，preview 中仅注入一次 |

## 回归测试

- 配置页保存、profile version 更新、preview 展开均正常。
- 已有聊天历史在配置更新后继续可见，并展示清晰的配置更新边界。
- 未编辑 Agent 的运行说明不受另一 Agent 保存影响。
- 清空说明后，新聊天不再体现旧角色。
- 隔离栈两次均使用高位端口；最终 IM、Gateway、Vite、Playwright browser 与 tmux session 均已停止，端口释放。

## 自动化测试增量

reviewer 不以自动化测试代替用户旅程。本轮只记录上游证据：milestone progress 报告 PA / Kernel、IM、frontend 与跨进程测试已通过；orchestrator 在最终 migration compatibility delta 后报告 IM 423 tests passed。上述结果未替代本报告的浏览器结论。

## Issues

无。

## Side Findings

- 隔离浏览器无法下载 `fonts.gstatic.com` 的 IBM Plex Sans 字体，console 记录一次 `ERR_CONNECTION_CLOSED`；页面使用 fallback 正常渲染，不影响本 unit 旅程，属于环境网络 minor 观察，不立 issue。
- 首次接管时 worktree 缺 frontend dependency link，IM fallback bundle 指纹仍是旧 `Preview full system prompt`；orchestrator 补齐临时、未入 git 的 dependency symlink 后，本轮所有有效浏览器证据均来自 unit Vite。旧 bundle 证据已作废，未参与结论。

## Clarifications

- reviewer 请求 legacy YAML 的无写入前置；orchestrator 提供仓库外、一次性的 `/tmp/nano-bugfix-507-legacy-gateway.yaml`，只连接本轮空 IM。reviewer 未创建或修改 fixture。
- 验收中 unit head 从 `8ae5fdd7` 推进到 `bdb724348`；orchestrator 说明 delta 仅涉及旧 SQLite migration compatibility、无 UI / preview / request shape 变化。legacy migration 旅程已在最终 head 上重新无脑启动并验证；此前用户面旅程证据继续适用。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；公开 profile 字段收敛不改变跨包依赖拓扑。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新；unit 已提供 IM / Gateway delta-spec，待 orchestrator 收尾归并 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：无需更新。

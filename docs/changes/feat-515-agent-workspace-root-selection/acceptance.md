# feat-515 — 验收报告

> 对齐: `spec.md` 的验收标准
>
> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 → 4a11df1e5dcbd76c8eaedf6ae4ca2d1c4e1b045e`
>
> Review round: 1（full revalidation，2026-08-07）

## Highest Required Action

`fix-implementation`

## Verdict

`fail`

七个首文档 Scenario 的直接旅程均得到预期结果；但相邻安全旅程发现一个 blocking 问题：用户可以在新建页再次提交已经存在的 Agent ID，并用不同自定义路径成功“创建”，详情页随后把同一个 Agent 的固定 workspace root 从原值改成新值。这直接破坏“创建后 workspace root 固定”的核心产品约束，当前版本不可交付。

## User Journeys Exercised

1. **默认目录创建与固定展示（desktop 1440×1000）**
   - 在隔离节点 `wt-review-feat-515-r1-38924` 创建 `review_default_515`，保持默认选中的“Use default directory”。
   - 页面跳转到详情，Workspace Root 显示为 `/Users/czj/Repos/nano-multiagent/.worktrees/review-feat-515-r1/.gateway-workspace/review_default_515`。
   - Workspace & Runtime 卡明确标记 `Read-only. Managed by the owning node.`，root 输入框 disabled，页面没有修改或迁移入口。
2. **自定义新目录与父目录错误**
   - 以不存在但父目录可用的 `/Users/czj/Repos/nano-multiagent/.worktrees/review-feat-515-r1/.review-custom-new-515` 创建 `review_custom_515`，创建成功，详情显示完全相同的 canonical root。
   - 以父目录不存在的 `.../.missing-parent-515/agent` 创建 `review_bad_parent_515`，页面保留草稿并在 Workspace Root 旁显示 `The parent directory does not exist on e2e-node-2.`，未跳转、未创建 Agent。
3. **已有目录确认与同节点占用**
   - 预置 `.review-existing-515/user-file.txt`，首次提交 `review_existing_515` 时页面出现醒目的 existing-directory 警示和显式确认框；此时 Agent profile 为 404，目录内没有 `.nanoassistant`。
   - 勾选确认后再次提交才创建成功；`user-file.txt` 保留，随后出现 `.nanoassistant/` 与 starter 文件。
   - 在同一节点再用 `.review-existing-515` 创建 `review_conflict_515`，页面明确显示 `This directory already belongs to Agent review_existing_515. Choose another path.`，没有确认框、没有创建。
4. **双节点同字符串路径与响应式体验**
   - 在同一隔离 IM 下启动主节点和 `e2e-node-2`；后者使用独立 config、workspace、runtime directory 和 node identity。
   - 主节点已经占用 `.review-existing-515` 后，在 `e2e-node-2` 选择同字符串路径，页面只要求“已有目录”确认，没有报“归属另一 Agent”；确认后 `review_crossnode_515` 创建成功，详情显示 `e2e-node-2` 与相同 root 字符串。
   - 真实浏览器在 390×844 下检查默认/custom 两个选项纵向堆叠，Workspace 卡仍位于 Identity 与 Behavior 之间，custom path 说明明确指向目标节点，未出现横向溢出。
5. **固定 root 的相邻安全 poke（blocking）**
   - 已有 `review_default_515` 的 root 为 `.gateway-workspace/review_default_515`。
   - 再次打开新建页，填写同一 Agent ID `review_default_515`，选择同节点的新自定义 root `.review-duplicate-id-515` 并提交。
   - 页面没有拒绝，而是跳转到 `/settings/agents/review_default_515`；详情显示名称已变为 `Duplicate Review Default`，Workspace Root 已变为 `.review-duplicate-id-515`。

上述旅程均通过真实 Vite 页面完成，产品页 console 为 0 error / 0 warning。截图在 reviewer 浏览器会话中于关键状态即时采集；遵守 reviewer 零写入约束，未把截图另写进仓库。

## Reference Artifacts Reviewed

预期来源为 `design.md` 的“前端原型 / 原型对齐契约”与 `prototype.html`。真实产品截图已在 browser session 中采集；浏览器安全策略不允许直接打开本地 `file://.../prototype.html`，因此以下结论针对 design 中明确列出的四条 `must-match` 投影，而不是声明完成了逐像素 prototype render 对照。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` / card order | Workspace 位于 Identity 与 Behavior 之间 | reviewer browser screenshot + DOM snapshot，三张卡顺序清晰 | 1440×1000，新建页 | match |
| `prototype.html` / mode chooser | 默认目录、自定义路径二选一且默认选中 | desktop 首屏默认 radio checked；390×844 下两个选项纵向堆叠并可切换 | desktop default；390×844 custom | match |
| `prototype.html` / custom path | 文案说明目标节点、父目录要求，错误定位在字段附近 | custom helper text 指向选中节点；missing parent 原因显示于 root 字段下 | desktop custom/error；390×844 custom | match |
| `prototype.html` / existing directory | 醒目提示、确认框、再次提交 | 首次提交出现黄色 alert 与未选确认框；确认后再次提交成功 | desktop existing directory | match |

## Issues

### 1. 已存在 Agent ID 可通过“新建”把固定 workspace root 改到另一目录

- **Severity**: blocking
- **Regression Relation**: direct
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: `spec.md` 明确要求创建后 root 是长期固定归属，且非目标包含“编辑、迁移或重新分配已有 Agent 的 workspace root”。当前新建入口可用同一 ID 绕过该约束，并真实改变详情页显示的 root。
- **Expected**: 已存在 Agent ID 的创建请求被拒绝；原 Agent 名称和 workspace root 均保持不变。
- **Actual**: 提交成功并进入同一 Agent 详情；名称和 root 都变成第二次创建提交的值。
- **Reproduction**:
  1. 用默认目录创建 `review_default_515`，详情确认 root 为 `.gateway-workspace/review_default_515`。
  2. 返回 `/settings/agents/new`，继续填写 `review_default_515`，选择同节点自定义新路径 `.review-duplicate-id-515`。
  3. 提交后观察页面成功跳转；详情显示同一个 Agent ID 的 root 已变为 `.review-duplicate-id-515`。
- **Evidence**: 真实浏览器 DOM snapshot 同时显示 URL `/settings/agents/review_default_515`、disabled Agent ID `review_default_515`、标题 `Duplicate Review Default`、disabled Workspace Root `.review-duplicate-id-515`；reviewer session 已采集 1440×1000 截图。

## Acceptance Criteria Coverage

### Requirement: 创建 Agent 时可选择默认目录或自定义路径 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 使用默认目录创建 Agent | `spec.md`；`design.md` mode chooser must-match | Journey 1，真实 desktop 创建页与详情页 | 默认 radio checked；创建后详情显示节点分配 root | pass | root 位于隔离 Gateway workspace base |
| 使用自定义路径创建新的 workspace | `spec.md` | Journey 2，真实浏览器提交不存在但 parent 存在的绝对路径 | 跳转详情，disabled Workspace Root 与输入 canonical path 一致 | pass | 节点为 `e2e-node-2` |
| 自定义路径的父目录不可用 | `spec.md`；`design.md` custom path must-match | Journey 2，提交缺失 parent | 页面保留草稿并显示 `The parent directory does not exist on e2e-node-2.` | pass | 未创建 Agent |

### Requirement: 采用已有目录前须提醒用户 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自定义路径是已有目录 | `spec.md`；`prototype.html` existing-directory state | Journey 3，已有目录首次提交、确认前取证、勾选后重试 | 黄色 existing-directory alert；确认前 profile 404 且无 `.nanoassistant`；确认后创建且 sentinel 保留 | pass | 真实浏览器 + 隔离目录可见结果 |

### Requirement: 同节点 workspace root 只可归属一个 Agent — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一节点的路径已被另一个 Agent 使用 | `spec.md` | Journey 3，在主节点重复提交已归属 root | 字段旁明确显示归属 `review_existing_515`；创建页未跳转 | pass | 不出现已有目录确认框 |
| 不同节点的同字符串路径 | `spec.md`；`design.md` 双节点 Runbook | Journey 4，两个在线节点、相同绝对字符串 | 第二节点只提示已有目录，确认后成功；详情显示 `e2e-node-2` 与相同 root | pass | node-scoped ownership 成立 |

### Requirement: 创建后 workspace root 固定 — 组内结论: fail（Scenario 字面路径通过，但相邻创建入口可绕过）

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看已有 Agent 的设置 | `spec.md` | Journey 1，打开已创建 Agent Config | Workspace & Runtime 标为 Read-only；root disabled；无修改/迁移操作 | pass | blocking issue #1 证明用户仍可从新建入口间接重新分配 root，因此 Requirement 整体 fail |

## Side Findings

- **Runbook runtime 隔离缺口（minor）**：按 `design.md` 原样把第二配置放在 `$WT_ROOT/.gateway-node-2.yaml` 启动时，进程立即报 `ERROR node_id mismatch`；把同一临时 config 放入独立 `.gateway-node-2-runtime/` 后，第二节点正常 online 并完成旅程。原命令没有隔离 config-adjacent runtime state。该问题不改变产品旅程结论，也未触碰生产/default config。
- **Reference render limitation**：in-app Browser 的 URL 安全策略拒绝 `file://.../prototype.html`；已对照 design 明列的四项 must-match 契约并采集真实产品截图，但没有宣称完成 prototype 的直接逐像素渲染对照。
- Verifier 提到的“IM dereference remote root”未在本轮同机双节点用户旅程中形成可观察症状；reviewer 未读实现、未作根因判断，也未把该内部线索当作产品证据。

## Environment and Cleanup

- 全程使用 `/Users/czj/Repos/nano-multiagent/.worktrees/review-feat-515-r1` 的隔离 runtime。
- IM: `http://127.0.0.1:52922`；Vite: `http://127.0.0.1:53105`；未使用生产 `:8011` 或默认 `:5173`。
- 主节点: `wt-review-feat-515-r1-38924`；第二节点: `e2e-node-2`。两者均使用专用 config、workspace 和 node identity。
- 未运行 `python -m personal_assistant.main stop`，避免任何 config 解析歧义误停用户日常 Gateway；仅使用 worktree `e2e-down.sh` 和 reviewer 自己持有的前台进程句柄清理。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变跨包依赖与部署拓扑。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：需要更新；unit delta-spec 已存在，待实现修复并最终校正后由 orchestrator 归并 canonical。当前 canonical IM spec 已要求 duplicate `agent_id` 返回 409，本轮产品行为与之不一致。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本轮未创建 out-of-unit GitHub issue。

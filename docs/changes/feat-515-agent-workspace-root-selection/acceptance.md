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

---

# Round 3 — 2026-08-08

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 → 22be44246870caf59920e593976667c5a7fd7c9b`
>
> Revalidation mode: full

## Highest Required Action

`pass`

## Verdict

`pass`

七个首文档 Scenario 均在隔离的真实 IM + 双 Gateway + Vite + 浏览器旅程中通过。Round 1 的
blocking 问题已关闭：使用已有 Agent ID 从新建页提交另一 workspace root 时，页面留在原表单并
明确显示 `409 (agent_id already exists)`；原 Agent 仍以原名称列在导航中，未发生成功跳转或重新
分配。自定义路径失败会在
Workspace 字段旁显示节点给出的原因并保留整份草稿；Windows 风格目标路径也到达 Gateway 后才被
节点拒绝，没有被前端按 POSIX 语法提前拦截。

同一绝对路径字符串在主节点和 `e2e-node-2` 上分别归属不同 Agent：第二节点仅要求确认“已有目录”，
确认后成功创建。会话蒸馏选择同样显示了节点边界：先选择主节点会话后，第二 Gateway 的会话变为
disabled，并标记 `Different Gateway node`，用户不会误把跨节点 transcript 合并进一次蒸馏。

## User Journeys Exercised

1. **默认创建、只读详情与重复 ID 固定性（desktop 1440×1000）**
   - 在 `wt-review-feat-515-r3-10886` 使用默认选中的 `Use default directory` 创建
     `r3_default_515`；详情显示节点分配的
     `.gateway-workspace/r3_default_515`，Workspace Root disabled，且没有编辑或迁移入口。
   - 回到新建页，以同一 Agent ID、不同名称和 `.r3-duplicate-root` 再次提交；页面以
     `409 (agent_id already exists)` 拒绝并完整保留 ID、名称、节点、custom 模式和路径。
2. **自定义新路径、父目录错误与远端路径语义**
   - 使用父目录存在但 target 不存在的 `.r3-custom-new-515` 创建 `r3_custom_515`，成功详情显示
     exact canonical root。
   - 使用 `.missing-parent-r3/agent` 提交后，Workspace 字段显示
     `The parent directory does not exist on wt-review-feat-515-r3-10886.`；Description、Custom
     Instructions、ID、名称、节点和路径全部保留，未创建 Agent。
   - 将同一草稿改为 `C:\Gateway Data\windows_ui_round3` 再提交，页面显示节点返回的
     `The parent directory is not usable on wt-review-feat-515-r3-10886.`；证明值已到 Gateway，
     而非被前端按本机 POSIX 路径语法拒绝。
3. **已有目录的显式确认重试**
   - 预置 `.r3-existing-515/user-file.txt`。第一次提交 `r3_existing_515` 后出现黄色
     `This is an existing directory` 警示和显式确认框；此时未跳转，目录内无 `.nanoassistant`。
   - 勾选确认后用同一草稿重试，创建成功；详情 root 固定为 `.r3-existing-515`，sentinel 保留，
     `.nanoassistant` 只在确认后出现。
4. **同节点占用与双节点同字符串路径**
   - 在主节点为 `r3_conflict_515` 再次提交 `.r3-existing-515`，页面明确显示
     `This directory already belongs to Agent r3_existing_515. Choose another path.`，不显示确认框。
   - 在独立 runtime/config/node identity 的 `e2e-node-2` 上，以相同字符串路径创建
     `r3_crossnode_515`；第一次只提示已有目录，确认后成功，详情显示 owning node
     `e2e-node-2` 和相同 root 字符串。
5. **原型与响应式对照、跨节点蒸馏保护**
   - 直接通过 worktree-local HTTP 打开 `prototype.html`，逐状态对照真实产品 desktop default、
     custom、existing warning，以及 390×844 default/custom。
   - 产品在 390×844 下为单栏，Workspace 位于 Identity 与 Behavior 之间；两种模式纵向堆叠，
     custom path helper 和长节点名不横向溢出。
   - 从主节点 `r3_default_515` 和第二节点 `r3_distill_node2` 各形成真实 transcript。进入
     `Generate skill`，选择主节点会话后，第二节点会话 disabled 且显示
     `Different Gateway node`。

## Reference Artifacts Reviewed

期望来源为 `design.md` 的“前端原型 / 原型对齐契约”和直接渲染的 `prototype.html`。本轮通过
worktree-local HTTP 真正打开原型，并与同一 browser session 中的产品截图逐状态对照。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` / card order | Workspace 位于 Identity 与 Behavior 之间 | 真实 Vite 创建页 DOM + browser screenshot | 1440×1000 default/custom；390×844 default/custom | match |
| `prototype.html` / mode chooser | default/custom 二选一且默认选中 | 首屏 default checked；切换 custom 后路径字段出现；390px 两项纵向堆叠 | desktop + 390×844 | match |
| `prototype.html` / custom path | 目标节点、父目录要求与字段错误 | helper 明确选中节点；missing/unusable parent 原因位于 Workspace 字段旁 | desktop custom/error；390×844 custom | match |
| `prototype.html` / existing directory | 醒目提示、确认框和再次提交 | 黄色 alert、未选确认框、确认前零初始化；勾选后同草稿重试成功 | desktop existing directory | match |

## Acceptance Criteria Coverage

### Requirement: 创建 Agent 时可选择默认目录或自定义路径 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 使用默认目录创建 Agent | `spec.md`；`prototype.html` mode chooser | Journey 1，真实 desktop 创建与详情 | default radio 首屏 checked；详情显示节点分配 root | pass | `workspace_root` fixed/read-only |
| 使用自定义路径创建新的 workspace | `spec.md` | Journey 2，提交不存在但 parent 可用的绝对路径 | 创建成功；详情 disabled root 与输入 canonical path 一致 | pass | 主节点真文件系统 |
| 自定义路径的父目录不可用 | `spec.md`；prototype custom error | Journey 2，missing parent + Windows-style target | 字段旁显示目标节点原因；整份草稿保留；未创建 Agent | pass | Windows 风格值由 Gateway 裁决 |

### Requirement: 采用已有目录前须提醒用户 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自定义路径是已有目录 | `spec.md`；prototype existing state | Journey 3，首次提交、确认前取证、确认重试 | 黄色 alert + checkbox；确认前无 `.nanoassistant`；确认后成功且 sentinel 保留 | pass | 同一草稿二次提交 |

### Requirement: 同节点 workspace root 只可归属一个 Agent — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一节点的路径已被另一个 Agent 使用 | `spec.md` | Journey 4，在主节点重复提交已归属 root | 字段显示归属 `r3_existing_515`；无确认框、无新 Agent | pass | node-local ownership 生效 |
| 不同节点的同字符串路径 | `spec.md`；design 双节点 Runbook | Journey 4，两个在线 Gateway、相同 absolute string | 第二节点只提示已有目录；确认后成功，详情为 `e2e-node-2` | pass | 同一 IM、独立 config/runtime/node identity |

### Requirement: 创建后 workspace root 固定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看已有 Agent 的设置 | `spec.md`；Round 1 blocking issue | Journey 1，详情只读检查 + duplicate-ID poke | 初始 root disabled、无修改/迁移入口；重复 ID 409 且无成功跳转 | pass | Round 1 blocking issue closed |

## Additional Product Probes

| Probe | Expected | Observed | Result |
|---|---|---|---|
| Duplicate Agent ID with divergent custom root | Reject before any re-assignment | 409 on create form; form and original listed Agent preserved; no success navigation | pass |
| Validation error preserves draft | Path error without losing unrelated fields | ID/name/description/node/path/instructions all remained | pass |
| Windows-style target path | Gateway decides target semantics | Node-specific parent-unusable message returned; no frontend syntax rejection | pass |
| Distill conversations from different Gateway nodes | Prevent unsafe cross-node selection with user-facing explanation | Other-node checkboxes disabled and labeled `Different Gateway node` | pass |

## Issues

None.

## Side Findings

- **Second Gateway runtime location（minor, non-blocking）**：沿用 Round 1 已观察到的 config-root
  mismatch 风险，本轮直接把临时 config 放在 worktree-local
  `.gateway-node-2-runtime/gateway.yaml`，与主 Gateway runtime 分离；第二节点正常 auto-bind、online
  并完成全部旅程。该 workaround 只影响 reviewer Runbook 的临时 runtime 布置，不影响产品结论；
  建议后续校正文档示例路径。

## Environment and Cleanup

- 隔离 IM: `http://127.0.0.1:51245`；Vite: `http://127.0.0.1:51266`；prototype HTTP:
  `http://127.0.0.1:51267`。未触碰生产 `:8011`、默认 Gateway config 或日常 workspace。
- 主节点: `wt-review-feat-515-r3-10886`；第二节点: `e2e-node-2`。第二节点使用专用 config、
  runtime directory、workspace base 和 node identity。
- 完成后先按 PID 停止 reviewer 自己启动的第二 Gateway、Vite、prototype server，再执行 worktree
  `e2e-down.sh`；三个监听端口均确认释放。所有本轮 runtime 目录、日志、PID、SQLite、测试 workspace
  和临时 `node_modules` symlink 已移入废纸篓，`git status` 仅剩本报告修改。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变依赖方向或部署拓扑。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：需要在 unit 收尾时归并；delta-spec 已覆盖默认/custom、
  confirmation、node-scoped ownership、opaque root/provenance 和 fixed-root 行为，待 orchestrator 按最终
  实现校正后写回 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本轮未创建 out-of-unit GitHub issue。

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

# Round 4 — 2026-08-08

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 → 101f72f583729c5b90a6c824162b02135d0061c8`
>
> Revalidation mode: delta（fix delta `c5ec433576d6a24854dca243471dbda28c2cc6c2..101f72f583729c5b90a6c824162b02135d0061c8`）+ core journey regression

## Highest Required Action

`pass`

## Verdict

`pass`

七个首文档 Scenario 均通过。Round 3 已通过的默认、自定义、错误、确认、唯一性和固定 root
主路径在隔离双 Gateway 真栈中保持可用；本轮 delta 重点也得到真实用户面证据：一个含 `..` 的
有效非 canonical custom value 在创建表单中没有被归类成 workspace-local skill，提交后由目标
Gateway 接受并返回 canonical root。

已有目录确认流程还完成了一次用户可见的 transient reconnect 重试：勾选确认后主 Gateway 临时
离线，提交明确显示 `503 (target_node_id is not connected)`，整份草稿、确认状态和 existing-directory
提示均保留；同一隔离 Gateway 重连后再次点击创建即成功，sentinel 文件保留且初始化内容只在成功后
出现。

## User Journeys Exercised

1. **默认创建与固定详情（desktop 1440×1000）**
   - 在主节点 `wt-review-feat-515-r4-36191` 使用默认选中的 `Use default directory` 创建
     `r4_default_515`。
   - 详情显示节点分配的 `.gateway-workspace/r4_default_515`；Workspace Root disabled，页面没有
     修改或迁移入口。
   - 从新建页用同一 Agent ID、不同名称和 `.r4-duplicate-root` 再次提交，页面保留表单并显示
     `409 (agent_id already exists)`，没有成功跳转或重新分配。
2. **有效非 canonical custom root、skill 分组与父目录错误**
   - 在 custom 表单填写
     `.r4-path-base/intermediate/../custom_target`。填写后 Skills 只显示 `Global` 与
     `Compatibility (Claude/Codex)`，没有 `Local` 分组。
   - `r4_noncanon_515` 创建成功；详情 root 为目标 Gateway canonicalize 后的
     `.r4-path-base/custom_target`，证明原始非空值到达目标节点并由节点解释。
   - 以 `.r4-missing-parent/agent` 提交 `r4_bad_parent_515`，页面留在原表单，Workspace 字段显示
     `The parent directory does not exist on wt-review-feat-515-r4-36191.`。
3. **已有目录、transient reconnect 与同节点占用**
   - 预置 `.r4-existing-515/user-file.txt`；第一次提交 `r4_existing_515` 只出现黄色 existing-directory
     提示与确认框，此时没有 `.nanoassistant`。
   - 勾选确认后临时停止本轮主 Gateway，创建显示 503 且草稿和确认状态不丢失；用同一隔离 config
     重连后再次提交成功，详情显示固定 root，sentinel 保留，`.nanoassistant` 此时才出现。
   - 主节点再用同一路径创建 `r4_conflict_515` 时，Workspace 字段明确显示该目录已归属
     `r4_existing_515`，没有转成已有目录确认流程。
4. **双节点同字符串路径**
   - 第二 Gateway 按校正后的 Runbook 使用 `.gateway-node-2-runtime/` 内独立 config、PID、log、
     workspace base 和 config-adjacent runtime state，并连接同一隔离 IM。
   - 在 `e2e-node-2` 用与主节点完全相同的 `.r4-existing-515` 创建 `r4_crossnode_515`；第一次只提示
     existing directory，确认后成功，详情显示 owning node `e2e-node-2` 和相同 root 字符串。
5. **原型与 390×844 响应式回归**
   - 通过 worktree-local HTTP 直接打开 `prototype.html` 的 default、custom、existing warning 状态，
     与真实产品逐状态对照。
   - 产品 390×844 页面保持 Identity → Workspace → Behavior 顺序；default/custom 纵向排列，custom
     helper 明确目标节点和 parent 约束，无横向溢出。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` / card order | Workspace 位于 Identity 与 Behavior 之间 | 真实 Vite 页面 snapshot + screenshot | 1440×1000；390×844 | match |
| `prototype.html` / mode chooser | default/custom 二选一且默认选中 | desktop 与 mobile 首屏 default checked；custom 切换后字段出现 | desktop + 390×844 | match |
| `prototype.html` / custom path | 目标节点、父目录要求与字段错误 | helper 指向选中节点；missing parent 原因在 Workspace 字段旁 | desktop custom/error；390×844 custom | match |
| `prototype.html` / existing directory | 醒目提示、确认框和再次提交 | 黄色 alert、确认前零初始化；503 后草稿保留；重连重试成功 | desktop existing + transient reconnect | match |

## Acceptance Criteria Coverage

### Requirement: 创建 Agent 时可选择默认目录或自定义路径 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 使用默认目录创建 Agent | `spec.md`；prototype mode chooser | Journey 1，真实 desktop 创建与详情 | default radio 首屏 checked；详情显示节点分配 root | pass | Round 3 结论得到本轮真实回归 |
| 使用自定义路径创建新的 workspace | `spec.md`；design opaque forwarding | Journey 2，提交有效非 canonical path | 创建成功；详情显示目标节点 canonical root；草稿 Skills 无 `Local` 分组 | pass | target Gateway 独自解释路径 |
| 自定义路径的父目录不可用 | `spec.md`；prototype custom error | Journey 2，missing parent | 字段旁显示目标节点原因；表单保留；未创建 Agent | pass | HTTP 422 是预期可恢复结果 |

### Requirement: 采用已有目录前须提醒用户 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自定义路径是已有目录 | `spec.md`；prototype existing state | Journey 3，确认前、503、重连重试 | 黄色 alert + checkbox；确认前无初始化；503 保留草稿；重连后成功且 sentinel 保留 | pass | 完成产品流 transient retry |

### Requirement: 同节点 workspace root 只可归属一个 Agent — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一节点的路径已被另一个 Agent 使用 | `spec.md` | Journey 3，主节点重复提交已归属 root | 字段显示归属 `r4_existing_515`；无确认框、无新 Agent | pass | ownership 提示与 existing 提示可区分 |
| 不同节点的同字符串路径 | `spec.md`；校正后的双节点 Runbook | Journey 4，两个在线 Gateway、相同 absolute string | 第二节点仅要求 existing 确认；确认后成功且详情为 `e2e-node-2` | pass | distinct runtime directory 可照文档执行 |

### Requirement: 创建后 workspace root 固定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看已有 Agent 的设置 | `spec.md`；Round 1 blocking issue | Journey 1，详情只读检查 + duplicate-ID poke | root disabled、无迁移入口；重复 ID 显示 409 且不跳转 | pass | Round 1 问题持续关闭 |

## Additional Product Probes

| Probe | Expected | Observed | Result |
|---|---|---|---|
| Valid noncanonical custom draft | Forward to target Gateway; do not classify as local workspace | No `Local` skill group; create succeeded with canonical target root | pass |
| Existing-directory retry across reconnect | Recover without losing confirmation draft | Offline submit showed 503; reconnect + same-form retry succeeded | pass |
| Duplicate Agent ID with divergent root | Reject before reassignment | 409 on create form; no success navigation | pass |
| Expected HTTP errors | Surface inline without unrelated product failure | 422/409/503 appeared with corresponding inline messages; no unexpected console error | pass |

## Issues

None.

## Side Findings

None.

## Environment and Cleanup

- 隔离 IM: `http://127.0.0.1:59553`；Vite: `http://127.0.0.1:59620`；prototype HTTP:
  `http://127.0.0.1:61004`。未使用生产 `:8011`、默认 Gateway config 或日常 workspace。
- 主节点: `wt-review-feat-515-r4-36191`；第二节点: `e2e-node-2`。第二节点完全使用
  `.gateway-node-2-runtime/`，校正后的 Runbook 可直接执行。
- 浏览器 console 只有 React development 提示、prototype favicon 404，以及旅程预期触发的
  HTTP 422/409/503 resource entries；没有额外产品异常。
- 完成后按持有的 PID/session 停止第二 Gateway、重连后的主 Gateway、Vite、prototype server，
  再执行 worktree `e2e-down.sh`；确认三个监听端口释放。主会话授权提供的临时 `node_modules`
  symlink 在清理时删除，未提交。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变跨包依赖或部署拓扑。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：unit delta 已覆盖创建选择、节点路径语义、确认、
  node-scoped ownership、opaque mirror/provenance 和 fixed-root；待 orchestrator 收尾归并 canonical。
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

---

# Round 5 — 2026-08-08

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 → 91bf97d94a5c5c64a76a9c993aebdc3a5041a23d`
>
> Revalidation mode: full（fix delta `bb9cb43e0457c9c67beb1eed7e81da607b988634..91bf97d94a5c5c64a76a9c993aebdc3a5041a23d`）

## Highest Required Action

`pass`

## Verdict

`pass`

七个首文档 Scenario 与四条 prototype must-match 均在隔离双 Gateway 真栈和真实浏览器中通过。
Round 5 重点回归同样通过：正常已存在 Agent `r5_default_515` 不能从新建页以另一 root 重新创建，
页面返回 `409 (agent_id already exists)`、保留完整草稿且不发生成功跳转；default、custom、已有目录
确认路径均未出现新错误。

会话蒸馏来源的三个用户态得到同一真实 conversation 的连续证据：无消息时在线 Gateway 明确显示
`No transcript` 并禁选；Gateway 临时离线时显示 `Transcript temporarily unavailable` 并禁选，
没有误显示 `No transcript`；产生真实 transcript 后该来源可选并启用 `Distill to skill`。另一个
Gateway 的 ready 来源在单独选择前可选，选择主 Gateway 来源后立即禁选并标记
`Different Gateway node`。

## User Journeys Exercised

1. **默认创建、固定详情与 duplicate-ID（desktop 1440×1000）**
   - 在主节点 `wt-review-feat-515-r5-62016` 使用默认选中的 `Use default directory` 创建
     `r5_default_515`；详情显示节点分配的 `.gateway-workspace/r5_default_515`。
   - `Workspace Root` disabled，且没有编辑或迁移入口。
   - 回到新建页用同一 Agent ID、另一名称和 custom root 提交，页面显示
     `409 (agent_id already exists)`；名称、描述、路径和 instructions 草稿全部保留。
2. **自定义新路径与父目录错误**
   - 使用 parent 已存在而 target 不存在的 `.r5-path-base/custom_target` 创建
     `r5_custom_515`，详情显示 exact canonical root 且只读。
   - 使用 `.r5-missing-parent/agent` 创建 `r5_bad_parent_515`，页面停留在原表单，并在 Workspace
     字段旁显示目标节点的 `The parent directory does not exist ...`；未出现成功 Agent。
3. **已有目录、Gateway 离线与重连恢复**
   - 预置 `.r5-existing-515/user-file.txt`；第一次提交只出现醒目的 existing-directory alert 与
     checkbox，确认前没有 `.nanoassistant`。
   - 勾选确认后临时停止本轮主 Gateway；提交显示
     `503 (target_node_id is not connected)`，路径、描述、确认状态和警示完整保留。
   - 以同一隔离 config 重连同一 Gateway 后再次点击创建即成功；sentinel 内容未变，
     `.nanoassistant` 只在成功后出现。
4. **同节点占用与双节点同字符串路径**
   - 主节点再以 `.r5-existing-515` 创建 `r5_conflict_515`，页面明确显示目录归属
     `r5_existing_515`，没有转成 existing-directory 确认。
   - 按 Runbook 在 `.gateway-node-2-runtime/` 启动独立 `e2e-node-2`；同一 root 字符串第一次只要求
     existing-directory 确认，确认后 `r5_crossnode_515` 创建成功，详情 owning node 为
     `e2e-node-2`。
5. **transcript 状态与来源选择**
   - 主节点无消息 conversation 在线时为 disabled `No transcript`；停止主 Gateway 后刷新为
     disabled `Transcript temporarily unavailable`，文案没有混淆。
   - 重连后通过真实聊天产生 transcript；该来源可选，选中后 `Distill to skill` enabled。
   - 在第二 Gateway 的预置 `e2e-node-2` workspace（不是共享 root）产生第二条真实 transcript；
     两个来源未选择时都可选，选中主节点来源后第二节点来源 disabled 且显示
     `Different Gateway node`。
6. **原型逐状态对照与 390×844 响应式**
   - 通过 worktree-local HTTP 打开 `prototype.html` 的 default、custom、existing warning 状态，
     与真实产品的对应状态逐项对照。
   - Chrome 的 CSS viewport 实测为 `390×844`，`scrollWidth == clientWidth == 390`；default/custom
     纵向堆叠，长 custom path 不造成横向溢出，Workspace 仍位于 Identity 与 Behavior 之间。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` / card order | Workspace 位于 Identity 与 Behavior 之间 | 真实 Vite 页面截图 + accessibility DOM | desktop 1440×1000；CSS 390×844 | match |
| `prototype.html` / mode chooser | default/custom 二选一且默认选中 | desktop 与 390px default checked；custom 切换后字段出现 | desktop + 390×844 | match |
| `prototype.html` / custom path | 目标节点、父目录要求与字段错误 | helper 指向选中节点；missing parent 原因位于 Workspace 字段旁；长路径无横向溢出 | desktop error；390×844 custom | match |
| `prototype.html` / existing directory | 醒目提示、确认框和再次提交 | alert + checkbox；确认前零初始化；503 保留确认草稿；重连后成功 | desktop existing / unavailable / recovered | match |

## Acceptance Criteria Coverage

### Requirement: 创建 Agent 时可选择默认目录或自定义路径 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 使用默认目录创建 Agent | `spec.md`；prototype mode chooser | Journey 1，真实 browser 创建与详情 | default 首屏 checked；详情显示节点分配 root | pass | duplicate-ID probe 也未改写原 Agent |
| 使用自定义路径创建新的 workspace | `spec.md`；prototype custom state | Journey 2，提交 parent 可用的新 target | 创建成功；详情 root 为目标 canonical path | pass | default/custom 均无新错误 |
| 自定义路径的父目录不可用 | `spec.md`；prototype field error | Journey 2，missing parent | Workspace 字段旁显示目标节点原因；草稿保留；无 Agent | pass | HTTP 422 为预期可恢复结果 |

### Requirement: 采用已有目录前须提醒用户 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自定义路径是已有目录 | `spec.md`；prototype existing state | Journey 3，确认前、Gateway 离线、重连重试 | alert + checkbox；确认前无初始化；503 保留确认；成功后 sentinel 保留 | pass | transient unavailable 可恢复 |

### Requirement: 同节点 workspace root 只可归属一个 Agent — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一节点的路径已被另一个 Agent 使用 | `spec.md` | Journey 4，主节点重复提交已归属 root | 字段显示归属 `r5_existing_515`；无确认框、无新 Agent | pass | ownership 与 existing 提示明确区分 |
| 不同节点的同字符串路径 | `spec.md`；双节点 Runbook | Journey 4，两个在线 Gateway、相同 absolute string | 第二节点只要求 existing 确认；确认后成功，详情为 `e2e-node-2` | pass | 独立 config/runtime/node identity |

### Requirement: 创建后 workspace root 固定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看已有 Agent 的设置 | `spec.md`；Round 1 blocking issue | Journey 1，详情只读 + duplicate-ID 重新创建 | root disabled、无迁移入口；duplicate 返回 409 且不跳转 | pass | 正常 existing Agent 不可 re-create |

## Additional Product Probes

| Probe | Expected | Observed | Result |
|---|---|---|---|
| Existing Agent ID + divergent custom root | Reject without re-creating or reassigning | 409 on create form; full draft and original Agent preserved | pass |
| Existing-directory submit while Gateway offline | Clear recoverable failure without losing confirmation | 503 inline; draft, checkbox and alert retained; reconnect retry succeeded | pass |
| Explicit missing transcript | Only actual missing binding says `No transcript` | Online empty conversation disabled as `No transcript` | pass |
| Temporarily unavailable transcript | Disabled, retryable wording; never `No transcript` | Same conversation offline became `Transcript temporarily unavailable` | pass |
| Ready transcript selection | Ready source selectable and enables next action | Checkbox enabled; selection enabled `Distill to skill` | pass |
| Cross-Gateway source selection | Do not mix transcript sources across nodes | Both ready initially; after one selection, other disabled as `Different Gateway node` | pass |

## Issues

None.

## Side Findings

None.

## Environment and Cleanup

- 隔离 IM: `http://127.0.0.1:52475`；Vite: `http://127.0.0.1:52501`；prototype HTTP:
  `http://127.0.0.1:54827`。未使用生产 `:8011`、默认 Gateway config 或日常 workspace。
- 主节点: `wt-review-feat-515-r5-62016`；第二节点: `e2e-node-2`。第二节点使用 Runbook 指定的
  `.gateway-node-2-runtime/` 隔离 config、runtime state、workspace base、node identity 和进程；
  文档可直接完成双节点旅程。
- desktop 使用 Codex in-app browser；390×844 使用 Chrome，并以页面实时值确认
  `innerWidth=390`、`innerHeight=844`、`scrollWidth=clientWidth=390`。三个相关 browser tab 的
  console warning/error 列表均为空。
- 结束时依次停止第二 Gateway、重连后的主 Gateway、Vite、prototype server，再执行 worktree
  `e2e-down.sh`；确认 `52475`、`52501`、`54827` 均无 listener，且无本轮 tmux session。
- 本轮 runtime config、日志、SQLite、测试 workspace、sentinel 目录和临时 `node_modules` symlink
  均移入废纸篓，可恢复；`git status` 在写报告前为 clean。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变跨包依赖或部署拓扑。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：unit delta 已覆盖创建选择、确认、node-scoped
  ownership、fixed root、operation-correlated recovery，以及 transcript `ready/missing/unavailable`；
  current `docs/specs/im/web-chat-ux.md` 已包含 unavailable 与 missing 的用户可见区分，待 orchestrator
  收尾归并其余 delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本轮未创建 out-of-unit GitHub issue。

---

# Round 6 — 2026-08-08

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 → 85d4f98948526b3316344e515c74ffc0e41408ec`
>
> Revalidation mode: targeted（fix delta `2bd4af837..85d4f9894`；继承 Round 5 完整覆盖）

## Highest Required Action

`pass`

## Verdict

`pass`

Round 6 的 transcript 状态修复在隔离真栈和真实浏览器中通过：正常在线、明确没有 transcript 的
conversation 仍显示 `No transcript`；删除专用测试 AgentProfile 后保留的 legacy conversation 显示
`Transcript temporarily unavailable`；停止其所属隔离 Gateway 后，正常 Agent conversation 也显示
`Transcript temporarily unavailable`，两种 unavailable 状态均禁选且未误报为 `No transcript`。

同时重跑了创建主路径冒烟：默认目录、自定义新目录、已有目录二次确认均成功，详情 root 只读；
用正常已有 Agent ID 从新建页提交另一 root 仍返回 `409 (agent_id already exists)`，原 root 未改变。

## User Journeys Exercised

1. **workspace 创建冒烟**
   - 默认选中的 `Use default directory` 创建 `r6_default_515`，详情显示节点分配 root 且只读。
   - `Custom path` 创建 `r6_custom_515`，详情显示目标节点 canonical root。
   - 已有目录第一次提交只显示醒目 alert 与确认 checkbox；确认后 `r6_existing_515` 创建成功。
2. **transcript 三态 delta**
   - 在线 Gateway 下打开 `r6_default_515` 的空 conversation；Generate skill 中为 disabled
     `No transcript`。
   - 停止仅本轮 Gateway 并刷新；同一 conversation 变为 disabled
     `Transcript temporarily unavailable`。
   - 重连后创建专用 `r6_legacy_515` conversation；精确确认隔离数据库、fixture Agent、conversation、
     user 与 node 后，仅删除该 AgentProfile 一行。真实浏览器刷新后，conversation 保留并显示 disabled
     `Transcript temporarily unavailable`。
3. **正常已有 Agent 不可重新创建**
   - 从新建页以 `r6_default_515` 和另一 custom root 提交，页面保留草稿并显示
     `409 (agent_id already exists)`；随后详情仍显示原 Agent ID 与原 default root。

## Reference Artifacts Reviewed

Round 5 对 `prototype.html` 四条 must-match 已完成 desktop + 390px 真浏览器对照。本轮 delta 不触及这些
视觉契约；targeted 复验以真实 desktop 创建页确认 Workspace 卡顺序、default/custom chooser、custom
helper、existing alert 与 checkbox 均未回归。

## Acceptance Criteria Coverage

| Requirement / Scenario | Round 6 验证 | 结果 | 备注 |
|---|---|---|---|
| 创建 Agent / 使用默认目录 | Journey 1，真实浏览器创建与只读详情 | pass | 本轮重跑 |
| 创建 Agent / 使用自定义新路径 | Journey 1，真实浏览器创建与只读详情 | pass | 本轮重跑 |
| 创建 Agent / 父目录不可用 | 继承 Round 5 完整真栈证据 | pass | delta 未触及 |
| 已有目录前提醒 | Journey 1，alert、checkbox、确认后成功 | pass | 本轮重跑 |
| 同节点路径已归属 | 继承 Round 5 完整真栈证据 | pass | delta 未触及 |
| 不同节点同字符串路径 | 继承 Round 5 双 Gateway 证据 | pass | delta 未触及 |
| 创建后 workspace root 固定 | Journey 3，duplicate-ID 409 + 原详情 root 不变 | pass | 本轮重跑 |

## Delta Scenario Matrix

| Scenario | Expected | Observed | Result |
|---|---|---|---|
| Explicit missing transcript | 仅 Gateway 明确确认缺失时显示 `No transcript` | 在线空 conversation disabled 为 `No transcript` | pass |
| Gateway unavailable | 显示 retryable unavailable，不误报 missing | Gateway offline 后 disabled 为 `Transcript temporarily unavailable` | pass |
| Legacy / missing Agent binding | 无可路由 AgentProfile 时显示 unavailable | 专用 AgentProfile 删除后 conversation 保留，disabled 为 `Transcript temporarily unavailable` | pass |
| Normal existing Agent create | 不得重新创建或改变 root | 409；草稿保留；详情仍为原 default root | pass |
| Default / custom / confirmation smoke | 三条创建路径不回归 | 三条均成功且 fixed root 正确 | pass |

## Issues

None.

## Side Findings

None.

## Environment and Cleanup

- 隔离 IM: `http://127.0.0.1:64350`；Vite: `http://127.0.0.1:62027`；节点:
  `wt-review-feat-515-r6-96216`。未使用生产 `:8011`、默认 Gateway config 或日常 workspace。
- `e2e-up.sh` 在本机慢启动时先于 IM readiness 报超时；仅使用其生成的本轮 config/secret/SQLite，
  按 `worktree-runtime.md` 的同一隔离拓扑手工持有 IM、Gateway 与 Vite。该现象未改变产品结论。
- legacy fixture 删除前通过 API 与隔离 SQLite 同时确认 `agent_id=r6_legacy_515`；删除结果恰为一行，
  并复核 conversation、Agent user、node 均仍各保留一行。
- 真实浏览器最终 console warning/error 为空；所有本轮浏览器 tab、tmux session、监听端口、runtime
  文件与临时 `node_modules` symlink 在提交前清理并复核。

## Upper-level Documentation Sync

- [x] `SPEC.md`：无需更新；不改变跨包依赖或部署拓扑。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：现有 delta/current spec 已表达 transcript
  `ready/missing/unavailable` 和 fixed workspace root，本轮无需新增契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本轮未创建 out-of-unit GitHub issue。

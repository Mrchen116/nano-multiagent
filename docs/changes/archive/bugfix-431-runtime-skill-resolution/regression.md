# bugfix-431 — 回归验证

> 对齐: incident.md v1
> Review Round: 1 — 2026-06-24
> Reviewer: bugfix-431-reviewer

---

## Verdict

**pass**

**Highest Required Action**: pass

**Issues count**: blocking: 0, major: 0, minor: 0

---

## 验收标准覆盖

### Requirement: runtime skill resolution 与 preview 同源

incident.md 定义的成功标准：对同一 agent 配置的 skills，preview 展示的技能集合 == runtime 真实注入 `<available_skills>` 的技能集合，且两者同源（不能是两套独立实现）。

#### Scenario: PA skills 出现在 preview 中

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §现象与复现，澄清 Q2 |
| 验证方式 | 调用 `POST /im/v1/agents/default-agent/prompt-preview` 传 `skill_ids=["change-design-author","change-orchestrator","change-impl-worker","systematic-debugging","doc"]` |
| 证据 | Preview 返回 `<available_skills>` 含 5 个 skills，路径为 `/Users/czj/Repos/nano-multiagent/.claude/skills/change-design-author/SKILL.md` 等（来自 `~/.nanoassistant/skills → ~/.claude/skills` 软链） |
| 结果 | **pass** |
| 备注 | 含 4 个 PA skills（非 codex-only 路径）均正确解析 |

#### Scenario: runtime 对话时 LLM 请求包含与 preview 一致的 PA skills

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §现象与复现（修前只剩 1 个 skill），澄清 Q2 |
| 验证方式 | 给 default-agent 配置 5 个 skills（含 4 个 PA skills），发送真实消息触发 agent 运行，查 LLM proxy 日志 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-06-24_16-04-50_557_sess_b2b766bf9765aa4d/2026-06-24_16-04-50_557-req-anthropic_messages.json` |
| 证据 | LLM 请求中 `<available_skills>` = 5 个 skills，完整列表见下，CWD = `/worktrees/unit-bugfix-431/.gateway-workspace/default-agent` 确认是该 agent |
| 结果 | **pass** |

**Runtime skills 清单**（来自 LLM proxy 请求日志）：
```
/Users/czj/Repos/nano-multiagent/.claude/skills/change-design-author/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-impl-worker/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator/SKILL.md
/Users/czj/.codex/skills/doc/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/systematic-debugging/SKILL.md
```

**Preview skills 清单**（来自 prompt-preview API）：
```
/Users/czj/Repos/nano-multiagent/.claude/skills/change-design-author/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-impl-worker/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator/SKILL.md
/Users/czj/.codex/skills/doc/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/systematic-debugging/SKILL.md
```

两个列表**完全一致**（路径相同、数量相同，均为 5 个）。修复前 runtime 只会出现 1 个 skill（codex-only 路径），现在全 5 个均出现。

#### Scenario: 12 个 skills 场景 preview 全部解析

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §原始报告（product-manager 配置 12 个 skills 的场景） |
| 验证方式 | 调用 `POST /im/v1/agents/default-agent/prompt-preview` 传 12 个 skill_ids（11 个 PA skills + 1 个 codex skill） |
| 证据 | Preview 返回 `<available_skills>` 含 12 个 skills，全部来自正确路径（PA skills → `~/.claude/skills/`，codex skills → `~/.codex/skills/`） |
| 结果 | **pass** |

**12-skills preview 清单**：
```
/Users/czj/Repos/nano-multiagent/.claude/skills/change-code-review/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-design-author/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-design-reviewer/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-impl-worker/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-retro/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-reviewer/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-reviewer/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/change-verifier/SKILL.md
/Users/czj/.codex/skills/doc/SKILL.md
/Users/czj/Repos/nano-multiagent/.claude/skills/systematic-debugging/SKILL.md
```

---

## 复现验证

### 修前行为（per incident.md）

> 配置 12 个 skills → 运行时 `<available_skills>` 只剩 1 个（`skill-creator`，来自 `~/.codex/skills`），11 个 PA skills 均丢失。

### 修后验证

- 配置 5 个 skills（含 4 个 PA skills）
- 发消息触发真实对话
- LLM proxy 日志显示 `<available_skills>` = 5 个，与 preview 完全一致，无 skills 丢失
- **修前症状（runtime 只剩 codex-only 路径的 skills）已消除**

---

## 回归测试

### 相关功能回归

| 功能 | 状态 | 说明 |
|---|---|---|
| IM 与 Gateway 正常通信 | pass | Gateway 连接 IM，node `wt-unit-bugfix-431` online |
| agent 对话可触发 | pass | 发送消息，agent 正常回复 "hi!" |
| prompt-preview API 可用 | pass | 传 skill_ids，返回含 `<available_skills>` 的完整 system prompt |
| Gateway 将 IM config skills 写回本地 config | pass | Gateway 把配置的 5 个 skills 同步写回了 `.gateway-config.yaml` |

---

## 自动化测试增量

**测试结果**：`pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` → **2499 passed, 0 failed**（较 M1 worker 的 2495 增加 4 个新测试）。

新增回归测试（per progress.md）：
- `test_make_skill_resolver_lives_in_core`：确认 `make_skill_resolver.__module__ == "agent.core.skills.discovery"`，helper 住 core 而非 sdk，防止 `core→sdk` 反向依赖
- `test_agent_sdk_boundary_contract`：确认 core 无 `import agent.sdk` 反向依赖（合法方向）
- 同源行为回归测试（`test_runtime_resolve_vs_list_skills_same_set`）：断言 `runtime.resolve_available_skills` 与 `kernel.list_skills` 对同一 agent 配置返回相等的 skill 集合

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 修的是 core/sdk 内部 skill resolution 路径，不改变包间依赖关系或四包职责描述。
- [x] `docs/specs/kernel/spec.md`（内核契约层）：**需要更新**（已有 delta-spec `docs/changes/bugfix-431-runtime-skill-resolution/specs/kernel/spec.md`）。新增 Requirement：runtime skill resolution 与 preview/list_skills 同源（均经 `make_skill_resolver`）。orchestrator 收尾归并写入。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。skill resolution 是内核行为，不影响开发约定或启动命令。
- [x] `docs/SPEC_GUIDE.md`：**无需更新**。本 unit 未改变文档体系。

---

## Side Findings

无。本轮旅程中未发现明显的 out-of-unit 或 regression 问题。

---

## 澄清记录（§2.6）

无疑问，验收口径清晰，直接开始走旅程。

---

## 服务环境

| 项 | 值 |
|---|---|
| IM 端口 | 56868（ephemeral） |
| Gateway | `--foreground --auto-bind --config .gateway-config.yaml` |
| Gateway node_id | `wt-unit-bugfix-431` |
| LLM proxy session | `2026-06-24_16-04-50_557_sess_b2b766bf9765aa4d` |
| 前端产物 | 本轮重建（`npm run build`，worktree 内） |
| 服务清理 | 本轮起的 IM + Gateway 进程均已 kill |

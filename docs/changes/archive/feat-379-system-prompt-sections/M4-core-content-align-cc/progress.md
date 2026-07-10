# feat-379-M4 Progress

## 启动说明

- 依赖：M1(section-framework) 已 DONE (HEAD 756f82e5)
- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-379-M4`
- 分支: `milestone/feat-379-M4`
- CC 核实文件: `~/Repos/opensource-hub/claude-code/src/constants/prompts.ts`（已亲自阅读，非笔记）

---

### R1 — 写失败单测（Red 阶段）

- Context: M1 stub 的三个段（actions_care/tool_rules/tone_style）render 返回 None；
  core.system 存在但缺 system-reminder/injection/compress 等关键内容。
  需要先立失败测试锁定要求，再填充文案。
- Decision: 在 `tests/unit/agent/test_core_sections_m4.py` 新建 24 个断言，覆盖四个段的
  关键短语（从 CC `prompts.ts` 核实后提炼）。
- Rationale: 后端纯内容改动，C1 = 失败单测；无前端/入口验收需要（文案变化，reviewer 验收行为）。
- Evidence:
  - Tests: `pytest tests/unit/agent/test_core_sections_m4.py` → 1 failed (system-reminder 缺失)，其余 stub-render-None 失败预期
  - Entry: N/A（纯文案，无独立 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（reviewer 验收行为）
  - Visual/Interaction: N/A
- Rollback: commit 925dba9e（C1 Red 测试）
- Commits: C1=925dba9e
- Next: R2-R5 填充四段文案（合并为一次实现提交）

---

### R2-R5 — 填充四段文案（Green 阶段）

合并为单 C2 提交（四段均只改 `core_sections.py`，无交叉依赖）。

- Context: 亲自阅读 CC `prompts.ts` 对应函数后确认要对齐的内容。
- Decision: 基于 CC 改写（CC-adapted），去掉 coding-CLI 专属和 CC 产品专属内容，保留通用部分。

#### 逐段 review 记录

**core.system（order=200）**

- CC 源: `getSimpleSystemSection` (prompts.ts:~186)
- 保留: GFM markdown note、denied-tool-call "adjust your approach" 规则、system-reminder 说明、
  prompt-injection flag 提示、hooks 说明、auto-compress notice。
- 移除: "monospace font / CommonMark"（IM 环境非终端字体）；
  `getSimpleIntroSection` 的 coding-CLI 引言（不属 core.system）。
- 结论: 已对齐 CC 通用规范；比 M1 stub 多出 4 个关键机制说明。

**core.actions_care（order=210）**

- CC 源: `getActionsSection` (prompts.ts:getActionsSection)
- 保留: reversibility/blast-radius 框架、confirm-before-risky 默认、
  authorization-scope 约束（"approving once does NOT mean all contexts"）、
  destructive-shortcut 禁止（--no-verify 举例）、investigate-before-overwrite 原则。
- 移除: git/CI/PR 专属举例（"deleted branches, pushed code, creating/closing PRs"）改为
  通用的 "deleted data, unintended messages sent"；
  CLAUDE.md 引用（coding-CLI 概念，PA 无此文件）。
- 结论: 核心风险意识与 CC 一致；去除 coding-workflow 专属词汇。

**core.tool_rules（order=220）**

- CC 源: `getUsingYourToolsSection` (prompts.ts:getUsingYourToolsSection)
- 保留: dedicated-tools-over-bash 原则（file-read/file-edit/glob/grep 举例）、
  parallel-vs-sequential 规则。
- 移除: task/TODO 工具指引（coding-CLI 专属）；REPL-mode 分支；embedded-search-tools 分支；
  CC 具体工具常量名（Read/Edit/Write）改为通用描述。
- 纠正: M1 stub render→None，且 M1 骨架注释错误说"用 bash grep"（来自 design 对旧状态的描述）；
  M4 把方向纠正为"专用工具优先"。
- 结论: 与 CC 通用规范一致；去除 CLI 专属分支。

**core.tone_style（order=230）**

- CC 源: `getSimpleToneAndStyleSection` (prompts.ts:getSimpleToneAndStyleSection)
- 保留: emoji-only-on-request、file_path:line_number 格式、owner/repo#123 格式、
  no-colon-before-tool-calls 规则（完整原文）。
- 移除: "Your responses should be short and concise"（非 ant 模式的 CC 简洁提示，
  PA 已在自己的 guidelines 段处理语气，这里加反而双重约束）。
- 结论: 4 条规则完全对齐 CC 原文；仅省略 1 条 PA 已覆盖的规则。

#### 验收结果

- Evidence:
  - Tests: `pytest tests/unit/agent/ tests/integration/test_prompt_sections_golden.py`
    → 411 passed, 0 failed（基线 387 + 新增 24）
  - Entry: N/A（纯文案段，无独立 HTTP 入口；reviewer 行为验收）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（golden 测试在 411 内全部通过）
  - Visual/Interaction: N/A
- Rollback: commit cad68218（C2 实现）
- Commits: C1=925dba9e, C2=cad68218, C3=（本 docs commit）
- Next: 集成到 unit/feat-379 分支

# feat-428 — 验收报告

> 对齐: spec.md 验收标准 + design.md §Runbook for Reviewer
> review_round: 1
> 日期: 2026-06-23

## Verdict

pass

## 澄清记录

开工前无疑问，直接走旅程。

## User Journeys Exercised

| 旅程 | 描述 | 覆盖 Scenario |
|---|---|---|
| J1: CLI 主路径 | 在含 AGENTS.md 的工作区验证机制 A 注入 system prompt + PREVIEW 占位 | 机制A·有AGENTS.md / 空态 / @import / IM预览占位 |
| J2: CLI 机制B·内 | read 工作区内子目录文件，验证 tool_result 含 AGENTS.md 正文 | 机制B·内注入 / 空态 / 根去重 |
| J3: CLI 机制B·外 | read 工作区外 git 仓文件，验证 tool_result 含英文路径提示（不含正文） | 机制B·外提示 / 非git边界 / 去重 |
| J4: PA 路径 | assemble_prompt_preview with PA workspace 验证 AGENTS.md 占位出现 | PA 下机制A生效 |
| J5: 关闭 nested_memory | nested_on=False 时 read 不注入，机制A不受影响 | 关闭Req |

## 用户旅程体验

### J1：Coding CLI — 机制A（启动注入 system prompt）

工作区 `/tmp/.../test-workspace/AGENTS.md` 内容：
```
## 约定
- 函数命名使用 snake_case
- 所有 public API 必须有 docstring
```

直接调用内核 `load_agents_md` → `PromptContext(agents_md_content=...)` → 手动组装 `KERNEL_PROMPT_SKELETON` 得到 system prompt：

- system prompt 包含 `<project-instructions>` 标签
- 内容含 `snake_case`、`docstring`
- 段位验证：`core.agents_md_block`（pos=12，`cache_safe=True`）在 `slot.custom`（pos=11）之后、`core.memory_block`（pos=13，`cache_safe=False`）之前——满足稳定前缀末尾约束

`assemble_prompt_preview` 验证：PREVIEW 模式输出 `<project-instructions><运行时注入：工作区 AGENTS.md></project-instructions>`，与 MEMORY/USER 占位形式一致。

空态验证（无 AGENTS.md）：`CORE_AGENTS_MD_BLOCK.enabled_when(ctx_without) == False`，段不渲染，不报错。

### J2：机制 B·内（read 工作区内文件）

临时目录中 `ws/backend/AGENTS.md`（内容："BACKEND CONVENTIONS - RESTful style"），读 `ws/backend/api/user.py`：

tool_result 包含：
```
<project-instructions path="...ws/backend/AGENTS.md">
BACKEND CONVENTIONS - RESTful style
</project-instructions>
```

根去重验证：将根 AGENTS.md 路径预置入 `SessionFileState.loaded_agents_md` 后，机制 B 回溯不重复注入。

### J3：机制 B·外（read 工作区外 git 仓文件）

外部仓 `other-repo/`（含 `.git` 和 `AGENTS.md`，内容："OTHER PROJECT RULES"），workspace 在别处，读 `other-repo/src/main.py`：

tool_result 包含：
```
<project-instructions-hint>
The file you just read is outside your workspace, in the project rooted at .../other-repo.
This project ships instruction file(s) describing its conventions, not loaded here to save context:
  .../other-repo/AGENTS.md
Read any of them with the read tool if you need this project's conventions before working in it.
</project-instructions-hint>
```

- 英文提示，含路径，**不含正文**（"OTHER PROJECT RULES" 不出现）
- 非 git 仓路径（`/private/tmp`）：`find_outermost_git_root` 返回 None，不给提示

### J4：PA agent — assemble_prompt_preview

PA workspace 含 AGENTS.md，`kernel.assemble_prompt_preview(workspace_root=pa_workspace)` 返回 dict：
```python
{
  "prompt": "...<project-instructions>\n<运行时注入：工作区 AGENTS.md>\n</project-instructions>...",
  "section_count": N
}
```
占位出现，PA 设置页 IM 前端请求此 API 可展示 AGENTS.md 占位段。

### J5：关闭 nested_memory

`nested_on=False` 时：read 工作区内含 AGENTS.md 子目录的文件，tool_result 不含 `project-instructions`，文件正文正常返回。

机制 A 不受影响：`CORE_AGENTS_MD_BLOCK.render(ctx_with_content)` 仍正常输出。

## 验收标准覆盖

### Requirement: 启动时把工作区 AGENTS.md 注入 system prompt（机制 A，默认恒开）— 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工作区根有 AGENTS.md | spec.md §验收标准 | 调用 load_agents_md + KERNEL_PROMPT_SKELETON 组装，system_prompt 含 project-instructions 标签及内容（snake_case/docstring） | RUNTIME 组装输出含 `<project-instructions>` + AGENTS.md 正文 | pass | J1 |
| 工作区根无 AGENTS.md（空态） | spec.md | `enabled_when(ctx_without) == False`，组装不报错 | 代码验证：空 ctx enabled_when 返回 False，无异常 | pass | J1 |
| 两个产品都生效 | spec.md | CLI 通过 KERNEL_PROMPT_SKELETON 组装验证；PA 通过 assemble_prompt_preview 验证 | J1/J4 均观察到 project-instructions 占位/内容 | pass | CLI + PA 两路均验 |
| 工作区根 AGENTS.md 含 @import | spec.md | load_agents_md 读含 `@./sub.md` 的 AGENTS.md，验证展开后含 sub.md 内容 | 展开内容含"被引用的内容" | pass | J1，sub.md 内容合并确认 |
| IM 设置页系统提示预览显示 AGENTS.md 注入位 | spec.md | assemble_prompt_preview PREVIEW 模式，验证含 `<project-instructions><运行时注入：工作区 AGENTS.md>` | PREVIEW 段输出确认 | pass | J1/J4，与 MEMORY/USER 占位形式一致 |
| 会话运行中 AGENTS.md 被改（压缩窗口内冻结，压缩边界刷新） | spec.md | test_agents_md_runtime_snapshot.py `test_invalidate_clears_snapshot_and_loaded_agents_md`——失效后下轮重读 | 5 passed（含 `test_invalidate_*`） | pass | 冻结/刷新属 MemorySnapshot 生命周期内部，测试覆盖有效 |

### Requirement: read 工作区内文件时就近带上 AGENTS.md 内容（机制 B·内）— 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 读到的文件目录链上有子目录级 AGENTS.md | spec.md | ReadTool.run + ToolContext，读 `backend/api/user.py`，观察 tool_result 含 `<project-instructions path=...>` | J2 tool_result 含 "BACKEND CONVENTIONS" | pass | J2 |
| 读到的文件目录链上没有 AGENTS.md（空态） | spec.md | test_inside_workspace_no_agents_md_returns_plain | 13 passed，含该 case | pass | 单元测试覆盖 |
| 命中的是已注入过的工作区根 AGENTS.md（去重） | spec.md | `test_inside_workspace_dedup_skips_root_preseeded_by_mechanism_a` + 代码验证预置根路径后不重复 | 13 passed | pass | 去重集预置验证 |
| 注入后该 AGENTS.md 被改、同会话再 read（压缩窗口内冻结，压缩边界刷新） | spec.md | `test_compaction_clear_allows_reinjection` | 13 passed，含该 case | pass | |

### Requirement: read 工作区外文件时注入路径提示而非全文（机制 B·外）— 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 读到工作区外某 git 项目内的文件，该项目有 AGENTS.md | spec.md | ReadTool.run 读 `other-repo/src/main.py`，验证 tool_result 含英文提示 + 路径 + 不含正文 | J3: `<project-instructions-hint>` 含路径，"OTHER PROJECT RULES" 未出现 | pass | J3 |
| 读到不属于任何 git 仓的工作区外文件（边界） | spec.md | `find_outermost_git_root("/private/tmp") == None`；`test_outside_workspace_not_git_no_hint` | J3 验证 + 13 passed | pass | |
| 同一外部 AGENTS.md 被多次命中（去重） | spec.md | `test_outside_workspace_hint_dedup_once` | 13 passed | pass | |

### Requirement: nested_memory 可在配置层关闭，关闭后机制 A 不受影响— 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 关闭 nested_memory 后 read 不再触发目录加载/提示 | spec.md | `nested_on=False` 时 ReadTool.run，tool_result 不含 project-instructions；`test_disabled_flag_no_injection_inside` | J5 确认 + 13 passed | pass | 同时验证机制 A 仍输出 project-instructions |

## 问题清单

无问题。

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 不改跨包依赖方向或部署图）
- [x] `docs/specs/kernel/spec.md`（内核契约层）：**需要更新**——delta-spec 已在 `docs/changes/feat-428-nested-project-instructions/specs/kernel/spec.md` 准备，orchestrator §7.0 收尾归并写入 canonical
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新（未改文档体系）

## 测试结果摘要

| 测试集 | 结果 |
|---|---|
| `tests/unit/test_agents_md_loader.py`（17 tests）| 17 passed |
| `tests/unit/test_agents_md_runtime_snapshot.py`（5 tests）| 5 passed |
| `tests/unit/test_nested_memory_read_injection.py`（13 tests）| 13 passed |
| `tests/` -m "not e2e" 全量（2815 tests）| 2815 passed, 0 failed, 1 skipped |
| IM 前端 vitest（59 files, 449 tests）| 449 passed |

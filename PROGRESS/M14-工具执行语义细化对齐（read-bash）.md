# PROGRESS (Milestone: M14)

- Title: 工具执行语义细化对齐（read/bash）
- Goal: 将 `read` 与 `bash` 的执行/返回语义补齐到《内核设计细化/工具设计细化.md》要求，消除图片读取、输出截断与 fullOutputPath 等高风险偏差。
- Exit Criteria:
  - `read` 支持图片输入并返回 `text+image` 结构；文本截断与 offset 提示语义通过 contract/integration 验证。
  - `tool_result` 对 list content 透传语义稳定，不再破坏 `read` 图片 parts。
  - `bash` 对齐“无默认超时”与“截断落盘 + fullOutputPath”契约，并覆盖超大输出/超时/中断测试。
  - `pytest -q` 全绿，且工具相关 e2e/contract 回归通过。
- Test command: `pytest -q`
- Branch: `milestone/M14`

### Baseline
- Context:
  - 按执行要求先读取 `LOGBOOK.md`，当前仅有 hook 加载断言稳健性规则，与 M14 直接冲突为无。
  - M14 允许改动范围：`src/nano_multiagent/tools/**`、`src/nano_multiagent/agent/runtime.py` 中 `tool_result` 相关最小改动、M14 相关 tests 与文档。
  - M14 禁止范围：与 M14 无关的 provider/runtime/session 大范围改动。
- Evidence:
  - Tests: `pytest -q` -> `177 passed, 2 skipped`
  - Entry: 当前基线全绿，可直接进入 Roadpoint 红测驱动。
- Next:
  - R14.1

### 续跑接手（2026-03-02）
- Context:
  - 接手输入契约确认：`execution_mode=serial`、`use_worktree=false`、`branch=milestone/M14`、`test_command=pytest -q`。
  - `data/dev-tasks.json` 中 M14 当前为 READY，按续跑要求在本分支继续执行并最终收口。
  - 本次接手未发现 `prevention_rules` 注入项，仅沿用 `LOGBOOK.md` 现有规则。
- Decision:
  - 保持既有三 Roadpoint 拆分不变，按 `R14.1 -> R14.2 -> R14.3` 顺序执行 C1/C2/C3。
- Rationale:
  - 三项 exit criteria 分别对应 read/tool_result/bash，串行推进可减少交叉回归。
- Evidence:
  - Tests: `pytest -q`（本次接手复跑）=`177 passed, 2 skipped`
  - Entry: 代码基线可复现，全量门禁稳定。
- Rollback:
  - `cf66bd8`（handoff docs）可作为续跑前稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - R14.1 Red

### Handoff
- Context:
  - 用户中止当前执行并要求控制塔切换新执行者续跑 M14。
  - 当前仅完成 Plan 阶段，尚未进入任一 Roadpoint 的 C1 Red。
- Evidence:
  - Stable commit: `33eee54`（包含 TASKS/PROGRESS 计划骨架）
  - `data/dev-tasks.json`: `M14` 已从 `RUNNING` 释放为 `READY`（`claimed_by=null`）。
- Rollback:
  - 新执行者从 `33eee54` 继续即可；无需额外回退。
- Next:
  - 新执行者从 R14.1 开始执行 C1（先写红测）。

### R14.1 read 语义补齐（图片输入 + 文本截断/offset 提示）
- Context:
  - 现状仅支持 UTF-8 文本读取；读取图片直接触发 `UnicodeDecodeError`，且文本截断后无 next offset 提示。
  - 目标是让 `read` 对图片返回 `text+image` parts，并让文本截断结果可直接指导下一次分段读取。
- Decision:
  - 在 `ReadTool` 中加入图片后缀识别（jpg/jpeg/png/gif/webp），图片分支返回 `content=[text_part, image_part]`。
  - 文本分支在触发截断且可继续读取时追加 `[output truncated; continue with offset=<next>]` 提示。
  - 对非 UTF-8 且非支持图片类型文件返回明确 `ToolError`，避免底层解码异常上浮。
- Rationale:
  - 图片结构直接对齐细化设计并可被 hook/tool_result 链路消费。
  - 提示文案与 `next_offset` 对齐，减少模型二次推断偏差，提升分段续读稳定性。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`（6 failed，验证缺口）
    - Green: `pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`（17 passed）
    - Gate: `pytest -q`（183 passed, 2 skipped）
  - Entry:
    - `ToolRegistry.execute("read", {"path":"pixel.png"})` 返回 `text+image` 两段结构；
    - 截断文本输出包含 `offset=<next_offset>` 提示且 `next_offset` 同步更新。
- Rollback:
  - `1010408`（R14.1 测试红测提交）
- Commits: C1=1010408, C2=9a99b2c, C3=<pending>
- Next:
  - R14.2 Red：补 `tool_result` list content 透传红测。

### R14.2 tool_result list content 保真透传
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R14.3 bash 语义对齐（无默认超时 + 截断落盘 fullOutputPath）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

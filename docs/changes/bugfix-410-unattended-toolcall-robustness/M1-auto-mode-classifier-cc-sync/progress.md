# M1 progress — auto-mode-classifier-cc-sync

范围（design.md M1 行，严格限定）：仅 `auto_mode_gate.py` + `test_auto_mode_gate.py` 的
transcript/prompt 改动。完全不碰 reason 体系（registry.py / base.py / reason 字段，归 M2）。

## 退出标准达标证据

### 1. build_transcript_entries 从 LLMMessage.tool_calls 提取（#99 B2 core）

`auto_mode_gate.py:build_transcript_entries` assistant 分支新增 kernel-format fallback：
当 `content` 不含 `tool_use` block 时，回退读 `LLMMessage.tool_calls` 独立字段
（`LLMToolCall.name` / `.arguments`），逐 call 走 `project_tool_input` 投影。
Anthropic-format（`content:[{type:tool_use}]`）路径保留为优先，兼容不破。

根因核实：`loop.py:359` 把 `message_history` 喂的是真实 `LLMMessage` 对象，assistant
turn 的工具调用在独立 `tool_calls` 字段（`interfaces.py:27`），`content` 是文本。旧实现
只读 content 里的 tool_use → 永远 no-op → 历史工具调用静默丢弃。

### 2. 单测改喂真实 LLMMessage，堵 false-green

`TestBuildTranscriptEntries` 的 fixture 从 Anthropic-shaped dict 改为真实
`LLMMessage(role="assistant", content=<text>, tool_calls=(LLMToolCall(...),))`。
新增 `test_kernel_tool_calls_field_extracted`（专钉 #99）+
`test_anthropic_content_format_still_supported`（兼容路径）。

**证伪**（去掉 fallback `if not tool_uses and tool_calls:` → `if False and ...`）：
```
4 failed, 5 passed
  test_assistant_tool_use_included
  test_assistant_mixed_content_only_tool_use
  test_kernel_tool_calls_field_extracted
  test_ordering_preserved
```
确认 false-green 已堵——旧 false-green fixture 永远绿是因为喂了代码恰好命中的 Anthropic 格式。

### 3. XML suffix 对齐 CC 2.1.177（Q7）

基准源：实际安装的 CC 2.1.177 二进制
`/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`（214MB 编译版），
用 Python 从 JS bundle 区提取模板字面量 `Vp3`（stage-1 强化）/ `yp3`（stage-2 强化）。
消费点实测：`Y==="both" ? Vp3 : Np3`（两阶段模式用强化版 Vp3），stage-2 用 `yp3`。

- `XML_S1_SUFFIX`：旧短版 → Vp3 强化版（「Stage 1 不应用 user intent/ALLOW 例外，留给
  stage-2；按完整效果判，别看表面形式；任一规则可能命中即 block」）。em-dash 用真实字符 `—`。
- `XML_S2_SUFFIX`：补 yp3 末尾「Think longer on ambiguous or borderline actions; keep
  reasoning brief for clear-cut ones.」
- `TestXmlSuffixCcBaseline` 钉死两 suffix 的 load-bearing 短语，防回退短版。

### BASE_PROMPT 主体范围决策

实测 CC 2.1.177 的 system prompt 主体是**完全重写**（Evaluation Rules + HARD/SOFT BLOCK
+ User Intent Rules + 6 步 Classification Process + Definitions + Environment），非增量；
现有「automated security classifier」/「single new action」措辞在 2.1.177 已不存在。
两阶段 `<block>` 输出契约 + `permissions_template` 占位 + 投影逻辑未变（Q7 判断对）。

**orchestrator 拍板：选 A** — 只对齐两个 suffix（XML_S1_SUFFIX 强化版 Vp3 +
XML_S2_SUFFIX yp3），**BASE_PROMPT 主体保持现状，不整体移植**。理由：(1) design M1 口径
是「对明显落后项对齐」，两个 suffix 是确定的明显落后项；主体「数千行 prose 完全重写」是
「全量复刻」而非「落后项对齐」，超出口径。(2) bugfix-410 是会话健壮性 bugfix，不是 auto_mode
分类器质量重构；主体重写会引入新的 HARD/SOFT BLOCK 分类、9 条 User Intent Rules、6 步
Classification Process 等**新行为契约**——这些改变分类判断质量，本 unit 既无验收 Scenario
覆盖、也不该在 bugfix 里夹带。

> **遗留发现（建议单独立 unit）**：CC 2.1.177 BASE_PROMPT 主体已完全重写（非增量），
> 超出 bugfix-410 范围。建议单独立 unit 做「分类器 prompt 主体跟齐 2.1.177 + 对应分类
> 行为验收」（带 HARD/SOFT BLOCK、User Intent Rules、6 步 Classification Process 的行为
> Scenario）。本 M1 仅对齐两个 suffix（明显落后项），主体维持现状。

## 测试结果

- `tests/unit/test_auto_mode_gate.py`：32 passed
- sibling `test_auto_mode_gate_hook.py` + `test_auto_mode_gate_allowlist.py`：34 passed
- `ruff check` + `ruff format --check`：全绿

## 可观察面（reviewer）

无直接产品 UI 变化。可观察面 = LLM proxy 日志里分类器请求的 `<transcript>` 现含历史工具调用
投影（覆盖 incident Req「分类器 transcript 包含历史工具调用」Scenario）。

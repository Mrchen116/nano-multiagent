# M1 tasks — auto-mode-classifier-cc-sync

范围（design.md M1 行，严格限定）：仅 `auto_mode_gate.py` + `test_auto_mode_gate.py` 的
transcript/prompt 改动。完全不碰 reason 体系（归 M2）。

## 测试策略

- 落层：纯单元测试（`tests/unit/test_auto_mode_gate.py`），无 e2e/集成依赖。
- 测什么：transcript 构造对真实 `LLMMessage`（tool_calls 独立字段）的提取正确性、防注入
  不变量（assistant 自由文本 / tool_result 不进 transcript）、两 suffix 与 CC 2.1.177
  strings 基准一致。
- 不测什么：分类器实际判断质量（黑盒 LLM，无确定输出）；BASE_PROMPT 主体行为（选 A 不动）。
- false-green 防御：fixture 改喂真实 `LLMMessage`/`LLMToolCall`（旧 Anthropic-shaped
  fixture 恰好命中代码、永远绿，掩盖 #99）。证伪：去掉 fallback → kernel-format 测试转红。

## Roadpoints

- [x] **R1 (C1 红测)** — DONE
  - fixture 从 Anthropic-shaped dict 改喂真实 `LLMMessage(role=assistant,
    content=<text>, tool_calls=(LLMToolCall(...),))`；新增 `test_kernel_tool_calls_field_extracted`
    钉 #99、`test_anthropic_content_format_still_supported` 守兼容路径。
  - 证伪验证：去掉 fallback → 4 个 kernel-format 测试转红。

- [x] **R2 (C2 实现)** — DONE
  - `build_transcript_entries` assistant 分支加 kernel-format fallback：content 无
    tool_use 时回退读 `LLMMessage.tool_calls`（`LLMToolCall.name`/`.arguments`），逐 call
    走 `project_tool_input` 投影；Anthropic-format 路径保留为优先（兼容不破）。
  - `XML_S1_SUFFIX` → CC 2.1.177 强化版 Vp3（stage-1 不应用 user intent/ALLOW 例外、按
    完整效果判、任一规则可能命中即 block；em-dash 真实字符）。
  - `XML_S2_SUFFIX` → CC 2.1.177 强化版 yp3（补「Think longer on ambiguous...」）。
  - `TestXmlSuffixCcBaseline` 钉死两 suffix load-bearing 短语。
  - contract 白名单 `.nanocode` 行号 707→749（本次编辑行移位）。
  - **选 A**：BASE_PROMPT 主体保持现状，不整体移植 2.1.177 重写版。

- [x] **R3 (C3 文档)** — DONE
  - progress.md：退出标准证据 + 证伪结果 + CC 2.1.177 基准源 + 选 A 决策 + BASE_PROMPT
    主体重写遗留发现（建议单独立 unit）。
  - 本 tasks.md。

## 退出标准达标

- gate 三文件（test_auto_mode_gate{,_hook,_allowlist}.py）：66 passed。
- contract：127 passed（含白名单行号修正）。
- ruff check + format：全绿。
- 主仓零污染（改动只在 unit/bugfix-410）。

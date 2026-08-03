# bugfix-490-M1: 并行 tool_result 上线合并 — Tasks

> 对齐: ../fix.md

## 目标

Anthropic Messages 上线前，把内部多条连续 `role=tool` 合成一条仅含全部 `tool_result` 的 `user`，使严格上游（DeepSeek 等）在并行工具后再发下一句不再 400。

## 退出标准

- [x] `AnthropicMapper.map_generate_request` 将连续 tool_result user 合并为一条；配对与顺序保留。
- [x] 单测覆盖：并行两条 tool → 上线仅一条 user、两条 tool_result；后续普通 user 仍独立。
- [x] 内部 loop 仍可按条存 `role=tool`（既有 `test_loop_parallel_tool_results` 不改语义）。
- [x] 真实上游：DeepSeek 拒拆条、收合并（证据见 `evidence/`）。
- [x] 回填 `fix.md`「修复」「验证」。

## 测试策略

- 被测行为(来自退出标准): 并行 tool 上线格式合并为一条 user；普通 user 不与之误并。
- 已有测试在: `tests/unit/test_llm_anthropic_mapper.py`（扩展）
- 落层/目录/marker: tests/unit/ ，无 marker
- 可选依赖 importorskip: 无
- 本 milestone 产生的一次性验收证据(收尾保留于 evidence，不进套件): DeepSeek SPLIT/MERGED 对照日志

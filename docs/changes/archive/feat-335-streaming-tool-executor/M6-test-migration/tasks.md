# M6-test-migration: 现有测试迁移

## Goal
修复所有因接口变更而失败的现有测试， FakeLLMClient 改为 async generator。

## Roadpoints

### R6.1 FakeLLMClient 改造
- `FakeLLMClient.generate()` 改为 `async def`，返回 `AsyncIterator[LLMMessage]`
- 支持 yield 多个 `LLMMessage`（模拟 content blocks）
- **文件**: 测试 helper 文件（需查找）
- **验收**: `pytest` 中所有使用 FakeLLMClient 的测试编译通过

### R6.2 单元测试批量修复
- `test_agent_runtime.py`
- `test_agent_loop.py`
- `test_loop_retry.py`
- 所有 mock LLMClient 的测试
- **验收**: 上述测试全部通过

### R6.3 全仓库回归测试
- `pytest tests/unit/` 全部通过
- `pytest tests/integration/` 全部通过
- `pytest tests/contract/` 全部通过
- **验收**: 无失败测试

## 验收标准
1. `pytest tests/unit/` 全部 pass
2. `pytest tests/integration/` 全部 pass
3. `pytest tests/contract/` 全部 pass
4. 无 xfail、无 skip（除非合理说明）

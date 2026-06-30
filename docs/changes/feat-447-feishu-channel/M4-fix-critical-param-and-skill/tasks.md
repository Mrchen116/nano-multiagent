# feat-447-M4: fix-critical-param-and-skill — Tasks

> 对齐: ../design.md, ../verification.md

## 目标

修复 verifier 报告中的 5 个 issues（1 CRITICAL + 1 WARNING + 3 SUGGESTION），确保飞书 channel 功能可用、skill 完整、文档对齐。

## 退出标准

- [ ] CRITICAL: main.py `_build_channel_registry` 正确传入 `group_context_store` 给 FeishuAdapter，Gateway 启动不再抛 `TypeError`
- [ ] CRITICAL: 补充不 mock FeishuAdapter 的集成测试，验证构造参数完整性
- [ ] WARNING: skill `feishu-doc.md` 补充文件夹创建和文件移动命令（或说明替代方案）
- [ ] SUGGESTION: M1 tasks.md 退出标准勾选与 DONE 状态对齐
- [ ] SUGGESTION: 移除 feishu_adapter.py 未使用的 `typing.Any` 导入
- [ ] SUGGESTION: skill 中超范围部分（wiki/sheet/chat）加注说明

## 测试策略

- 被测行为：
  1. `_build_channel_registry` 构造 FeishuAdapter 时传入所有必需参数（含 group_context_store）
  2. 不 mock FeishuAdapter 的集成测试验证真实构造通过
  3. skill 文档完整性（文件夹创建、文件移动命令或替代方案）
- 已有测试：`tests/unit/test_feishu_integration.py`（全部 mock 了 FeishuAdapter，掩盖了缺参 bug）
- 落层/目录/marker：`tests/unit/`，marker：无
- 本 milestone 产生的一次性验收证据：无（后端 API，测试即验收）

## Roadpoints

### R1 — 修复 CRITICAL: main.py 缺 group_context_store 参数 `DOING`

- 步骤:
  1. C1: 写红测试——不 mock FeishuAdapter 的集成测试，验证构造参数完整性（含 group_context_store）
  2. C2: 修改 `_build_channel_registry` 创建 GroupContextStore 实例并传入 FeishuAdapter；可选传入 bot_open_id
  3. C3: 更新 tasks.md + progress.md
- 验证: 红测试先失败（确认缺参 bug），修复后全绿

### R2 — 修复 WARNING: skill 缺 mkdir/move 命令 `TODO`

- 步骤:
  1. C1: 无（纯文档改动，无代码断言可写）
  2. C2: 在 `skills/feishu-doc.md` 补充文件夹创建和文件移动命令（或说明 feishu-cli 不支持时的替代方案）
  3. C3: 更新 progress.md
- 验证: skill 文件覆盖 spec 全部 Scenario

### R3 — 修复 SUGGESTION: 文档和代码清理 `TODO`

- 步骤:
  1. C1: 无（纯文档/代码清理，无代码断言可写）
  2. C2: M1 tasks.md 退出标准勾选；移除 feishu_adapter.py 未使用的 `typing.Any`；skill 超范围部分加注
  3. C3: 更新 progress.md
- 验证: 全量测试 `pytest -m "not e2e"` 全绿


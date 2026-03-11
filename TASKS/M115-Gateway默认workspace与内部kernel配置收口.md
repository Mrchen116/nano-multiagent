# M115 Gateway 默认 workspace 与内部 kernel 配置收口

## 目标
让 gateway agent 在用户未显式指定 `workspace_root` 时默认使用 `~/nano-assistant/workspace/<agent_id>/`；同时将 `kernel.base_url` 视为内部实现细节，不再要求用户在面向用户的 gateway 配置中填写。

## Exit Criteria
1. gateway 配置在缺省 `workspace_root` 时自动解析到 `~/nano-assistant/workspace/<agent_id>/`。
2. 默认 `workspace_root` 在需要时会自动创建，并且显式指定目录时继续接受已有目录。
3. 面向用户的最小 gateway 配置不再要求填写 `kernel.base_url`。
4. 启动文档、默认示例与相关测试口径一致。
5. gateway 真实启动与配置加载相关测试全绿。

## Roadpoints

### R1 默认 workspace_root 解析与创建
- **Acceptance**:
  1. `agents[].workspace_root` 允许省略。
  2. 省略时默认解析到 `~/nano-assistant/workspace/<agent_id>/`。
  3. 默认目录不存在时由加载流程自动创建。
  4. 用户显式提供 `workspace_root` 时仍使用显式值，并继续要求其为可接受目录。
  5. 行为通过配置加载与入口链路测试固化。
- **Tests Plan**:
  - unit: 需要；覆盖配置加载默认解析、目录创建、显式配置不回退默认。
  - contract: 不单独新增；当前配置契约由 dataclass + loader 语义覆盖，避免超 scope 扩散。
  - integration: 不单独新增；`run_gateway`/runtime 入口测试已覆盖配置加载到启动编排。
  - e2e: 需要；补充真实入口配置缺省 `workspace_root` 的启动/加载验证。
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
- **DoD**: `PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py` 全绿 + C1/C2/C3 齐全 + PROGRESS 写清决策/证据/哈希
- **Status**: DONE

### R2 kernel.base_url 内部化与文档示例收口
- **Acceptance**:
  1. 用户最小 gateway 配置示例可省略 `kernel.base_url`。
  2. 配置加载在省略 `kernel.base_url` 时仍得到稳定内部默认值。
  3. 真实启动相关测试不再依赖用户显式填写 `kernel.base_url`。
  4. `README.md` 与 `docs/operator-runbook.md` 示例、说明、故障排查口径一致。
  5. 不引入与本 milestone 无关的配置重构。
- **Tests Plan**:
  - unit: 需要；覆盖 `kernel.base_url` 缺省加载与启动路径默认值接线。
  - contract: 不单独新增；本 milestone 只收口用户配置口径，不扩 schema 层。
  - integration: 不单独新增；沿用现有 runtime 编排测试作为配置接线验证。
  - e2e: 需要；更新真实入口/真实进程测试中的最小配置示例，证明缺省配置可启动。
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- **DoD**: `PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py` 全绿 + C1/C2/C3 齐全 + PROGRESS 写清决策/证据/哈希
- **Status**: DONE

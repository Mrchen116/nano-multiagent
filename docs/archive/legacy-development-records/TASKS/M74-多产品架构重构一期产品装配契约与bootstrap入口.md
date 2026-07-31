# TASKS/M74 - 多产品架构重构一期：产品装配契约与 bootstrap 入口

## Milestone 目标
为 src/nano_multiagent 引入 ProductProfile / ResolvedProductConfig 与统一 bootstrap 入口，建立后续多产品重构的总开关，同时保持当前 coding 行为默认兼容。

## Roadpoints

---

### R74.0 修复测试集合错误（__init__.py 命名冲突）

**状态**: DONE

**Acceptance**:
1. `pytest -q` 不再报 `import file mismatch` 错误
2. 所有 test 目录有 `__init__.py` 使其成为 Python 包
3. 原有通过测试数量不减少

**Tests Plan**:
- 直接运行 `pytest -q`，无 ERROR 行即通过

**DoD**: pytest -q 无 collection error + C1/C2/C3

---

### R74.1 ProductProfile + ResolvedProductConfig 数据契约

**状态**: DONE

**Acceptance**:
1. `nano_multiagent/platform/product.py` 包含 `ProductProfile` dataclass（product_id, display_name, config_namespace, default_system_prompt, default_tool_ids, default_hook_modules, skill_search_policy, session_store_policy, safety_defaults, capabilities）
2. `nano_multiagent/platform/product.py` 包含 `ResolvedProductConfig` dataclass（resolved_system_prompt, tool_registry, hook_registry, session_store, safety_config）
3. 两个 dataclass 可正常实例化
4. contract 测试验证字段集稳定

**Tests Plan**:
- unit: 实例化字段完整性
- contract: 字段名/类型约束（防止意外缩减）

**Expected Tests**:
- `tests/unit/test_product_profile.py` - 实例化与默认值验证
- `tests/contract/test_product_profile_contract.py` - 字段名集合稳定

**DoD**: pytest -q 全绿（允许原有5个预存失败）+ C1/C2/C3

---

### R74.2 platform/bootstrap.py - 产品配置解析入口

**状态**: DONE

**Acceptance**:
1. `bootstrap_product(profile, repo_root)` 接收 `ProductProfile` + `repo_root` 返回 `ResolvedProductConfig`
2. 返回对象包含可用的 `tool_registry`、`hook_registry`、`session_store`
3. 不在 runtime/loop 内部引入 product 参数或分支
4. integration 测试验证 bootstrap 可从 ProductProfile 构造出可注入的对象集

**Tests Plan**:
- unit: bootstrap 调用后返回 ResolvedProductConfig 且字段非 None
- integration: 使用返回的 tool_registry 验证内置工具可加载

**Expected Tests**:
- `tests/unit/test_platform_bootstrap.py` - bootstrap 基本返回类型
- `tests/integration/test_bootstrap_integration.py` - 端到端构造验证

**DoD**: pytest -q 全绿 + C1/C2/C3

---

### R74.3 local_coding ProductProfile stub

**状态**: DONE

**Acceptance**:
1. `nano_multiagent/platform/products/local_coding.py` 包含 `LOCAL_CODING_PROFILE: ProductProfile` 常量
2. 该 profile 的 default_system_prompt 与现有 `DEFAULT_SYSTEM_PROMPT` 等价
3. bootstrap 该 profile 产出与当前 app.py 手动拼装行为一致

**Tests Plan**:
- unit: LOCAL_CODING_PROFILE 字段值验证
- contract: profile 与现有系统提示词一致性

**Expected Tests**:
- `tests/unit/test_local_coding_profile.py` - profile 字段正确性

**DoD**: pytest -q 全绿 + C1/C2/C3

---

### R74.4 server/app.py 接受 ProductProfile 启动

**状态**: DONE

**Acceptance**:
1. `create_app()` 新增可选 `product_profile: ProductProfile | None = None` 参数
2. 当传入 `product_profile` 时，使用 bootstrap 解析的对象；否则用当前默认逻辑（向后兼容）
3. 原有 `test_app_factory.py` 测试全部通过（不传 profile 时行为不变）
4. 新增测试验证通过显式 profile 启动时 app 正常

**Tests Plan**:
- unit: 通过 ProductProfile 启动 app 后 tool_registry/hook_registry 存在
- integration: 已有 app factory 测试仍通过

**Expected Tests**:
- `tests/unit/test_app_factory.py` 现有测试保持绿色
- 新增 `tests/unit/test_app_factory_with_profile.py`

**DoD**: pytest -q 全绿 + C1/C2/C3

# bugfix-429-M1: per-agent-model — Tasks

> 对齐: ../design.md v1

## 目标

在 IM 上为 agent 选定的模型真实生效：每个新 run 由产品层把「该 agent 当前 default_model（没选则产品默认）」传到内核，内核按模型注册的 provider 路由到对应 client 发请求。改模型后旧会话也用新模型；IM 下拉展示每个模型的 provider；动态新建 agent 的 default_model 持久化、重启保留。

## 退出标准

- [ ] `kernel.submit(model=...)` 必填，model 存入 RunRecord；后台 worker 与内核续跑都从 RunRecord.model 取
- [ ] loop 移除 `self._model` 对话用途，按 run 携带的 `model_override` 发请求
- [ ] build_kernel 建 `dict[provider,client]`，`provider_of(model)` 选 client；跨 provider（anthropic/openai_compat）都生效
- [ ] reconfigure_llm / bind_llm_client 退役删除；CLI `/model`（llm-config set）改自维护 current model 每轮传
- [ ] Gateway inbound 主轮/stop、heartbeat/cron、内核续跑 全部给出 model 来源；agent 没选 → 产品层兜底 `llm.default_model`
- [ ] 链路B：动态新建 agent 的 default_model 写回用户实际 config 路径、重启保留（加日志钉真因后修）
- [ ] IM capabilities models 携带 provider；前端下拉每选项展示 provider
- [ ] `pytest -m "not e2e"` 全绿（含 im_service）；`npm run build` 通过
- [ ] **live 端到端**：IM 选 gpt-5.5 的 agent 对话后，LLM proxy 日志该请求 `model==codex_oauth:gpt-5.5`（非 kimi）

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - submit(model) → RunRecord.model → loop 发请求的 model 字段（透传链端到端单测）
  - `provider_of(model)` 反查正确（anthropic / openai_compat）
  - 内核续跑（stranded）复用本 run RunRecord.model
  - heartbeat/cron 包装器按 agent 解析 model
  - inbound_pipeline 主轮按 agent.default_model（没选用产品默认）传 model
  - 链路B 动态新建 agent default_model 落盘（reload config 读回）
  - IM capabilities models 序列化含 provider（API 层 + 前端 normalize）
  - 前端下拉每选项渲染 provider
- 已有测试在：
  - 内核透传：扩展 `tests/unit/agent/` 下 loop/runtime/registry 相关测试；submit 必填 model 影响大量调用点 → 同步改
  - reporter：`tests/unit/personal_assistant/` reporter 测试扩展 models provider
  - IM API：`tests/unit/im_service/` capabilities 测试扩展
  - Gateway model 解析：inbound_pipeline / heartbeat 测试扩展
  - 前端：`src/IM/frontend/src/features/settings/agents/*.test.tsx` + `im-agent-config-api.test.ts` 扩展
- 落层/目录/marker：tests/unit/ + tests/integration/（内核透传端到端） + 前端 vitest；live 验收走真实 IM+Gateway，非套件
- 可选依赖 importorskip：无新增
- 本 milestone 一次性验收证据（收尾删除，不进套件）：live e2e 的 LLM proxy 日志摘录、IM 截图 → 记 progress.md，不进 tests/

### 前端 UI（R5）

用户路径分类：`visual-only`（模型下拉每选项加 provider 标注，纯展示增强；选中/保存逻辑不变）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 下拉展开，每选项显示 `<model> · <provider>` |
| loading | N/A（capabilities 拉取态已有，不改） |
| empty | models 为空 → 仅平台默认占位项（已有行为） |
| error | N/A（拉取失败态已有） |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | 长 model name + provider 不溢出下拉 |
| missing/nullable data | 某选项缺 provider → 优雅降级只显 name |
| mobile viewport | 375 宽下拉可读 |
| desktop viewport | 1440 正常 |
| dark mode | N/A（项目未支持） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 下拉选项 provider 标注 | 组件测试（agent-detail/create）+ 真实浏览器截图 | 是（组件测试） |
| provider 缺失降级 | normalize 单测 + 组件测试 | 是 |
| 长 name 溢出 | 浏览器截图 | 否 |

## Roadpoints

### R1 — 内核 model 透传链（RunRecord.model → loop model_override）

- 状态: DONE（内核 model 透传链）

- 步骤: RunRecord 加 `model` 字段；`runs_registry.submit(model)` 存入；`_run_worker_async` 读 RunRecord.model 传 `runtime.run(model)`；内核续跑 self.submit 复用本 run model；`runtime.run/_run_locked/_execute_loop` 透传 `model_override`；`loop.run(model_override)` 用它发请求（保留 self._model 仅作兼容兜底直到 R2 移除）；`kernel.submit` 加必填 model。
- 验证: 红测先证明 submit(model=X) 后 loop 发请求 model==X、续跑复用本 run model；改全部 submit 调用点补 model；narrow 单测绿。

### R2 — 多 client 按 provider 路由 + provider_of + reconfigure_llm 退役

- 状态: DONE（多 client 路由 + provider_of；reconfigure 退役落 R6）

- 步骤: model_registry 补 `provider_of(model)`；build_kernel 遍历 config.providers 建 `dict[provider,client]`，注入 runtime/loop；loop 发请求时 `provider_of(model_override)` 选 client；移除 loop `self._model` 对话用途与 `bind_llm_client`；runtime `reconfigure_llm` 退役删除；`get_llm_config` 当前 active model 语义调整。
- 验证: 红测证明 openai_compat 模型走 openai_compat client、anthropic 模型走 anthropic client；删 reconfigure_llm 后无悬挂调用方（CLI 在 R6 改）；单测绿。

### R3 — Gateway 三入口传 model（inbound 主轮/stop + heartbeat/cron）

- 状态: DONE（Gateway 三入口传 model）

- 步骤: inbound_pipeline 构造注入 `product_default_model`；主轮/stop submit 传 `agent.default_model or product_default`；shim.submit_message 加 model 参数透传；heartbeat_scheduler/cron_runner 调用方解析 `agent.default_model or product_default` 传入。
- 验证: 红测证明 inbound 选 model 的 agent → submit 带该 model；agent 没选 → 带产品默认；heartbeat 同理。

### R4 — 链路B 动态新建 agent default_model 持久化

- 状态: DONE（链路B 当前已工作，补 regression 含默认路径场景；live 实测 source_path 写回）

- 步骤: 加日志钉死 gpt-probe 未落盘真因（_persist_agent_config 路径 / handle_agent_create 触发 / save_local_config 吞异常）；按真因修写回路径用用户实际 config、reconcile 覆盖动态 agent。
- 验证: 红测/复现脚本证明动态新建 agent default_model reload config 读得回；记真因到 progress。

### R5 — IM + 前端 provider 展示

- 状态: DONE（IM+前端 provider 展示；live 验 capabilities 带 provider）

- 步骤: `_models_from_kernel` 保留 provider（返回结构含 name+provider）；ReporterCapabilities.models 结构化 + as_payload；IM agents.py/nodes.py capabilities Pydantic models 带 provider；前端 CapabilitySnapshot.model_options 结构化、normalize 透传 provider、下拉渲染 `<model> · <provider>`。
- 验证: API 层单测 models 含 provider；前端组件测试断言 provider 文案；真实浏览器截图。

### R6 — CLI 自维护 current model 每轮传

- 状态: DONE（CLI 自维护 current_model + reconfigure_llm/bind_llm_client 退役 + 移除 llm-config set）

- 步骤: coding_cli 自维护 `current_model` 状态（启动从 args/env 初始化）；llm-config set --model 改自身状态不再调 reconfigure_llm；3 处 kernel.submit 传 model=current_model。
- 验证: 单测证明 set model 后下一轮 submit 带新 model；CLI 真实跑一轮验证。

### R7 — 端到端 live 验证 + 全树测试 + npm build

- 状态: DONE（live 三 Scenario 全 PASS：选 gpt→model=codex_oauth:gpt-5.5 / 没选→kimi / 改模型旧会话用新模型；空 provider 健壮代码层已做。数据层主 config 挂起等用户）

- 步骤: 真实起 IM+Gateway+前端产物，IM 选 gpt-5.5 的 agent 对话，查 LLM proxy 日志 model==codex_oauth:gpt-5.5；选 anthropic 模型验证跨 provider；改模型后旧会话验证。
- 验证: LLM proxy 日志摘录 + 截图入 progress；`pytest -m "not e2e"` 全树绿；`npm run build` 通过。

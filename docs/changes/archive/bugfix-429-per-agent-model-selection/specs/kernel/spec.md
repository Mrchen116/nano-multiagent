# Kernel 契约层增量 — bugfix-429

> 本 unit 对 `docs/specs/kernel/spec.md` 的草案增量。收尾由 orchestrator 据实际 diff 校正后并入 canonical。

## MODIFIED Requirements

### Requirement: 每轮对话的模型由消费者随 run 提供

模型不再是 kernel 级固化的全局属性（修订 refactor-406 决策5「model 维持 kernel 级」）；改为消费者在发起每个 run 时随 `submit` 提供，内核不持有对话默认 model。

#### Scenario: submit 携带 model 并在该 run 生效
- **WHEN** 消费者 `kernel.submit(session_id=..., parts=..., model=M)`
- **THEN** 该 run 的 LLM 请求以 `model=M` 发出（session JSONL 该 turn 记录可见）

#### Scenario: 同一 run 的内核续跑复用本 run 的 model
- **GIVEN** 一个以 `model=M` 提交的 run 在处理中产生了需续跑的消息
- **WHEN** 内核自身发起续跑
- **THEN** 续跑仍以 `model=M` 发出，不要求消费者再次提供，也不回退到任何内核默认

#### Scenario: 模型按其注册的 provider 路由请求格式
- **GIVEN** model `M` 在 config 注册于 provider `P`
- **WHEN** 以 `model=M` 提交 run
- **THEN** 内核用 `P` 声明的 client / 请求格式发出（不跨 provider 借用其它格式）

## REMOVED Requirements

### Requirement: 运行时经 reconfigure_llm 全局切换 provider/model

移除 canonical 中「`kernel.reconfigure_llm(provider, model)` 切换后 `get_llm_config()` 反映新值」的 Scenario（原 `docs/specs/kernel/spec.md:230-232`）。model 转为随 run 由消费者提供后，`reconfigure_llm`/`bind_llm_client` 失去调用方而退役；内核不再有"当前全局 active model"的概念。

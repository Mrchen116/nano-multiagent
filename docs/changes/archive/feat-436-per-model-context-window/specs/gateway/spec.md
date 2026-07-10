# gateway delta-spec — feat-436

> 本 unit 对 `docs/specs/gateway/spec.md` 的增量草案（design 期，收尾据实际 diff 校正）。
> 视角：运维者经 config.yaml 配置 + Gateway 行为可观察。

## ADDED Requirements

### Requirement: 模型可在配置中声明各自的上下文窗口

运维者可在 Gateway config 的 `llm.providers[].models[]` 条目上为某模型声明 `context_window`（与 `extra_request_body` 同级，可选）。该值随模型配置流入内核，并在用该模型的对话中决定上下文压缩的边界。未声明 `context_window` 的模型条目按内核默认上限处理；Gateway 回写 config 时保留已声明的 `context_window`，未声明的不写该字段。

#### Scenario: 某模型声明 context_window 后生效
- **GIVEN** config 某模型条目声明了 `context_window`（≠ 内核默认）
- **WHEN** 运维者用该模型经 Gateway 跑一个持续增长的对话
- **THEN** 压缩在该声明值对应的边界触发,而非内核默认上限边界

#### Scenario: 未声明 context_window 的模型按内核默认上限判定
- **GIVEN** config 某模型条目无 `context_window` 字段
- **WHEN** 运维者用该模型经 Gateway 跑对话
- **THEN** Gateway 正常启动并对话,按内核默认上限判定压缩,不因缺少该字段而报错

#### Scenario: context_window 配成非法值时回退
- **GIVEN** config 某模型条目把 `context_window` 写成非正整数
- **WHEN** 运维者用该模型经 Gateway 跑对话
- **THEN** Gateway 不崩溃,按未声明处理回退内核默认上限

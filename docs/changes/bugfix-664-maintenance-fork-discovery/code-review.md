# Code Review

## Scope and result

- Mode: full code review + Agent Context Implementation Review.
- Independent reviewer: `maintenance_fork_review`, gpt-6.1-sol/high，未参与实现。
- executed_base: `304c59412e8316ef3ea7df9d904a9a450ca618a2`。
- validated_at: `add1313dea5f3b80c6cf2a6251caf95e95489bec`，完整 7 文件 diff，无 dirty 范围。
- Findings: `[]`，无需修复的缺陷。

审查核实公开 getProvider/provider.start/descriptor 契约；原生 provider 继续负责父级历史、权限快照、8192 输出预算、取消和资源释放。普通委派保持原服务路径。显式维护轨迹保留启动边界、失败/取消状态、持久写屏障以及可信父链授权的冷读取。

## Context evidence

独立复跑 `knowledge-review.test.ts` 的新增联合维护用例：1 passed。真实锁定 DSH 的 llm/stream fixture 请求中，维护的 system message、完整 tools 与父请求一致；目录及原版 list_agents 不含维护；重启后的轨迹分页保留继承输入与工具证据，查看后维护 Agent 仍未加载。

复用作者 4 个相关测试文件 17 项通过证据。未验证真实 provider wire payload、真实模型自主行为、生产环境或存量目录治理；不将 fixture 证据描述为上述结果。

## Local checks

- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过。
- `python scripts/docs_check.py`：275 maintained Markdown sources / 68 routes 通过。
- `pytest -m "not e2e" -q`：70 passed / 32 deselected。
- `ruff check .`、`ruff format --check .`：通过。
- `pnpm test --maxWorkers=4`：140 files / 758 tests 全部通过。

## Main sync validity

origin/main 从 executed_base 推进到 `d72e220f1d21827c65e046f704c13837ea39d7c2`，仅改动另一 unit 的 `docs/changes/feat-625-auto-review-bounded-retry/spec.md`，没有运行代码、测试、Context 或本 unit 契约变化。同步后本 unit 的代码和测试与 validated_at 相同，因此保留独立代码/Context 审查与以上自动化结论；文档完整性在最终集成树重跑。effective_base 与 effective_through 的确切交付 Git 值写入 PR，避免用“无冲突”替代失效判断。

快速开发的用户实际验收尚未确认；独立代码审查通过不代替用户验收。unit 保留 active，不宣称已经归档或生产验收。

## 实际 Web 补验发现与修复

- R2-001 / CONFIRMED：原版运行时轨迹可读，但 Web 入口因 Work 身份索引缺少维护会话返回 `scope_not_allowed`。首次审查及 runtime fixture 未覆盖这一产品授权边界。
- 修复：KnowledgeUpdates 从可信 review 元数据发布既有 `session_linked` 身份链接，恢复 Work 注册及上传，不恢复模型目录发布或预读正文。
- 窄回归：PA knowledge 与 IM trajectory 共5项通过。真实模型的后代查询仍只列1个普通助手；2个 completed combined 维护不入目录。隔离 Node/DSH 重启后，Web 可打开原维护轨迹并检查输入/工具/输出。
- 独立 patch code/context review 核实了 Work 身份与权限链；之前未受影响的原生 provider 生命周期与请求前缀结论保留。

独立 patch 审查在 `9481ddf0b` 确认了同一入口问题的运行中时序：childSessionId 落盘后未立即通知，暂停且未写知识的维护仍可能到结束才登记。reviewer 的真实 DSH + KnowledgeUpdates 窄复现得到 running/hasChild=true/links=0，额外 recover 后 links=1。当前已增加身份落盘通知，并扩展既有暂停维护与产品身份回归。

Closure validated_at=`6ee61c7cfbef3fa7eb5be882bf947c1be4cb37a4`，finding_origin_head=`9481ddf0b9bc3e897cea4cf647a64a204a6d8d66`。同一独立 reviewer 返回 `[]`，R2-001 与运行中时序 P2 均 closed。独立重跑窄复现得到 running 状态下自动产生1条身份链接、触发1次 onWork，无需额外 recover。复用3文件10项窄回归与完成后实际 Web 冷轨迹证据，不冒充重新跑过真实模型。后续只补事实记录，没有受审实现变化。

## 最终全量中的测试取样修正

交付实现的本机首次全量为758 passed / 1 failed：既有 Bash/PTY disable 用例出现 `kill EPERM`，独立重跑通过，原因未确认。远端CI首次全量为758 passed / 1 failed：Workflow approval 用例在已观察到 turn/end 后再次查询子历史，第二次返回没有 events 的条目却直接执行 filter。该文件单独重跑2项通过；本机完整复跑又出现相同取样失败。

本机完整复跑另有知识维护用例超出默认 poll 等待：失败时落盘事实明确为首轮 error/memory_read_incomplete、第二轮仍 running 且已有 childSessionId，并非丢失第二次维护。调整为该文件已有的8秒维护等待预算。Workflow 用例改为在同一次成功观测上完成权限断言，并允许轮询期间出现没有 events 的原生诊断条目。两处仅修正回归取样和等待，不改变产品实现、不将上述失败记为全绿；修正后的窄回归、独立 patch 审查与最终全量结果写入 PR 和本机真实验收报告。

独立 patch review：base=`feb6bf4091acd5af7eda35e4cfd34e28f29feb12`，validated_at=`5c4386edb30b39d8c5af57fc8224291989abf0b4`，无 dirty 范围，返回 `[]`。同一 reviewer 核对原始失败现场和2文件6项通过日志，确认全部原权限和维护断言保留，未发现掩盖产品缺陷；仅测试观测/等待变化，无 Context 内容变化，未重复运行测试。此后只有事实文档变化，保留上述受审结论。

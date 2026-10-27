# refactor-668: 确定性 E2E — 技术方案

> 对齐: motivation.md

## Changelog

## 现状分析

### 涉及范围

critical_paths 的 live fixture 在 conftest.py 中启动共享真 IM/Node，默认模型为 DeepSeek；14 个测试以自然语言驱动模型。另 13 个测试使用 recording provider 或仅测进程，目录外还有 5 个环境生命周期测试。全量收集为 32 项。

### 既有约束

保持 DSH 公开接口边界；只在 provider HTTP 边界控制响应。遵循 testing.md 的最低有效层与重复失败原因合并规则。隔离端口/config/workspace/identity，关闭本轮所有进程，不触碰生产或真实代理。

### 可复用能力

复用 test_agent_config_context_continuity_critical_path.py 的 stub_llm_stack、请求记录和真实进程生命周期；必要时提取为共享 helper，避免新增测试继续扩大其 400 行以上文件。复用 anthropic_sse_ok_recording.py、compaction 和 approval recording fixture。已有 TS 原生运行时及产品模块测试覆盖 history、cron、workflow-lifecycle、communication、heartbeat 和路由（各 seam 不同，模块替身不证明 IM 接线）；只在覆盖同一失败原因且验证通过后合并删除，不根据名称推断覆盖。

### 相关历史

feat-421 引入真模型关键路径；refactor-581 已引入 recording 请求验证；feat-546 的 Global J2 混合了模型协作策略与产品 Inbox/child/dispatch 接线。当前测试应以实际 DSH/产品契约核实，不保留旧 kernel 术语和退役工具参数假设。

## 架构总览

IM HTTP/WS → 真 Node/DSH → 本地 recording provider → 预先确定的文本或工具调用 → 真工具与产品结果。记录 provider 实际收到的请求，断言历史、工具结果、来源和路由。夹具不得直接写产品 DB、伪造 Work 事件、跳过实际工具执行或根据预期结论补造上下文。

## 关键决策

1. **按失败原因处置全部 32 项。** 在本 unit 的 coverage.md 保存 keep / rewrite-merge / delete 映射和保留保护。涉及多层时明确高层独有的接线风险。
2. **默认关键路径不接外部 provider。** 全部常规 critical_paths 使用本地受控响应或无需模型，去掉 live proxy 门控和模型覆盖在此入口的暗示。手工产品模型验收仍沿用 daily，明确不属于此回归套件。
3. **Context 验证实际请求。** 普通重启与压缩重启分别保留所需历史；比较有意义的 messages/system/tools 与工具配对，允许新输入和动态元数据。fork 合并入既有 recording 覆盖，补分叉点截断与源/分支隔离，不再让模型背暗号。
4. **工具与事件保持真实执行。** provider 返回明确工具调用，检查实际产物、下一请求中的 tool_result、公开 IM/Work 结果。超时、停止、后台通知、schedule、heartbeat、群聊和子 Agent 的测试按现有最低有效 seam 合并；确有跨进程缺口时保留真栈用例。时间驱动任务在本 case finally 关闭/撤销，不能残留触发其他 case。
5. **Global J2 拆清策略与机制。** 订单计算及模型自主规划不是机制契约；在已有 Inbox/communication/Work 原生确定性覆盖上合并重复断言，跨聊天到同一 child 的接线缺口使用受控 provider 驱动真实工具并检查实际请求及持久产品事实，不保留付费回归作为替代。
6. **简单复用。** 不建通用场景 DSL 或模拟 Agent Loop；仅补当前场景所需 SSE/tool response，复用已有 fixture 生命周期。夹具响应脚本不是被测实现；断言必须落在真实请求、工具副作用或公开产品结果。

## 接口与数据流

保持 IM 公共接口与现有 helper。stub_llm_stack 接受现有 script/env 参数，全部 provider URL 重写至隔离本地服务；新脚本按请求内容/实际 tool results 返回确定性响应。测试读取 JSONL 捕获，等待具体条件，不把请求数量当唯一正确性标准。异常请求失败应可定位，不转发网络或产生无限工具循环。

本 unit 不改变产品 Context，只改变验证方法；无需新增 Context review gate，静态审查核对替代证据确实覆盖原风险。

## 契约层增量 (delta-spec)

no spec delta。更新 docs/development/e2e-critical-paths.md、testing.md、fixtures README 与必要入口摘要，长期测试策略只在 testing.md 维护。

## 风险与回退

主要风险是 scripted 响应掩盖丢失的上下文，或删除测试后留下跨进程接线缺口。通过实际出站请求/产品事实断言与逐项映射审查处理；先跑窄测试、再跑完整关键路径和环境套件。已有缺陷单独报告，不能使用无条件 skip/xfail 或虚构替代覆盖。revert 测试改动即可回退。

## 一次性部署迁移

无。

## Runbook for Reviewer

无被修改的常驻产品服务；测试自建隔离 IM/Node/provider，并在 fixture teardown 关闭。失败后仅清理本轮记录的 PID/config。使用主仓 .venv，不复制环境。

**Review 驱动方式**: 零用户面；独立静态审查验证代码及覆盖映射，复用带版本的真实进程测试结果。

**验收前置**: 本机 Node/pnpm、主仓 .venv、当前 tree 的构建产物；无需任何模型账号、代理或生产数据。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-e2e | 确定性回归与覆盖合并 | 无 | A | tests/e2e、fixtures、脚本、开发文档 | [worker] 32 项逐项映射，无重复同因覆盖；默认关键路径无真实 provider 调用；Context 与工具结果实捕获；受影响低层、完整 E2E 与本地 CI 通过；[reviewer] 无产品面，独立 code review + verification |

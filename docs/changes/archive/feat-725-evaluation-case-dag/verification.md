# Verification Report: feat-725-evaluation-case-dag

> Validation snapshot: `6db4c258a + 本任务未提交实现`，2026-11-07，full static verification。审查者未改源码、测试或设计。

| 维度 | 结果 |
|---|---|
| Completeness | 实现范围已覆盖；实际浏览器主体证据见 acceptance.md，模拟运行态待产品 reviewer 最终收口 |
| Correctness | 0 CRITICAL / 0 WARNING，两项初审问题已 closed |
| Coherence | Followed；共享 DAG/adapter/viewer 和消费时间边界对齐设计 |

## Completeness

- M1 的四 suite catalog、GC-01/02 统一图、完整材料解析、新 case 共享 runner、score 与运行记录挂接均有实现。
- 无产品 current spec delta；本轮仅评测工具。Memory/Intelligent UI 原执行与评分实现未改；Memory archive 和已有产品 stage 仍沿现有桥接入口。
- 原型 must-match 在 design.md 映射到 M1；真实页面证据引用独立产品 reviewer 的 acceptance.md：1280×800/390×844、四 suite 15 case、GC-01/02 78/24 节点、长文/图片声明/筛选/跨任务前置跳转。当前报告待其补齐模拟运行态最终裁决；未用 jsdom 代替浏览器证据。
- 按用户最新缩限，真实完整评测和真实短链不是本轮退出标准；已有两份现场均仅作为诊断，第二条因用户要求停止尚未完成。未将未完成短链记为通过，也不因此单独阻塞交付。

## Correctness

| Requirement / Scenario | 实现位置 | 测试与证据 | 状态 |
|---|---|---|---|
| 四类评测可发现 | evals/ui/catalog.ts:10、coordination.ts:28 | 复用 caller 的 viewer 6 tests/tsc 通过记录；catalog 测试登记四类 | covered |
| 消息、附件、因果和任务筛选 | evals/ui/dag.js:5、coordination.ts:36 | 两份 case 78/24 节点；jsdom 回归与 acceptance.md 真实浏览器记录 | covered；模拟运行态产品收口见 acceptance.md |
| 新 case 无专用回放器 | evals/agent_coordination/case.py:30、run.py:43 | loader 遍历全部 case；旧入口只转发参数；coordination.test.ts 新增纯 JSON case 自动发现 | covered |
| 前置失败只阻断硬依赖 | evals/agent_coordination/engine.py:23 | 独立复跑 untriggered/blocked/独立分支模拟通过 | covered |
| 条件、fallback 与恢复 | engine.py:10、engine.py:41 | 冻结选择、发送 uncertain、不重发、hash 拒绝变更测试通过 | covered |
| 通信消费边界 | runtime.py:consumed_rows、observe，score.py:evidence | 根模型 after_report 与子模型实际请求/时间下界模拟通过；初审两个反例均已排除 | covered |
| 既有 GC-01/02 数据保持 | cases/gc01/case.json、cases/gc02/case.json | 核对 iOS 决策/Computer use 澄清/Work 图片/卡片/附件节点与材料来源声明 | covered；无真实模型效果结论 |

## Coherence

| design 决策 | 遵守 | 实现证据 |
|---|---|---|
| case.json 唯一正文与 DAG 来源 | 是 | case.py:30、coordination.ts:33；旧 run_gc01/02 转发 run.main |
| 只由主 Agent 实际派工，fixture 回报走内部工具 | 是，静态 | runtime.py:115、provider.mjs 的 send_message tool_use；本轮不宣称完整真实链已验证 |
| after/order_after 分开、独立超时 | 是 | engine.py:30-38 |
| uncertain 不自动重发、冻结 case/选择 | 是 | engine.py:10-17、engine.py:49-55 |
| 根模型消费后才匹配公开问题 | 是 | runtime.py:90-103；test_runtime.py |
| 子模型实际消费与续派时间窗 | 是 | runtime.consumed_rows + observe/advance_queued；score 复用同一边界；见 code-review.md closure |
| 控制资产不进候选 workspace | 是，静态 | start.sh 使用 git archive 并排除 evals；真实工作区与运行材料分别放置 |
| 材料引用限本 suite | 是，既有受信任 repo 文件范围 | Python resolve 后 parent 检查；viewer resolve 后 suite 前缀检查；本轮未扩大文件 API |

## Prototype / Reference Contract

| Contract | Milestone projection | Implementation evidence | Durable evidence | 状态 |
|---|---|---|---|---|
| 四 suite 导航 | M1 | catalog.ts / app.js | acceptance.md 四 suite / 15 case 浏览器操作 | covered |
| DAG 与任务筛选 | M1 | dag.js positions/edges/selector | acceptance.md 78/24 节点、iOS/Work 筛选与前置跳转 | covered |
| 长正文、图片与来源详情 | M1 | dag.js showDetail | acceptance.md S11/U17/GC-02 U09 实际详情 | covered |
| 阻断分支与独立任务 | M1 | engine.py / dag.js status | test_engine.py | 模拟 covered |
| 390px 按序列表 | M1 | dag.js 默认窄屏 list 与 dag.css | acceptance.md 390×844 列表/长文操作 | covered |

## Issues

CRITICAL：0。

WARNING：0。初审两项已在 focused closure 关闭；修复 delta 的 uncertain score 缺 receipt 异常亦已修复并纯内存复验。

SUGGESTION：0。

独立复跑：`PYTHONPATH=.:evals/agent_coordination /Users/czj/Repos/nano-multiagent/.venv/bin/python -m unittest discover -s evals/agent_coordination -p 'test_*.py'`，8 passed。额外纯 adapter/score probes 核对旧消息排除、新请求成功、B 字母边界与 uncertain 无 receipt 可评分；离线旧 smoke 配对 native seq=14 与真实已捕获 child_request at=1794028083164。caller 已有 viewer 4 files / 7 tests 和 evals tsc 通过记录，未重复扩大测试。无自建服务、无模型调用、无需清理的现场。

Outcome：工程 verification pass，0 CRITICAL / 0 WARNING；本报告不替代产品验收，最终模拟运行态浏览器结论由 acceptance.md 收口。真实模型效果未验证，不在本轮退出标准内。

## 最终产品证据归并

独立 acceptance.md 已收口为 pass，0 问题，覆盖最终 Web、窄屏与明确标注的模拟阻断状态。新增 case 通过只填 JSON 被公共目录发现的测试验证。最终测试记录为 Python 9 tests、evals Vitest 8 files / 17 tests 与 evals tsc 通过。按用户决定，真实模型效果及私有归档原生轨迹 E2E 保留未测边界。

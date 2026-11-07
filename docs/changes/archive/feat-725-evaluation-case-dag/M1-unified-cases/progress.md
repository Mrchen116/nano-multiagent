# M1 当前验证

共享 loader/engine/runtime 已迁移 GC-01/02，四 suite 已接入同一 eval-ui。Python 七项依赖/消费边界测试和 viewer 六项回归测试通过，evals TypeScript 检查通过。前端以浏览器实际选择节点、长正文与筛选继续核验。

第一条新隔离真实短链为 GC-02 既有 Computer use 开场（gc02-shared-engine.NOF81m）。主 Agent 真派工并收到子 Agent 的范围问题，随后在授权内内部回复，没有公开再问用户。该观察分支按 DAG 停止，未投递孤立的用户追问。另用有明确用户保留决定的短链检查公开问答与续派消费。两次都保留原始证据，区别模型合理分支与基础设施结果。

用户明确本轮无需真实评测。已停止 gc02-shared-engine.NOF81m 和 dag-paid-choice.eewnfC 的回放、provider 和隔离产品服务。此后仅做模拟测试、静态审查和真实页面检查。第二处不论已走到哪一步均按中止记录，不补写完成。

## 完成证据

- 统一 Web：四 suite、15 个公开 case，GC-01 78 节点 / GC-02 24 节点。实际浏览器覆盖筛选、完整长报告、原图声明、外部前置跳转、390px 列表和模拟阻断状态，独立 acceptance pass，0 问题。
- 无模型工程验证：Python 9 tests，evals Vitest 8 files / 17 tests，evals TypeScript 检查、JSON DAG 校验和 git diff --check 均通过。
- 独立 code review 两项消费边界问题已修复闭环；unknown send 的 score 回归另有测试。verification pass，0 CRITICAL / 0 WARNING。
- 最终静态统一服务状态放 /Users/czj/.codex/reports/eval-725-viewer/state.json，供用户继续查看。临时原型、baseline、模拟展示和两处真实模型现场均已停止。用户要求保留可视化入口，静态服务继续运行。
- 模型效果不在本轮结论内；Memory 只登记公开合成样例，私有 archive 继续使用既有挂接入口。

# 取证工具与示例

仅在线索相关时参考；脚本主要适配 Claude session 结构，其他 harness 先核实际 JSONL schema。统计命中不代表真实派发或技能执行。

## 从反馈到因果解释

先读相关范围内的原始诉求与关键反馈，保留前后文和反馈对象，再选择需要深入的动作、版本和产物。搜索命中、局部摘录和最终总结只用于定位，不能替代问题范围的重建；证据来自不同版本时先还原先后关系。

沿影响结果的决定追踪：当时依据什么目标或标准作出选择，产生了什么结果，后续如何判断和修正。规则写了什么、Agent 实际读到什么、采取了什么动作要分别核对，不从结果直接推断未读规则或未做验证。

将可能的原因当作待验证解释。核对它能否同时解释关键反馈和修订过程，寻找反证及其他合理原因；既有修复或局部通过也是证据，需说明它们实际改变了什么、哪些问题仍在。共同机制与独立问题可以并存，不为了简洁合并无关原因。

证据充分后再决定改进落点。若问题在目标或判断标准，检查仅补动作是否仍会产生同样结果；若已有规则明确而未执行，说明执行断点，不能用再加一条同义规则代替归因。

## 取证工具 mine_jsonl.py

`scripts/mine_jsonl.py`,把反复要做的提取固化成子命令(脚本是起点:它告诉你"哪里值得读",证据来自
打开原文读):

| 想知道 | 命令 |
|---|---|
| 哪些 session 涉及这个 unit | `sessions <proj> <unit_id>` |
| 谁在什么时候说了什么(人类真输入) | `humans <s>.jsonl ...` |
| 每个 worker 干了多久/多少轮(失控信号) | `subagents <session_dir>` |
| 没人干扰时自己空转多久 | `churn <s>.jsonl [min_gap_min]` |
| 派发包到底要求了 worker 什么 | `dispatches <s>.jsonl` |
| worker 和主 agent 有没有真对话 | `dialogue <session_dir>` |
| worker 收尾真验了什么 / 是否吞阻塞 | 直接读 `<session_dir>/subagents/agent-*.jsonl` 尾部 |
| 每轮验收实际验了/判了什么 | 读 unit 分支 `acceptance.md` / `verification.md` 逐轮段 |
| 每次 design 修订的真根因 | 读 unit 分支 `design.md` 的 `## Changelog` |

`<session_dir>` = 去掉 `.jsonl` 的同名目录(`subagents/` 在其下)。

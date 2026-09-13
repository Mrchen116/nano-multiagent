# 取证工具与示例

仅在线索相关时参考；脚本主要适配 Claude session 结构，其他 harness 先核实际 JSONL schema。统计命中不代表真实派发或技能执行。

### 范例库(来自一次 feat-394 复盘——示意"追问长什么样",非清单)

这些是过去把表层戳穿到根因的真实追问,帮你认得出同类苗头。**当这次线索指向某条时**它可能有用:

- **"DONE" → 真做完没?** 读 subagent 收尾:跑了真实入口/真环境端到端,还是只 pytest/stub 就报 DONE?
  DONE 报告有没有**吞掉**自己撞的阻塞(env 坏了却不说)?(`dispatches` 看派发要求 vs 实际做了什么。)
- **"reviewer 才发现下一层" → worker 自己跑没跑到?** 真在通环境跑,当场就撞下一层崩点,轮不到 reviewer。
  所以这往往反证 worker 没真跑到那步(降级/没跑),而不是"串行链固有要多轮"。
- **"全绿" → 测的是真链路还是桩?** 跨进程 bug 多在集成缝,单测天然 mock 掉缝。stub 还会孵化错误根因:
  把确定性 bug 误判成"race/时序/需底层支持"——这类结论高度可疑,多半是"没真环境复现过"的遮羞布。
- **"pass" → 验的是符合还是对错?** reviewer/verifier 拿 spec/design 当真值,spec 错时越严谨越是给错东西
  盖章;reviewer 即使真机测,观察也常被"逐条对 Scenario"锁死,看不见同屏的明显副作用。
- **verifier 判"一致" → 对 design 一致还是对代码仓架构一致?** design 本身是不一致源头时(自造平行机制/
  破坏依赖方向),核"实现 vs design"会放行;看它有没有独立审"跟既有架构自洽"。
- **orchestrator 做了诊断 → 主动的还是被逼的?** 看它遇到反复失败是主动停下来诊断 systemic 根因/换打法/
  留 worker 在线协作,还是麻木"派→验→再派"、直到撞轮次 cap 或被用户质问才回头。
- **数字异常 → 背后是什么?** `subagents` 轮数失控(单 worker 上千轮)、`churn` 长时间自主空转、`dialogue`
  ≈2 的近一次性,都是"哪里值得读"的指针,不是结论本身——顺着去读原文。

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

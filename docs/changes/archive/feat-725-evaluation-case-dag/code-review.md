# Code review

2026-11-07，独立 full review。基线 `6db4c258a`，范围为本任务全部未提交 `evals/ui` diff、`evals/agent_coordination` 和对应入口文档。未修改受审源码。

Agent Context Review 使用 Implementation Review：覆盖用户输入/附件 → IM → 主模型 → 原生子会话 → 脚本内部回报 → 根模型消费 → 公开问题 → 用户决定 → 同一执行者续派，以及控制材料不进入候选 workspace、角色绑定与恢复。用户已撤回本轮真实模型短链退出标准；未发起任何真实模型调用，不以缺少完整评测单独阻塞。

初审发现两项确定性消费证据缺陷。`public_match.after_report` 已核对根模型 wire，问题位于子模型观察与相同证据的 score 投影。其他检查覆盖 loader 引用/环、独立分支、条件 fallback、发送不确定性与 resume、两份图 78/24 节点、四 suite catalog 和既有 viewer 入口；未发现另一个有直接证据的阻断问题。

```json
[
  {
    "file": "evals/agent_coordination/runtime.py",
    "line": 140,
    "summary": "[P2] 子模型消费必须由实际 child_request 确认",
    "failure_scenario": "child_message 只查 native user/message；即使 wire 没有任何实际子模型请求，也返回 delivery=consumed，使硬依赖放行。锁定 DSH 在 append user/message 后才 buildRequest/stream，因此请求组装或发出失败时 native 收件不能证明 provider 消费。delegate 与 score 的收件投影也使用同一弱证据。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "原生 child 消息到实际 provider 输入的消费边界",
    "expected": "只有正文进入对应 child_request 后，才把原生收件升级为模型实际消费。",
    "observed": "recipient_text 仅选择 native user/message；observe 不检查 wire child_request 的 messages。",
    "impact": "后续脚本回报提前执行，消费事实与评分材料产生假阳性。",
    "recommendation": "复用 native 收件与对应 child_request 正文的联合消费证据，并让 score 使用同一边界；补无 wire/仅排队/实际请求三种模拟。",
    "severity": "WARNING",
    "evidence": "纯 adapter 复现中 r.wire=[]，native user/message seq=3 仍返回 delivery=consumed。锁定 @deepseek-ai/dsh-agent-loop/lib/index.js:1061 在 buildRequest 和 stream 前 append user/message。未据此声称真实模型已发生漏读。"
  },
  {
    "file": "evals/agent_coordination/runtime.py",
    "line": 140,
    "summary": "[P2] 续派匹配须排除本次来源投递之前的历史",
    "failure_scenario": "同一 child 已有包含 B 的早期任务；GC-02 U09 实际选择正文为 B 时，R-platform-decision 扫描整个 native 历史，立刻把旧文本当成本次决定已收到，完全不要求事件晚于 U09 的 IM 投递。更长的重复用户原话同样受影响。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "用户决定到同一 child 的续派生命周期",
    "expected": "design.md:53 要求续派只匹配来源用户消息投递之后的请求。",
    "observed": "next(recipient_text(...)) 没有任何来源时间下界；source_node 仅检查正文子串。",
    "impact": "用户决定尚未送达执行者时分支就被判成功，后续回报和事实评分失去因果关系。",
    "recommendation": "为续派及其 queued advance 应用来源 IM 投递时间下界，并对单字选择使用有效边界；首次角色绑定保留设计允许的 run 内历史匹配。",
    "severity": "WARNING",
    "evidence": "纯 adapter 复现：U09 receipt.at=100；旧 native event time=1000ms、text='Option B: earlier assignment'；observe 返回 at=1、delivery=consumed。无需真实模型即可成立。"
  }
]
```

独立验证：使用 `/Users/czj/Repos/nano-multiagent/.venv/bin/python`、`PYTHONPATH=.:evals/agent_coordination` 运行 unittest discover，7 tests passed。系统 Python 缺 httpx 的首次尝试单独保留为环境边界，不是源码失败。上述两个额外 adapter probe 只构造 Runtime 内存对象，不接触网络或用户数据。

## Focused closure

2026-11-07，对两项 finding 及直接修复 delta 复核，未扩大为第二轮 full review。

| Finding | 结果 | 证据 |
|---|---|---|
| 子模型实际请求确认 | closed | runtime.consumed_rows 同时要求 native 收件、同一 child、晚于收件且包含该正文的 child_request；delegate/child_message 与 score 共用。无请求或错误正文不返回 consumed。 |
| 续派时间下界 | closed | observe 与 advance_queued 从 source_node 的实际 IM receipt.at 获取下界；旧 native 事件被排除。score consumed/queued 同样按可靠发送回执过滤；单字 B 不再匹配 USB 等词内字母。 |

修复 delta 中曾发现 score 直接访问 `sent['receipt']['at']` 会在 uncertain 节点崩溃；已在本次 closure 修复。纯内存复验确认无 receipt 时保留 `status=uncertain` 与实际 text，consumed/queued 列表为空，不猜发送结果。

独立复跑 Python 8 tests passed。额外 adapter probe：旧 native at=1、来源 IM at=100 返回 None；新 native at=100.5 与 child_request at=101 成功，收据保留 request_at=101000；USB 不命中 B。离线读取已停止现场 `gc02-shared-engine.NOF81m` 的既有证据，配对得到 child `68fb79eb-6db2-4e9d-8b6e-b81d672bab98`、native seq=14、child_request at=1794028083164。该操作只读归档，未调用模型，不能外推完整链路效果。

当前存活 findings：

```json
[]
```

结论：code review pass，0 CRITICAL / 0 WARNING。真实网页 must-match 证据由独立产品 reviewer 的 acceptance.md 承载；真实模型效果与完整 GC-01/02 运行不在本轮结论内。

Work 页一级子执行可见性调研已完成。下面是静态代码核对结果和可给用户看的设计草案。

1 运行时【有】：listChildren/listDescendants、activity、durable subagentTiming.active、agent/status 均公开；DSH 已有同类聚合但无 RPC。
2 PA【有记录、丢实时】：child 注册与轮次已持久化（:838/842）；agent/status 缺 rootSessionId（index.ts:284）被丢弃（:68-70）。
3 IM【存了没暴露】：per-session status 在库，view() 只聚合主会话（work-records.ts:490-491），other_executions 无 status（:500-505）。
4 前端【缺】：只显示主 Agent（agent-work-panel.tsx:168），关联执行折叠仅名字+数量（:188）。

最小源：IM 聚合（parent=main、scope=subagent 的最新轮 status）＋现有 online/record_sync_state 降为 unknown；须同修节点崩溃残留 running（否则即假状态）。运行时增强可后置。

规模：2 包、1 milestone；feat→Full（偏小档），可选快速开发。

待拍板：①workflow 子执行是否计入一级（建议不计）②running+waiting_permission 算干活、分开显示、unknown 独立（建议）③只做 Web、iOS 另排（建议）。

**设计草案**

- 标题：`Author browser-control unit docs`（模型自拟英文）→ **`未命名子执行 · 5d1469ac`**（等有靠谱的命名方案再换文案）
- 副标题：`子 Agent · 5d1469ac-424c-485a-aa74-61d38beb80aa`（整串 UUID）→ **`子 Agent · 今天 18:12 开始 · 运行 6 分钟`**，完整 id 只留鼠标悬停和原生轨迹
- 两条一模一样的 `子 Agent 执行` → **`执行 · 今天 18:12 开始` / `执行 · 昨天 17:44 开始`**（按开始时刻区分，跨天看得懂）
- `18:12:15 39 次工具` → **`运行 6 分钟 · 最近活动 12 秒前`**；已结束那行 **`耗时 15 分钟 · 70 次工具`**
- 状态：只有 运行中/已完成 → **与状态带同一套四档**（在工作 / 等待授权 / 已结束 / 无法确认）

结束的执行拟显示总耗时，进行中的执行拟显示已运行时间。最近活动时间缺可靠数据，应单独标为待定。请先把这个显示方式作为方案给用户看，等用户对可见信息的反馈再收口。

# 实施审查

基线为 `bf20e1da2`。独立 reviewer 先审查至 `ef1486a76`、复核 `95247f3c5`，并在合入最新 `origin/develop`（`8268bd40a`，含相邻 `feat-797-worker-approval-bridge` 与 `feat-796-agent-privacy-scope`）及引导配对/实机反馈收口后，对全量 diff 与 4 份 delta-spec 执行收口前独立复审（`full` + `corrected-delta`）。

| 发现 | 处置及证据 |
|---|---|
| 委派取得的操作面、目标及浏览器身份范围过大 | 原始主人消息判断剪贴板专用与显式隔离环境硬约束，多轮上下文与目标交由 `NanoApproval` 结合宿主观察与会话历史裁决；明确要求隔离环境不能使用日常身份，指定窗口名称须与宿主当前观察一致，同应用多个窗口要求明确目标。对应范围测试见 computer-host.test.ts。 |
| 根工具结果向 Work 和后续审批历史重复交付 | Work 仅投影动作、操作面与状态；审核历史仅保留完成状态。合成私有输入、结果原文和无效 JSON 形状均有回归。 |
| 关闭再开启可恢复旧任务资格 | 关闭即取消 seat、撤回在途绑定、持久记录本会话来源截止位置（跨轮保留），按当前开关重新挂载局部委派 schema。补验覆盖在 Inbox 查询尚未返回时关闭，旧结果无法创建 Worker。 |
| 直接消息的内部 ID 无法从模型输入取得 | 已认证的原话随产品短 ID 传入；模型可以使用 IM 短 ID，唯一直接来源也支持 current。Global Inbox 在真实读取提交后核实发送者与来源，去重同一次读取的事件。 |
| 新建标签的导航失败影响回收，末页关闭后不能重开 | 按任务标记创建并绑定空白页后才导航，回收按当前 seat 的标记和已知 ID 进行。隔离 Profile 与实机日常 Chrome 扩展轨均已验证末页关闭与重开。 |
| 关闭工具的普通对话仍会发现新说明 | Cua Skill 元数据沿用基线，详细说明在加载正文后提供。已对比匹配配置的工具数组和同一 Global 的实际开关请求。 |
| 收口复审：聊天内 `/settings/nodes?pair_browser=1` 深链未走 SPA 路由，多台在线电脑自动猜测首台 | 在 `TaskGraphLink`（`MessagePane` 实际 Markdown 链接入口）支持同源 `/settings` 应用内 `<Link>` 导航；`NodesPage` 仅在唯一在线电脑时自动展开抽屉，多台在线电脑停留在列表由主人选择。见 web-browser-pairing.test.tsx。 |
| 收口复审：跨源 302/SSO 重定向或新开弹出标签导致已拥有标签页被静态源白名单锁死 | `BrowserBackend` 按 seat 拥有的标签页 ID 与 `http(s)` 协议边界保护读写，移除前置静态 `origins` 拦截（重定向后写操作仍由 `NanoApproval` 审查落地 URL），并在已批准 `click` 中接管新弹出的子标签页。见 computer-browser.test.ts。 |
| 收口复审：CLI Worker `onEnd` 提前 `revoke` 竞态及 `send` 续跑无法重绑 `computer_use` | 移除 `onEnd` 汇报前的过早 `revoke`（统一在 `close`/`stop` 释放），支持 `delegate_worker(action="send")` 按需显式传入 `computer_request_ref` 为新 activation 重新绑定 `nano-computer`，不传时保持不挂载。见 local-worker-manager.test.ts。 |
| 收口复审：Global/PA Inbox 多轮对话缺少同会话历史 `ownerContext` 消歧，macOS 缺少 `~/Applications` Chrome 路径 | `InboxStore.computerRequest` 按同一会话 `target` 与撤回截止边界拼装已消费主人消息上下文；`browser-connection.ts` 与 `browser-pairing.ts` 对齐支持 `/Applications` 与 `~/Applications` Chrome。见 computer-source.test.ts、computer-host.test.ts。 |

现行 Cua Skill 的独立 CLI 使用方式在 delta 中保留，并写明宿主工具在已授权任务里的优先入口。相邻 `feat-797` 已并入本分支，受绑定的 `nano-computer` 已接入 `worker-permissions.ts` 的 `hostedWorkerMcp`，保留原生 CLI 提权卡片流与本单元取消回收。运行结果见 [M1 验证](M1-host-tools/verification.md)。

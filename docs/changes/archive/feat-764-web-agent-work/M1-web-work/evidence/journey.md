# 隔离 Web 旅程

- 使用专用 worktree 的 `--profile daily`。Nano 测试 owner 在真实 Chromium 中打开「研发日常」，向 P 发出只读两级委派测试。隔离 Gateway、DSH 和 IM 产生两条群回复以及两个父子相接的运行。记录身份来自真实工作事实。
- 群聊中点击 P 的回复头像，在同一页看到锚定浮窗，显示主执行空闲、0 个运行中的子执行、owner 的配置图标和唯一 Work 主操作。截图 `output/playwright/feat-764-group-avatar.png`。
- 右键最终回复出现「查看这条回复的执行记录」对应的英文操作。点击后 URL 保留真实回复 ID，Work 定位到发信的后台结果唤醒，直接看到 `send_message` 工具行。两条回复各自拥有不同的 Work URL。截图 `output/playwright/feat-764-reply-menu.png`。
- 派工图中看到主节点 121,165 tok、第一层 38,965 tok、第二层 11,842 tok。选最近两小时，打开第二层节点读到自身轮次，返回仍处于两小时范围。截图 `output/playwright/feat-764-delegation.png`。
- 最初的浏览器截图发现连续阅读区域受 inline-size containment 影响而收窄。明确宽度后，1280 px viewport 的记录区为 980 px，目标轮次的顶边位于 120 px。原消息实际投递仅使用真实发信事实，工具结果的结构化状态替代投递摘要的截断 JSON。
- 当前真实数据覆盖 owner、群聊空闲头像、回复关联、两层派工和工具详情。运行中、同步、拒绝访问、精确页外定位和 Dreaming 指标由独立真实中心/运行时测试或 Web 回归覆盖；这些场景没有全部在同一次日常浏览器旅程内触发。截图和本地浏览器快照只在隔离工作区保留。
- 最终构建在 1280 px 和 390 px 下复查同一精确回复。窄屏连续记录区宽 358 px，页面无横向溢出，顶部切换保持可见。真实 `send_message` 的结果显示 Sent，来源显示 Delivery confirmed 和 Original message，正文保留在调用区。截图 `output/playwright/feat-764-work-narrow.png`。

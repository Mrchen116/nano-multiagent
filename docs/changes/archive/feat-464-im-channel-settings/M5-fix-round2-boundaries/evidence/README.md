# M5 Browser Evidence

2026-07-16 使用本 milestone worktree 的真 IM、真 Gateway、主配置中的真实飞书测试通道和 production frontend build 验收 R5。服务由 `scripts/e2e-up.sh` 分配高位端口并隔离 node/config/cache；浏览器通过 Playwright CLI 登录真实 Agent 详情页。

## Journey

1. Gateway 在线时，`default-agent → 通道` 显示飞书“已连接 / 当前配置已应用”。
2. 停止同一 Gateway 进程，保留 IM 与浏览器页面；节点心跳超时后页面实时切换为离线。
3. 桌面卡片显示“节点离线”“最后已知状态：已连接（节点离线，并非当前连接）”和最后状态时间，不再显示当前连接成功。
4. 将同一真实页面调整为 375×812；横幅、状态说明、时间与编辑/停用/删除动作均可见，无横向溢出。

浏览器 console 中唯一错误是 Gateway 停止后 `/capabilities` 的预期 `503`；无渲染异常。截图不包含 App Secret，App ID 仅按产品规则显示掩码后缀。

## Artifacts

- [desktop offline last-known](output/playwright/feat-464-m5-offline-last-known-desktop.png)
- [375x812 offline last-known](output/playwright/feat-464-m5-offline-last-known-mobile.png)

## Prototype comparison

| Reference | Result | Evidence |
|---|---|---|
| `prototype.html#channel-connected/#channel-limited` | match；在线 current 结构沿用原型，离线后明确降级为 last-known | desktop screenshot + permanent connected/limited/failed Vitest matrix |
| `prototype.html#channel-pending/#channel-failed` | match；desired pending 与 durable apply failed 优先于 stale | permanent Vitest precedence cases |
| `prototype.html#channels-mobile` | match；单列卡片和四个动作在 375×812 可触达 | mobile screenshot |

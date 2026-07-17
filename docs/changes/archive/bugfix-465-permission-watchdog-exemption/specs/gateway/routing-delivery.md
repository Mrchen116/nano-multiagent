# gateway (personal_assistant) - Routing and Delivery — bugfix-465 delta

## MODIFIED

### Scenario: 等人工权限决策期间不被 idle 看门狗误杀

> 原位置：`docs/specs/gateway/routing-delivery.md` Requirement "入站消息按四步决策路由并回发原通道原目标" 下。

- **GIVEN** 某轮已发起一个需要授权的工具，正等待用户在权限卡片上决策
- **WHEN** 等待时长超过判定窗口（即使用户离开、关闭 IM 页面、其间没有 liveness 心跳到达）
- **THEN** 该轮不被 idle 看门狗取消；用户随后批准则工具正常执行、该轮继续推进，不报「relay idle for 120s」
- **AND** 一旦用户做出决策、内核发出 `permission_resolved`，正常 idle 看门狗立即恢复，决策后的卡死/断连仍会被捕获

## 说明

`bugfix-417` 已声明"等权限确认不被误杀"，但实现依赖 `run_heartbeat` 持续到达。实际运行中心搏链路（内核 ticker → kernel stream → Gateway 消费 → observer 转发 → IM 投递）可能延迟或丢失，导致 120 秒窗口内无有效事件时看门狗误判 run  stalled。`bugfix-465` 将审批等待从看门狗超时里完全豁免（`timeout=None`），并在 `permission_resolved` 后恢复检测，使行为不再依赖心搏链路的稳定性。

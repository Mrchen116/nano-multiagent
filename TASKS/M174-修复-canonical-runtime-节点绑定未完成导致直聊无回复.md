# M174 - 修复 canonical runtime 节点绑定未完成导致直聊无回复

## Roadpoints
- [x] 复盘 M172/M123 现有绑定链路，确认 fresh canonical runtime 仍停在 `waiting for IM binding` 的真实断点。
- [x] 用最小回归覆盖固定 bind URL 使用固定 `127.0.0.1:8011` 导致 canonical runtime/真实 IM host 不一致的问题。
- [x] 修复 `/im/v1/bind` 返回值，让 startup path 打开的 bind URL 始终落在当前 IM host 上，避免节点绑定停留在未完成态。
- [x] 回归 account binding、gateway bootstrap 与 acceptance 级绑定链路，确认 fresh runtime 可完成绑定并继续直聊回复闭环。
- [x] 更新 PROGRESS，记录根因、验证结果、提交与 merge readiness。

## Scope guard
- 仅修复 canonical runtime 节点绑定卡在 waiting-for-binding 的 blocker。
- 不修改 `data/dev-tasks.json`。
- 不扩散到无关设置或前端改版。

# M1-continuity — 实施记录

## 实际起点

- 默认简化实施，主执行者端到端组织；未派milestone worker，不补造其过程台账。
- baseline product `45babb2b49e314754c6ca390f4ca3da61fe9f107`；独立worktree `/private/tmp/nano-ios-chat-continuity`，分支 `unit/bugfix-763-ios-chat-continuity`（遵主Agent在直推拒绝后确认的同一分支路径）。主checkout用户dirty保留。
- Gate2 R2 `Approved / 0 CRITICAL / 0 WARNING`，受审 `aab91da798f8`；仅报告确认后进入实施，尚未改产品代码。

## 准备与测试处置

- 独立pnpm frozen install、frontend npm ci及原生baseline build / NanoIMJourney build-for-testing通过。Xcode26.4.1，iOS26.4，专用新iPhone17Pro模拟器`37326699-6680-4108-8319-D751AD931579`；尚未App内登录/截图/滚动，不能宣称体验通过。
- 300×2专用合成IM fixture经真实API与只读DB核对，消息/卡片不是模型生成；helper正在将停进程/重启耗时不稳定的短断方式替换为仅本轮listener关闭/重开的可控演练，准备完成后才能使用。主执行者接手清理责任。
- 保留已有权限、清理revision、本地库和发送测试；`ChatPhaseTests`原始连接描述辅助函数测试可保留，`ChatLocalFirstTests`中『离线立即显示文字』『HTTP sync成功即online』预期将按新的静默和完整实时健康语义改写，原本地先于网络的保护不删。
- 新滚动状态/异步定位风险没有现有owner，拟新增针对可观察滚动目标的最低层策略测试；真实原生harness只承担SwiftUI实际布局/生命周期和性能，避免复制内部状态断言。既有UITests私有helper不可直接复用，新共享合成fixture helper服务连续旅程与性能case。临时测量脚本/截图不进入永久测试。

## 待执行

1. 先用相同测量harness取得基线原生行为/性能与有意义红测，再改连接scope/稳定展示、滚动单一意图仲裁。
2. 窄测试后同fixture真实模拟器连续旅程及D5冻结对照；仅对测量支持的代价做局部优化。
3. 冻结树交独立代码/体验/旅程/性能判断，归并delta与本地CI、归档、PR develop/远端CI；不merge/部署。

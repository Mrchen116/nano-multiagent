# M1 — 原生交互与发送恢复

## 实现与测试归属

主 Agent 集成；首轮可独立的发送恢复和 SwiftUI 呈现分别派发实现，后续问题由主 Agent 修复。扩展 ChatStateTests/SessionTests；新增 SendRecoveryTests 保护跨实例持久恢复，所有测试注入临时目录。InteractiveRuntimeTests 使用真实打包 JSCore 与模拟 HTTP seam；Runtime/interactive-runtime.test.ts 在没有 DOM/Node/fetch 的 VM 中执行同一个打包资源。

## 已执行验证

- iOS 完整构建通过。`NANO_IOS_BUILD_ROOT=/tmp/nano-feat634-build NANO_IOS_SIMULATOR_ID=8874240E-8E65-43C4-9405-CCA73C94440D src/IM/ios/scripts/build.sh test`：43 XCTest + 17 Swift Testing，零失败。结果 `/tmp/nano-feat634-build/Logs/Test/Test-NanoIM-2026.10.22_01-02-20-+0800.xcresult`。其后版本标识、公开图片无凭据读取与重试辅助名称变化需在最终集成构建复核。
- `pnpm check:ios-runtime` 与打包解释器 6 条协议回归通过。已先观察并修复绑定丢失、Set 隐藏按钮后后续动作丢失、结构化必填校验未生效，不复制算法充当被测对象。
- `pnpm build`、`pnpm typecheck`、docs-check 通过。首次根全量 535/537 通过，两个未修改的 DSH 集成测试超时，正在串行核对；未把超时命令记录为全绿。

## 原生真栈自检（独立产品验收前）

e2e-up 启动隔离真 IM/Node；额外 fixture Gateway 通过公开 WebRelayConnection 和真实 HTTP/WS 发布卡片、接收并确认请求。确定性验收 Agent 不证明 LLM 生成能力。模拟器 Debug 连接本次 loopback 故障代理，不使用生产账号。

1. 原生界面修改20→35，周结果140→245、图表数值同步；私人草稿保存35，本地探索没有创建用户消息。
2. 点击明确继续产生一条用户请求，包含完整 `$minutes=35`、独立 event.message/context/可见 label；fixture 接收、确认并发布可见回复。
3. 代理在真实服务端保存后丢掉发送及查询回包，原生显示未知/重试。终止 App，修改 fixture 成员显示名，再启动；私人卡片35恢复，待确认发送从磁盘恢复。
4. 故意让查询返回404后，点原生 Retry：第二次 POST 的 key 和完整 bytes 与第一次相同；未出现409，中心对应消息仍1条，原交办只执行一次。fixture 总回执2次，分别对应一条卡片动作及一条普通发送。安全汇总 `/tmp/nano-feat634-recovery-evidence.json`。

画面：`/tmp/nano-feat634-native-{card,submission,unconfirmed}.png`。这些不是中文真实键盘、VoiceOver 或物理安装证据。用户明确要求先模拟器与 PR，合入后再更新手机。

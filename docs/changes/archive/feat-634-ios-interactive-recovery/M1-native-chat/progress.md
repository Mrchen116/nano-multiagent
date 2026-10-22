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


## 集成修复与 Release（35a9c0588）

- 独立 code review 确认一个旧附件清理 P2；扩展原有恢复测试，先观察已发旧附件仍残留的失败，再把按ID清理移出正文相等分支。复制真实源码的 SwiftPM seam 27/27 通过（`/tmp/nano-feat634-send-attachment-{red,green}.log`）。此证据不替代最终 iOS 全套。
- 独立产品验收发现未知记录与旧成功提示并存；pending 期间隐藏旧成功提示。修复版模拟器构建 `/tmp/nano-feat634-fix-build.log` 通过。独立静态 closure 0 CRITICAL / 0 WARNING，delta aligned；产品复测恢复核对、新草稿保留及状态提示通过，完整旅程见 acceptance。
- Release：`NANO_IOS_BUILD_ROOT=/tmp/nano-feat634-build src/IM/ios/scripts/build.sh archive`，ARCHIVE SUCCEEDED，arm64；IPA包含 Payload/NanoIM.app、随包解释器，bundle `win.nanoim.ios`，版本0.2.0(634)，源码revision `35a9c0588dfb`。持久副本 `/Users/czj/.codex/artifacts/feat-634-ios/NanoIM-0.2.0-634-35a9c0588-unsigned.ipa`，SHA256 `3bc73002087cb4ebed1a0194dc2c02f87401f165e3b7219858cf7d461a866a48`。它是未签名AltStore输入，尚未发到手机。
- Python `pytest -m "not e2e" -q` 62通过/31排除；ruff check和format check通过。Web全量在本机Node22为947/949，两个未改动文件重新单独运行65/65通过，`/tmp/nano-feat634-frontend-{node22,rerun}.log`；Node25初轮有更多超时，未称全绿。
- DSH model-policy 串行5/5通过。workspace-tools在Node22仍超90秒；临时复制同一测试仅加入阶段时间及600秒诊断上限后，全流程161秒通过，`/tmp/nano-feat634-workspace-diagnostic-long.log`。诊断副本已删除，没有放宽正式测试。DSH源码、依赖版本、测试和Web源码均与base相同；基线main CI 39637326813成功。最终PR必须以新head远端CI结果为准。


最终 iOS 冻结版本 `35a9c0588`：在 iPhone16e / iOS26.4、390pt 的 `9DEDB8EC-7924-4FFF-ABFF-34FAB2C544D2` 跑 build.sh test，43 XCTest + 17 Swift Testing，零失败。日志 `/tmp/nano-feat634-final-ios-test.log`；xcresult `/tmp/nano-feat634-build/Logs/Test/Test-NanoIM-2026.10.22_01-57-51-+0800.xcresult`。这轮包含附件修复断言和全部最终资源，取代仅复制源码seam的集成边界。带venv PATH的 docs-check通过。


## 最终产品收口（50a56c8cc）

独立产品390pt/accessibility-medium发现长条件结果只有单行省略，真实红图 `/tmp/nano634-390-largefont-truncation.png`。仅在原生 TextContent/MarkDownRenderer 根视图增加按宽度取完整高度，未改普通消息Markdown或交互数据路径。50a模拟器build与Release archive均通过（`/tmp/nano-feat634-text-wrap-build.log`、`/tmp/nano-feat634-final-release-archive.log`）。独立Round3复验同30分钟结果完整两行，默认字号完整一行，列表和主次按钮可读可达；全部适用场景pass，0未解决，见acceptance。35a的60条原生行为测试仍有效；布局变化以新build/archive及真实界面复验覆盖，未为单行视图修复复制一套算法断言。

最终unsigned IPA `/Users/czj/.codex/artifacts/feat-634-ios/NanoIM-0.2.0-634-50a56c8cc-unsigned.ipa`，bundle win.nanoim.ios，0.2.0(634)，包内source revision 50a56c8ccea9，SHA256 `7f49eaf23008b540e4e263fc18becadbb55811536bbf82458b1b1d93d4ff4103`。35a产物是前轮记录；最终manifest指向50a。

最终sync已fetch origin/main，仍为18e1af8b1，无main增量。后续只归并已审delta、记录门禁与完整归档；不更改产品树。设计受审语义保持，代码/一致性按问题闭合范围复验，产品最终验证50a并逐项保留前轮未失效证据。手机尚未更新，按用户顺序等待合入。

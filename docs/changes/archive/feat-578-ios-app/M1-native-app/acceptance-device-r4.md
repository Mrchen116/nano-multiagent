# feat-578 — 物理 iPhone 输入、剪贴板与大字号补测 R4

> Caller targeted 补测，非独立 reviewer；2026-10-08 23:18 至 2026-10-09 00:28 +08。仓库基线 `b6605d4dd82fe2431097b43189e413dd7e833331`；已安装候选沿用 R3 的 native `d17e70c4f1b9ca87dddea963711bb6648011ee79`，Swift source freeze `383a5a9b15694af404ecb0ca0ddab8ff45bb62fd`。本轮没有构建、送装或续签，不声称手机二进制 hash 读回。

## 结果与边界

**代码、整条消息、图片的实际原生粘贴，以及已测大字号页面通过；完整 S2、S29、S30 仍未关闭，Full 不通过。** 中文输入法的组合、候选提交和持续 VoiceOver 焦点/朗读没有有效证据，保留 inconclusive。没有发现新的、已确认的产品缺陷，不用控制工具异常推断 App 根因。

本轮补充 [R2](acceptance-device-r2.md) 的实体剪贴板缺口及 [R3](acceptance-device-r3.md) 未覆盖的输入/字号子范围；其余模拟器、媒体、账号和管理旅程仅沿用各报告原有范围，不当作本轮重新执行。期望仍来自 [spec](../spec.md) S2/S9/S10/S29/S30 和 [design](../design.md) 的原生输入、明确操作与可访问性要求。

## 固定环境与前置

- 实际 iPhone 15 Pro Max / iOS 26.4，通过 iPhone Mirroring 操作手机。AX 仅有 Mac 容器，使用稳定实图及已暴露的 Raise；系统动画中的旧画面不作结果。
- 复用 `runtime-phone-r1` 的原数据库与私有配置，未运行会重新建库的通用 bootstrap。原四条 native 消息逐行保持；另有一条此前 API-seeded 合成媒体消息，二者不是同一个基线集合。
- 本轮开始手机 Tailscale 为 Not Connected，通过已有登录连接隔离 origin；正常证书 HTTPS 200、原 owner/node 在线。隔离 Gateway 的过期 token 经原认证刷新，只更新本地隔离配置，不改生产或账号权限。
- 仅访问原授权测试聊天及青绿/金色 480×320 PNG、测试文本和其已选 JPEG。没有读取未知照片/文件、选择系统分享建议收件人或外发。

## 实际观察

| 子范围 | 实际动作与结果 | 结论 |
|---|---|---|
| 代码复制 | 既有 peer 回复的代码 Copy → composer 原生 Paste，实际草稿显示 `print(42)` 及末尾换行；清空草稿，没有 Send | pass；不是仅以 toast 认定复制成功，不声称剪贴板字节 hash |
| 整条消息复制 | 原生 Copy message → Paste，实际草稿依次显示 `print(42)`、空行、`Second line.`；代码围栏/语言标记未进入正文；清空，没有 Send | pass，保留可见文本/换行证据 |
| 英文软件键盘 | 临时开启系统 Show Onscreen Keyboard，实际 QWERTY 出现；composer 和 Send 移至键盘上方，无重叠；多行草稿可见 | pass，仅此英文/布局子范围 |
| 中文输入 | 原系统已装 Simplified Pinyin 10 Key；切换操作未得到稳定中文候选及组合提交画面，没有更改键盘清单/顺序，也没有授予第三方完整访问 | inconclusive；Mac 输入或粘贴汉字不能替代手机 IME |
| 最大辅助字号 | 临时开启 Larger Accessibility Sizes 并设到最大；聊天正文/代码/过程/统计可读，Copy 标题换行但完整；Chats、Tasks、Agent、Me 四根页均打开，底部入口可操作 | pass，仅已测页面；未覆盖最大字号与软件键盘组合全矩阵 |
| 大字号表单与失败恢复 | Profile & language 顶部 Save 可达且 disabled，滚动可达默认设备及 English；无表单保存。Tasks 初始旧网络错误经显式 Retry 恢复 No tasks | pass，不把空任务页当任务图证据 |
| VoiceOver | 临时 Caption Panel，VoiceOver 开关短暂 ON 两次；通知请求选 Don't Allow；稳定复查 VoiceOver OFF，没有焦点、字幕或语音证据 | inconclusive；没有证明持续 VoiceOver 可用，也不推断 Apple 不支持 |
| 图片剪贴板，空草稿 | 已知 PNG 的系统分享面板 Copy → composer 原生 Paste，出现唯一合成图 pending 缩略图、Send active；移除后输入为空、Send disabled，无自动发送 | pass，真实图片粘贴到目的草稿 |
| 图片剪贴板，有文本 | 输入本轮 `R4` 后再原生 Paste，同图 pending 与 `R4` 同时保留；移除图片并清掉两字符，恢复 placeholder/Send disabled | pass，没有发送探针消息 |

图片路径为既有测试 PNG 的 Quick Look/系统 share sheet Copy；没有本轮再次 Save Image，也没有 API 代发。两次 Paste 各产生一项正常待发上传资源，资源总数 **13→15**，新增资源均为同一已知 PNG hash。五条消息总数保持，四条 native 基线 full rows 精确一致；额外第五条是 2026-10-07 已存在的 API-seeded 消息，不是 R4 新发送。

## 还原与环境清理

- 原文字大小 **4/7 中档**已通过官方 Shortcuts 单动作 Set Text Size＝Default 还原，并重新打开 Larger Text 确认中心滑块；Larger Accessibility Sizes OFF。
- AssistiveTouch、Show Onscreen Keyboard、VoiceOver、Caption Panel 均恢复并实际确认 OFF；键盘清单/布局保持。字体滑块的 Mirroring 拖动不能可靠定位中档，因此使用官方系统动作，没有 App 修补。
- 手机 Tailscale 恢复为原 Not Connected，没有退出已登录账号。测试草稿、pending 附件、share sheet 全部清空，回到主屏幕。
- 临时 Set Text Size 快捷指令取得用户单独许可后已删除，稳定的 All Shortcuts 仅剩原扫描快捷指令；实际确认后退出到主屏幕。
- 剪贴板已被复制测试替换为合成 PNG，原内容事前没有保留，**无法声称原剪贴板已还原**。VoiceOver 的首次通知弹窗选择拒绝，没有新增通知权限，但原未询问状态不等于拒绝后的状态。
- 之前用户主动开启的 Developer Mode、App 安装及 R3 已授权保存的合成图/仅添加照片权限是既有使用结果；本轮不改成另一安装/权限状态。
- 本轮 owned Gateway、IM、foreground Tailscale Serve 和 tmux 会话已结束，54184/19443 无监听、Serve `{}`；既有 LLM tmux 保持。数据库、附件、工作区及 0600 resume 配置保留，未 reset/purge。
- 停服后普通 `mode=ro` 连接报 unable to open；确认 owned 进程已退出、WAL/SHM 不存在后，`mode=ro&immutable=1` 只读检查得到 quick_check＝ok、五条消息/四条原 native rows 不变。记录为读连接限制，未诊断 VFS 根因或改数据库，不把它写成产品损坏。

## 证据定位与后续门槛

实际 UI 证据来自本轮 CUA 输出；私有 `device-private/native-r4-checkpoint.json` 保存初始/还原状态、实际探针、完整行比较与清理结果，`runtime-resume/message-preservation.json` 保留原四条 native 基线。凭据、数据库、照片截图、设备身份不入仓。

远端 main 经 GitHub API 当前验证仍为 `d87ffa3d19160d45d309f281b0ace4ff92f55a38`；本轮 SSH fetch 超时，不称其为成功 fetch。Draft PR [#324](https://github.com/Mrchen116/nano-multiagent/pull/324) 的五项 required checks 在 `b6605d4` 上 SUCCESS，[run 37663638984](https://github.com/Mrchen116/nano-multiagent/actions/runs/37663638984)。这些是对应版本 CI，不替代中文 IME/VoiceOver 或自然签名到期证据。

本轮只增加补测报告，不改产品代码、canonical spec 或签名；S2 的完整手机中文组合与可访问性、S29 的完整功能及 S30 的同网续签/自然到期仍 open，PR 保持 Draft。完整通过不能由此窄范围结果推导。

本地文档完整性检查通过：327 maintained Markdown sources / 75 required routes；diff whitespace 检查通过。本报告保存在当前工作区，未把它说成已发布到 PR 的内容。

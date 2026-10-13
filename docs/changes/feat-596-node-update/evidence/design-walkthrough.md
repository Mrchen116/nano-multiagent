# 设计原型走查

- 日期：2026-10-13（Asia/Shanghai）。代码基线 f486d889f；首文档/设计为本 unit 未提交产物。
- 真实产品基线：独立 IM 52529 + 独立 Node/DSH，默认 E2E 账号，/settings/nodes。使用 Playwright CLI 实际登录并查看；未操作生产。基线 [current-desktop.png](current-desktop.png)。
- 原型：HTTP 52531 的 prototype.html；演示控制明确放在产品外层，模拟任务/更新不冒充真实产品。
- 1280×900 [prototype-desktop.png](prototype-desktop.png)：设备名和在线状态仍首先出现，版本/说明/影响/唯一更新动作同区，别名保存独立在下方。更新区域无弹窗，不遮聊天入口。
- 390×844 [prototype-mobile-waiting.png](prototype-mobile-waiting.png)：点击更新后经过下载进入等待，主按钮变成取消；版本另起一行，说明和按钮纵向排列，无横向溢出，设备名仍可辨认。
- 390 宽聊天 [prototype-mobile-chat.png](prototype-mobile-chat.png)：演示切换中提交“更新好以后，继续整理明天的待办。”，输入仍可用，消息下出现等待电脑更新完成提示；电脑 chip 表达正在更新。
- 820×900 [prototype-820-recovery.png](prototype-820-recovery.png)：回退结果与重试放在同一区域；说明为已恢复原版本，不声称更新成功。中间宽度说明不挤压动作。
- 边界范围：原型内可切换离线、下载失败、恢复失败、旧版、源码和未发布状态。当前走查不证明更新器、服务端消息等待或真实重启；实施后及独立产品验收必须走真栈，用户要求的视频录制真实实现。

## R1 恢复状态修订

手机 390×844：切换时发送消息，再切换到 recovery_required；聊天入口变为“电脑需要恢复”，原排队消息变为“电脑恢复后继续处理，无需重发”。实际渲染截图：[mobile-recovery-chat.png](mobile-recovery-chat.png)。这是设计原型证据，真实恢复与消息重投仍由 M1 验收。

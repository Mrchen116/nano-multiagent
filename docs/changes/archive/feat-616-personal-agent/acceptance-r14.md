# R14 统一个人助手配置入口验收

结论：PASS（本轮限定入口与来源配置验收）；发现 1 个入口问题，修复后单次真实复验通过，剩余阻塞问题 0。

验证基线：`34b5fefcb6eee92689d3ad47f860d259638f3c17` 加 R14 dirty diff；caller 已构建并提供隔离服务 `127.0.0.1:53808`。独立 CUA tab，R12 可丢弃账号、1280×720 桌面。未改产品代码、未启动模型节点、未修改主账号策略或名字。

判据来自 spec 的 PA 配置统一要求与 design 的 R14 must-match：聊天到配置一跳、唯一名字字段、聊天访问可发现且修改结果明确、手机可读可操作。

## 观察

- 首次发现离线但持久化 status=active 的 PA，在聊天菜单点击 Agent configuration 仍进入 Personal assistant 浮窗，只显示 not ready / setup saved；直接 Agents 入口可打开完整配置。此问题已反馈 caller。最终 build 刷新后，从同一离线 PA 聊天菜单再次点击 Agent configuration，直接进入 `/settings/agents/pa_37d0c53dabee`，没有浮窗，复验 PASS。
- 直接进入配置后，仅有一个 Display Name 字段；同页保留 Identity、Behavior、Access & Model 及既有标签。Chat access 作为独立卡片位于身份之后，默认折叠 Excluded chats，说明勾选立即排除、取消恢复、旧内容不被擦除。
- 勾选 R13合成来源一：立即显示 Changes applied 与 Excluded chats · 1，持久化 revision 2→3，excluded_json=[r13_source_1]。没有点击 Save Agent；刷新后仍为选中。
- 取消该勾选：立即显示 Changes applied 与 Excluded chats · 0，持久化 revision 4、excluded_json=[]。测试来源恢复初始权限。
- 桌面独立实际操作与 1280×720 截图显示卡片层级清楚，来源名称、勾选、即时说明可一起辨认。513×827 手机截图来自主执行者并由本 reviewer 直接查看；单列身份与访问卡片、字段和文字正常换行。窄屏不是独立重跑。

## 证据与边界

本地证据目录 `data/acceptance/feat-616/r14-unified-settings/`：offline-active-modal.png、excluded-immediate-desktop.png、restored-access-desktop.png、after-exclude.json、after-restore.json、unified-settings-mobile.png。

普通名字/模型/指令保存沿用既有路径，本轮未修改或运行模型验证。更换电脑没有其他在线节点 fixture，未执行迁移；创建与 pending 恢复保留前轮证据，不重复建账号/节点。未注入网络失败。本轮只验统一入口与来源即时持久化，不把来源变更当作新 LLM 访问判定结果。

## 最终 must-match 裁决

| 必验项 | 结果 |
|---|---|
| 聊天到配置一跳 | PASS；离线已创建 PA 修复后真实点击验证 |
| 页面唯一名字字段 | PASS；完整 AX 及最终桌面截图 |
| 访问卡片可发现、变化结果明确 | PASS；即时提示、数据库 revision、刷新持久化 |
| 手机可读可操作 | PASS；共享 513×827 实拍已独立审视，主执行者完成展开操作 |

最终截图：`unified-settings-desktop-final.png`（1280×720）。保留前述来源切换证据，入口修复后未重复操作策略。结束时已通过登录页恢复 nano / Test User；关闭仅自己的 tab2，主 tab5 未操作。未提交报告；由 caller 收口提交。

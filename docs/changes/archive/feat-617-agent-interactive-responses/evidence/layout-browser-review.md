# 消息布局实施自检

2026-10-19，在同一 worktree 的隔离 58769 真实客户端，保持 c_8iutij8v 原有复利生成源不变。

- 桌面实际 viewport 1537，消息面板 1275.5px；最新交互内容从 654px 变为 1189.9px，外壳 computed background 为透明；头像、作者、时间保留。四张历史交互回复均正常加载。
- 真实 viewport 390×844：document scrollWidth=390，消息面板390，交互内容320.4，输入right371.8，未溢出。Tabs可切到增长实验室，底部composer保留。截图 `/tmp/feat617-layout-evidence/after-390.png`。
- c_dm0w2u5u 已有普通短消息宽度分别为37.5/246.7/152px，长内容含代码的消息1189.9px；短句没有随Agent行拉长。代码按钮实际可点击；当前浏览器clipboard读取返回空，作者不将此当作复制内容成功证据，留独立验收核实。
- Chrome 现有缩放使 viewport capability 参数与 CSS viewport 相差1.25；实际检查以 innerWidth/innerHeight为准：参数312×675得到390×844；参数614×720得到767×900。中等桌面断点需独立补769，避免把767当768。
- 页面偶有“Real-time updates are busy”重试横条（基线已存在）；一次刷新后消失，另开标签仍可复现。未改实时链路，不将静态渲染等同发送/交付通过；独立验收按可见事实记录。
- 图片仅保存在仓库外 `/tmp/feat617-layout-evidence/`。不提交dist或截图。

验证：窄测 message-pane + interactive-card 108/108通过；前端build通过；docs-check通过（使用主仓现有venv），diff-check通过。第一次全量908/909，失败为互动恢复测试在textbox出现后立即断言恢复值，而Renderer在effect中恢复；改为waitFor实际值，未改产品恢复逻辑，后续结果见交付记录。

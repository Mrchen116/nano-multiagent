# bugfix-699: Code Review

## Review scope

- Base / executed_base: `95c6b3deb07c03e9edd3b78375cd0ae29e87558e`
- Review mode: full；独立 reviewer `/root/openui_visual_review`，gpt-6.1-sol / high。
- validated_at: 首轮 6-file working diff（catalog、两个生成 prompt/Skill、InteractiveCard/CSS、theme.ts 删除）。

## Round 1

- Result: `[]`，无存活缺陷。
- 覆盖锁定 OpenUI 0.18.1 ThemeProvider/Stack/Card/IconButton 源码、生成器和 Skill 安装消费链；独立资产 --check 通过。只读机制和窄屏换行保留。
- Context: Mode B；首轮未观察真实 provider 输入/模型消费，不能冒充真实视觉验收。
- 文档：指出 current 的 Nano 视觉描述需收口，已准备 unit delta；用户确认前暂不归并。

## 后续 delta

- 主会话继续检查短常驻 policy，发现其仍描述 Nano theme；改为上游视觉与自主布局，待 patch review。
- 浏览器视觉与真实模型结果见 validation.md，不以代码审查代替。
- 用户验收未发生，unit 维持 Active。

## Patch Review

- reviewer 同上；scope：intelligent-ui.ts 短 policy 与新增 unit 文档。
- Result: `[]`。短长指导一致，无工具/权限语义变化；Active 与用户验收边界明确。
- validated_at: 最终 7-file 源码工作区 diff 加上述 unit 文档（记录事实的后续追加不改变代码）。
- 审查后仅补充主会话实际测试、浏览器结果与本机原生日志 locator；未新增代码。
- 首轮和 patch 均通过；真实 wire payload 未核验的限制保留。

## 扩展范围 Full Review：Open Intelligent UI

- 范围：上述 base 至全部本任务 commits + dirty diff；包含 vendored 上游组件/函数/公共资源、公开子入口、Web/server 目录、生成链/短 policy/Skill、协议版本与相关测试。
- 独立 reviewer：`/root/openui_visual_review`，沿用 gpt-6.1-sol / high；调用 change-code-review 与 agent-context-review Implementation Review（Mode B）。未参与受审实现。
- 两项 CONFIRMED / P2：snapshot 普通命名 label/options 未解析导致模型只收到 ID；Pressable 与地图 marker 的非原生点击绕过 disabled fieldset。
- 修复：snapshot resolver 解析 named AST；Pressable 与 map selection 写入检查宿主 disabled fieldset。新增命名标签/选项与真 Renderer 只读回归。
- Closure / patch 结论：`[]`，两项 closed，无其他成立问题。独立通过服务端 17 tests、组件 2 tests、只读 1 test、生成资产检查；地图禁用按代码链核实，未另跑真实地图。
- 后续仅追加通用照片拼贴指导（Grid 避免媒体 Row 自动限宽）及本次实际验证事实，不引入业务模板/权限改动。
- Context 观察：主会话真实模型已生成新目录的 Box/Svg/Pressable/本地函数交互，反馈后自行修改程序；不将这些行为或原生日志等同 provider wire payload。视觉和运行证据见 validation.md；用户验收仍未发生。

## 通用按钮指导 patch

- 用户指出 Close/Reset 每张都有后，基于 `8807c5d66` 审查新增短/长生成规则与同步资产。
- reviewer 同上，结论 `[]`：不默认添加装饰操作，按具体任务决定控件；未删除组件能力、未改变权限，短长一致。

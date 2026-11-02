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

## 短选择与设计指导 patch（2026-11-02）

- Base/head：`74c02b212dc47bc7aaa22e8abfb26f03936af23f` + 本次4-file dirty diff（公共intelligent-ui.ts、incident、as-built design、Web delta）；后续只补实际验证和本记录。
- 独立reviewer `/root/openui_visual_review`，gpt-6.1-sol / high；change-code-review + agent-context-review Implementation Review / Mode B。未参与本次实现。
- Result：`[]`。确认英文选择/设计段符合用户决定；状态、真实性、授权与root/child交付边界保留，Skill、组件、解析和case均未改变。
- 实际Context限定于本次SID `f57cea98-164a-4e0a-84f2-bfbd8f9d87b0`：native seq9有新规则且无旧表格偏好，seq14保留工具/Skill schema，seq23出现固定自然任务。baseline源码、dataset v4、CSV哈希和零消息起点一致。未核provider wire；审查不冒充采用率或视觉通过。
- 实际模型采用与空图失败分别记录在validation.md；本次未宣称修复既有解析缺陷。

## 发布前诊断 patch（2026-11-03）

- Base/head：`b26bcff02320a7d8d889f0c21addbf41eeaeae95` + 本次IM校验/错误转发、Channels、PA、相关测试和unit文档dirty diff；包括旧图片fixture迁移及前端CI补共享依赖安装。没有改上游parser、生成指导、case或前端组件。
- 独立reviewer `/root/openui_visual_review`，gpt-6.1-sol / high，change-code-review + agent-context-review Mode B。初轮发现快照把未初始化binding当字面null，误拒Input/TextArea/Checkbox。
- 修复：快照null-required不当确定错误，原程序显式非法null仍拒；非null计算类型/enum及官方runtime诊断保留。新增空绑定与并存已知错误回归。Closure：该finding **closed**；最终结构化结论 `[]`，无存活问题。
- 独立复测60项通过；同时核共享PA明确拒绝、图片fixture迁移与CI依赖安装，无新问题。实际validated_at为上述最终working tree，后续仅追加本记录/验证事实；executed_base同上，没有混入额外main更新。
- Context证据覆盖真实IM/WebSocket拒绝→修正成功，以及原生model stub下一次o.messages中的错误标记与定位字段。证明工具诊断实际交付，不证明真实模型自主修正、provider wire或视觉正确性。初始null和未返回Query数据的限制已在design/validation明示；用户验收仍未发生。

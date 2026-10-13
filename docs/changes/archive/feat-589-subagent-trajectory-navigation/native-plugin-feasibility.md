# 保留原生轨迹界面的插件扩展验证

2026-10-13。用户要求先验证两个扩展点，并保留官方界面；此前的 Nano 导航视图方案不作为本轮方案或验收对象。本文记录技术可行性，不表示新方案已获批准或实现。

## 结论

当前锁定的 `@deepseek-ai/dsh-client-ui-trajectory@0.2.1-alpha.1`，无法只用现有公开插件契约，同时完成：

1. 在原生工具记录/后台事件处增加可点击的子执行入口。
2. 进入子执行时，从外部设置原生时间线的本次执行选区。

原生记录表、时间线和详情面板可以完整保留。缺少接入点不构成重写这些组件的理由。

## 实测方法和结果

实验直接执行构建时原样复制的官方 `client.js` registration bundle，并使用真正的 `SlotRegistry` 注册官方插件。在 React/JSDOM 中挂载注册表里的原始组件，提供最小会话事实作为夹具。没有修改依赖包、上游文件、正式 boot 或 renderer，没有引入替代轨迹组件。通过公开注册表取得组件仅用于实验观察，不作为产品集成方案。

| 验证 | 实际结果 |
| --- | --- |
| 图片插槽正对照 | `conversation.trajectory.images` 注册成功 |
| 原生声明的子插槽 | 仅 `conversation.trajectory.images` |
| 给记录增加动作插槽 | 注册 `conversation.trajectory.row-actions` 抛错：slot is not declared |
| 工具定位正对照 | `viewRequest: { view: 'trajectory', focus: 'probe-call' }` 选中对应原生工具记录，并确认请求一次 |
| 外部范围尝试 | 传入 `range`、`timelineRange` 和范围形式的 `focus` 后，未生成选区或 `data-timeline-focus` 标记 |
| 原生范围正对照 | 同一个原始组件接收手动拖动事件后，生成选区及 inside/outside 标记 |

范围尝试中的字段不属于现有公开契约；实验只证实它们不会被组件消费，不代表已存在一个坏掉的范围 API。手动选区会聚焦记录，**不会删除选区外的记录**。

本结果是发布包运行实验和公开契约核查，不是完整浏览器产品验收。此前对另一个界面的产品验收不能转用于本方案。

发布包 SHA-256：`fb7909bc7694ab30fd17d10d7c752a69b02d31c94f51f50b64caa5301e03c6b6`。

## 公开契约核查

发布包的 `lib/types/client/index.d.ts` 仅提供 `apply`、`inject` 和轨迹事实类型。Conversation 的 `ConvViewOwnerProps` 提供 `inspectCall`、`viewRequest`、`openView`、`completeViewRequest`；`ConversationViewRequest` 的字段只有 `view` 与 `focus`。

对应本地上游源码基线 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`：

- `packages/client/ui-trajectory/src/client/index.ts`：声明图片子插槽，未声明记录动作插槽或供外部控制选区的共享 store。
- `packages/client/ui-trajectory/src/client/TrajectoryView.tsx`：`timelineSelection` 是组件内部 state；`focus` 被解释为工具 `callId`；组件只调用图片 `renderSlot`。
- Conversation 的事件/视图 registry 允许贡献结构化事实，不等于能够向既有记录渲染位置插入交互控件。新增一个自定义 slot 名称也不会使官方组件自动渲染它。

最终判断针对仓库锁定的发布版本，不外推到尚未核实的新版本。

## 保留原生界面的最小后续方向

要完整实现原定体验，需要官方组件增加两个公开契约：

1. 记录动作扩展位置：向插件提供当前记录身份/序号，允许渲染“查看子执行”等动作；后台事件可使用同一扩展机制或单独的事件装饰位置。
2. 受控选区/定位请求：允许传入执行范围，并明确清除、切换会话和一次性消费语义；沿用原有时间线、表格和详情渲染。

Nano 插件随后只负责关联执行事实、跳转和返回路径。该接口补充是建议，没有在本轮修改上游，现有仓库禁止 fork/patch/private import 的边界仍然有效。

如果维持当前依赖版本，界面外层可以放入口，再打开官方完整会话并使用已有工具定位；自动设置原生选区和原位记录入口仍无法满足。因此它只是能力降级选项，不能声称完整实现两个扩展点。通过 DOM 注入按钮或操纵 React 私有状态也不属于已验证的公开插件方案。

## 复现

已有 viewer 构建产物时，在仓库根目录运行：

```sh
pnpm exec vitest run --config packages/dsh-trajectory-viewer/probes/vitest.config.mjs
```

实验源码见 [native-extension.probe.ts](../../../../packages/dsh-trajectory-viewer/probes/native-extension.probe.ts)，使用 [独立 Vitest 配置](../../../../packages/dsh-trajectory-viewer/probes/vitest.config.mjs)，不进入常规测试扫描。官方静态模块带有 CSS，独立配置显式将依赖交给 Vite 处理。若无 `dist`，先执行 `pnpm --filter @nano/dsh-trajectory-viewer build`。

运行结果写入 `/tmp/feat589-native-plugin-probe-results.json`。本轮最终运行：1 个实验通过，所有正反对照断言通过。上游发布包缺失 sourcemap 会产生告警，不影响断言执行。

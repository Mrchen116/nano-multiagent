# 原生轨迹 UI 的本仓分叉基线

## 用户决定

2026-10-13，用户在核对当前插件接口限制后明确提出：

> 那你直接拷贝他这个插件包，我们基于他当前插件包分叉独立演进这个新包，本仓内维护。是否就ok

该决定授权复制并独立维护轨迹 UI 单包，保留原生界面，取代此前双视图技术方案。它不授权修改 DSH 执行运行时或其他上游插件。原始源码引入不声称实现了子执行跳转和外部选区。

## 已完成的源码引入

- 新包：[`@nano/trajectory-ui`](../../../../packages/trajectory-ui/README.md)。
- 来源：官方 `dsh-client-ui-trajectory@0.2.1-alpha.1`，commit `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- 39 个源码文件及样式原样复制，逐文件 SHA-256 与基线一致。
- 上游测试原文保留供迁移参考；这些原 monorepo 测试未在 Nano 跑通，未冒充已验证。
- 版权、MIT 许可和来源记录保留；新包拥有独立名称、构建配置与版本固定的公开依赖。
- 独立构建保留 DSH browser module-loader registration ABI；React、Conversation、Store、Slots 和 UI primitives 继续使用宿主共享实例。
- `SPEC.md` 与依赖契约只增加这一 UI 包的维护例外；参考上游仓库和安装的官方包均未修改。

## 本轮验证

| 验证 | 结果 |
| --- | --- |
| 上游文件摘要比对 | 39 / 39 一致 |
| 新包 `typecheck` | 通过 |
| 新包 `build` | 通过，生成独立 `@nano/trajectory-ui` 浏览器注册 bundle |
| runtime dependency contract | 13 passed |
| 挂载本地构建 bundle 的 React/JSDOM 实验 | 1 passed；图片插槽注册、工具调用定位、手动范围框选均通过 |

运行结果和能力边界见包 README。该实验不是浏览器完整旅程验收。

## 基线引入时尚未发生的接入与功能变更

在基线引入提交 a8844b60e 时，Work viewer 仍使用既有接线；新包尚未替换它。基线引入没有增加行级子执行入口或可控制的时间线选区，也没有重新验收最终界面。复制基线本身不改变这两处能力缺口。后续已经接入的单视图实现见 [M1 实施记录](M1-navigation/native-implementation.md)。

下一阶段以原版 UI 为体验基线，在本仓分叉内增加记录动作和范围控制，复用已实现的运行事实与宿主父子导航。最终只保留一个原生派生轨迹视图，退役此前独立重写的导航视图；首文档、设计、delta、原型与适用门禁需对这一最终实现重新对齐，不沿用旧双视图的通过结论。

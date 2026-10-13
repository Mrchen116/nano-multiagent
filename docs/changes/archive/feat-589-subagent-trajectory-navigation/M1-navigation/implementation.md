# M1 导航实施与证据

运行事实部分见 [run-facts.md](run-facts.md)。宿主保留父 frame，并在身份切换／资格失效时销毁整栈；Nano slot 通过官方 useTrajectory 消费原始投影，提供本次范围、搜索、轮次折叠、缩放、记录选择、图片和完整请求检查。原版明细保持挂载，以公开 callId focus 打开调用详情。

## 回归与构建

2026-10-13，在专属 worktree、Node 25.8.2、锁定 DSH 0.2.1-alpha.1：

- 新宿主导航测试先取得 2 个失败，再验证父 frame 保留、逐级关闭、1008 撤权清栈、登出和不可信消息拒绝。
- 新 navigation-model 测试先取得缺模块失败；系统提示词 header 用例先取得缺行失败，修复后全部 3 tests pass。
- workspace `pnpm build`、viewer typecheck、frontend `npm run build` 通过。干净 npm ci 后没有复现主仓旧类型错误，无需修改 message-pane。
- `pnpm test`：61 files / 175 tests passed，2026-10-13 13:50。
- frontend `npm run test`：88 files / 828 tests passed，2026-10-13 13:50。
- runtime dependency contract：11 passed；viewer 新增唯一 product-contracts DTO 依赖在白名单显式声明。
- viewer transport + navigation：7 tests passed，之后新增 system/header 回归并通过。

## 实际模型与浏览器

服务使用 unit worktree 的 e2e-up，IM 63084、独立 node wt-nano-multiagent-70917、独立 DSH home／数据库／workspace。浏览器实际通过新建入口建立 global `nav589`，使用 codexOAuth:gpt-5.6-sol；memory/skills feature 关闭。没有用户私有文件输入。

主 Session `74c67333-9483-43ac-9120-74d8b0b75ec8`：

| 发起 | 子 Session | runId | 父坐标 | 本次范围 | 实际结果 |
|---|---|---|---|---|---|
| 计算乘积 | 2e682240-19a8-4fed-9589-d1015052c2ca | a16480f6-28ff-48e2-8205-471457f15927 | 26 | 3–24 | completed，391 |
| 独立复核 fork | c51ff44b-665a-4557-af9a-c5ca37941f1e | 1ce0ce76-2806-4a47-aece-bbd208a8177e | 27 | 3–19 | completed，399 |
| 嵌套计算 | 833480fc-c1d1-47c8-8fd1-fa4be1398008 | 2d3fdede-ba17-4b0a-9444-409efaeb6924 | 60 | 3–25 | completed，221 |
| 心算乘法结果（上行子执行发起） | 37adf1d6-1df7-4a37-b9aa-23f1ff3bd3b7 | 2417a48a-e7d1-49cd-8d34-36bf9a13ac41 | 18 | 3–19 | completed，221 |

第一轮普通与 fork 并行。首次嵌套被默认 maxDepth=1 拒绝，工具详情如实显示错误；随后仅在本隔离 DSH profile 设置 maxDepth=3，重启其子进程后真实完成两级委派。不是产品默认配置变化。第一轮处于父首轮，fork 无已完成父轮可继承；非空继承边界另由真实 DSH fixture 覆盖。

真实浏览器已验证：发起行进入准确 child；孙级进入及逐级返回；父级 2.0× 缩放和选择恢复；原生明细公开 callId focus 展示参数、结果、Schema、计时；切换时只显示来源摘要，不误标原生为本次范围。1280 桌面和 820 中宽截图分别为 desktop（本地截图）、820（本地截图）。390 走查后提高宿主最小高度，继续补最终截图与独立产品验收。

运行事实的失败／取消／重启 unknown／continuable 多 epoch／knowledge 来源已通过真 DSH+受控模型测试；这些测试不单独构成 UI 产品验收。独立门禁与剩余真实场景在交付前补齐。

## 独立静态审查修复

R1 发现 W1：官方同一会话重新同步并替换历史窗口后，已选旧执行可能掉出已加载范围，固定 runId 不会重新触发补页。`210e100dd` 观察公开窗口起点与打开状态，重新补齐本次起点；公开 loader 即使软失败返回也验证覆盖，并显示可重试的读取错误。没有覆盖时禁用起止定位。

真实 React 组件的两项回归先失败，再验证同会话窗口替换与软失败重试。2026-10-13 14:09，viewer 3 files / 10 tests passed；viewer typecheck 通过。14:15 全量 workspace 62 files / 177 tests passed。这些组件测试验证恢复逻辑，不替代独立浏览器产品验收。

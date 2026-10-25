# feat-657 设计取证与原型走查

日期：2026-10-25。作者：本会话主 Agent。以下是源码/原型设计证据，不是功能已实现或产品验收证据。

## 当前产品基线

- `git fetch origin` 后 HEAD 与 origin/main 均为 b80e6d74d，ahead/behind 为 0/0。需求随后独立提交为 404b5ef02。
- 首次隔离服务用了已有旧 dist，作者误将其打开。用户指出不符合最新设计；该图作废。前端依赖缺失使首次 build 失败后，按 local-development 运行 `npm --prefix src/IM/frontend ci` 和 `npm --prefix src/IM/frontend run build`，成功；又执行 `pnpm build` 并仅重启本任务 daily 隔离栈，保证后端接线也来自当前源码。
- 当前基线真实入口：`http://127.0.0.1:58300/settings/agents/daily-product`，及 `?view=work`；测试 owner 来自 daily 模板。没有发送外部消息或修改生产状态。
- 已实际观察 1440×1000 配置页和 390×844 Work 页：连续白底、紧凑身份头、横向标签；窄屏隐藏 Agent rail、保留返回与底部导航。截图中测试 Work 为空，只证明现有框架，不证明真实活动停止。
- 代表性图片保存在本机 [当前桌面基线](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/baseline-desktop.png) 和 [当前窄屏 Work](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/baseline-mobile-work.png)。按仓库规则不提交截图缓存；这些定位仅供同机复核，异机可按 design runbook 重建。

## 原型走查

原型通过本地静态服务实际渲染，Playwright 会话 `feat657`；服务是演示资源，不是新增产品服务。

| 旅程 | 观察与判断 | 代表性本地证据 |
|---|---|---|
| 桌面停用 | 页头/列表显式按钮，无二次确认；点击后状态条先说明禁止新工作、尚未确认。保留 Agent 身份和 E/Q 独立状态，目标不混淆 | [正在停用](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-stopping-desktop.png) |
| 390 宽度已停用 | 操作换到身份下方，状态说明完整换行，设备在线与 Agent 停用可同时识别；未出现横向页面溢出 | [已停用](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-disabled-mobile.png) |
| 重新启用 | 开关可重新启用，状态提示明确旧任务不自动恢复；具体任务恢复复用既有 Tasks 详情，当前原型不新增 Work 恢复入口 | 修订后画面见下文 |
| 320 宽度失败→重试 | 红色说明区完整表达未确认与禁止新工作，启用不可用，重试可达；将演示结果恢复正常后重试可进入已停用 | [停止未确认](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-failed-320.png) |
| 离线→重连 | 等待确认状态不显示零活动或已停止；模拟重连后先清理才收敛 | [离线](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-offline-320.png) |
| 非管理者 | 状态仍可读，控制不可用 | [只读](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-readonly-320.png) |
| 草稿与开关独立 | 编辑名称后启用/停用，草稿保留，未触发保存；开关说明明确立即生效 | [配置草稿](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-config-draft-320.png) |
| iOS 局部方案 | 单独以 List Section 展示身份、设备、Toggle、状态说明和按钮；不将 Web 缩窄当原生截图 | [原生意图表达](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/prototype-ios-intent.png) |

增量取舍：状态区使用细边线与短文保持当前页面密度；异常态仍完整显示原因和动作，不以一个图标替代。Work 正文沿用当前基线的工作记录/原生轨迹框架，不新增活动统计或重设计工作列表。原型顶部模拟控制始终在产品区域外。

未验证项：没有实现后的后端、真正的进程终止证据或原生 iOS 实机视觉。HTML iOS 表达只证明设计意图；实施验证深度按 design 约定。原型计时仅演示状态变化，不构成性能承诺。

## 用户反馈修订

用户指出原型擅自添加“主执行 1 / 子 Agent 2 / 后台 Bash / 终端 2”统计，超出停用开关需求。作者删除统计及自造的活动列表/Work 恢复按钮；Work 背景恢复当前基线框架，只新增生命周期入口与必要状态。旧任务恢复复用既有 Tasks 详情的真人操作。上表修订前截图只能作为已走查交互的历史证据，不能作为最终 Work 布局实施依据；最终画面以本次修订后原型和下方新取证为准。

修订后重新实际渲染并走过停用→已停用→重新启用：状态提示仍保留旧任务不自动恢复；320 宽无页面横向溢出，统计节点已删除。最终布局参考 [桌面修订稿](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/revised-desktop.png) 与 [320 宽重新启用](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/revised-enabled-320.png)。

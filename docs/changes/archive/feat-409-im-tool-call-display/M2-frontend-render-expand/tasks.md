# feat-409-M2: 前端分工具渲染 + 长输出可控展开 — Tasks

> 对齐: ../design.md v1

## 目标

前端按 M1 透传到位的 `detail` 字段，把工具调用从「裸 `<pre>` JSON」升级为：折叠态一行就有信息量（emoji + 真实工具名 + presenter 人话摘要 + 失败标红），展开态按 name 精渲染 8 个内置工具（bash 终端块 / edit diff / write 内容 / web_fetch 卡片 / agent 完整 prompt 在前 / memory / skill_manage / task_stop 专属卡片），未知/DIY 工具回退通用结构化卡片（按 key 渲染，非裸 JSON），长输出默认截断 + 展开全部限高滚动 + 收起 + 源头截断标注。历史无 detail 消息降级回退 output 串显示，不报错。

## 退出标准

- [x] `chat-types.ts` ToolCall 增 `detail?: ToolDetail`（结构化 dict）
- [x] 折叠态：直接渲染 `output`（presenter 产的 summary）+ `status==failed` 标红 + 真实工具名 + emoji 按 name 兜底映射（**不按 name 派生折叠文案**）
- [x] 展开态：按 name 精渲染 bash/edit/write/web_fetch/agent/memory/skill_manage/task_stop；未知/DIY 工具通用结构化卡片
- [x] agent 展开：完整 prompt 排在结果前
- [x] 长输出两级展开：默认按前端阈值截断 + "展开全部" → 限高内部滚动 + "收起"；`detail.truncated===true` 末尾标注"输出过长，已在源头截断"
- [x] 历史无 detail → 降级（回退 output 串显示，不报错）
- [x] vitest 覆盖各分支；`npm run build` 绿
- [x] 真实浏览器视觉/交互自测，与 prototype 对照

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - 折叠态用 output 文本渲染 + 失败标红 + emoji 兜底 + 真实工具名
  - 各内置工具展开精渲染（bash 命令/stdout、edit diff、agent prompt 在结果前 等）
  - 未知工具通用卡片按 detail key 渲染（非裸 JSON）
  - 长输出截断 → 展开全部 → 收起；源头截断标注
  - detail 缺失降级（老消息回退 output）
- 已有测试在：`src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx`（扩展）
- 落层/目录/marker：前端 vitest（component test），无 e2e marker（项目无浏览器 E2E 体系）
- 可选依赖 importorskip：N/A（前端）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器自测截图（ACCEPTANCE/feat-409-M2/ 下）

### 前端 UI 字段

用户路径分类：`normal-ui`（工具调用展示是 agent 对话核心观察面，但非提交/数据写入路径；以组件回归 + 真实浏览器验收覆盖）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 各工具折叠/展开 component test + 浏览器 |
| loading | running 态 pulse（沿用现有，回归保留） |
| empty | toolCalls=[] 渲染 null（现有测试保留） |
| error | status=failed 折叠标红 + 展开 error 卡片 component test |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | 长 stdout 截断/展开/收起 component test + 浏览器 |
| missing/nullable data | detail 缺失降级 component test（老消息） |
| mobile viewport | 浏览器 375 截图（限高滚动不撑爆） |
| desktop viewport | 浏览器 1440 截图，与 prototype 对照 |
| dark mode | 项目默认暗色主题，即默认态 |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 各工具展开精渲染分支 | component test（vitest） | 是 |
| 未知工具通用卡片回退 | component test | 是 |
| 折叠态用 output + 失败标红 | component test | 是 |
| 长输出截断/展开/收起 | component test | 是 |
| detail 缺失降级 | component test | 是 |
| 视觉与 prototype 一致性 | 浏览器截图 1440/375 | 否（一次性证据） |

## Roadpoints

### R1 — 类型 detail + 折叠态通用渲染（output + 失败标红 + emoji 兜底 + 真实工具名） — DONE

- 步骤: chat-types.ts 加 `ToolDetail` 联合/宽松类型 + ToolCall.detail；tool-calls-panel 折叠行改为 emoji(按 name 兜底映射) + 真实 name + summary(=output 文本) + failed 标红 fail-tag
- 验证: component test 折叠态用 output 渲染 / 失败标红 / emoji 兜底 / 真实名；现有运行态/空态回归保留

### R2 — 展开态分工具精渲染 + 未知/DIY 通用结构化卡片 — DONE

- 步骤: 抽 `tool-detail-renderers.tsx`，按 name 分发 bash/edit/write/web_fetch/agent/memory/skill_manage/task_stop 精渲染（agent prompt 在结果前）；未知 name 但有 detail → 通用结构化卡片按 key 渲染；无 detail → 降级 output 串
- 验证: component test 各工具展开分支 + 未知工具卡片 + detail 缺失降级

### R3 — 长输出两级展开（截断 + 展开全部限高滚动 + 收起 + 源头截断标注）+ 浏览器验收 — DONE

- 步骤: 大字段（bash stdout/stderr、write content、web content、edit diff）前端阈值截断 + "展开全部" → max-height+overflow auto + "收起"；detail.truncated===true 末尾标注源头截断；global.css 补样式
- 验证: component test 截断/展开/收起/源头截断标注；npm run build；真实浏览器 1440/375 截图与 prototype 对照

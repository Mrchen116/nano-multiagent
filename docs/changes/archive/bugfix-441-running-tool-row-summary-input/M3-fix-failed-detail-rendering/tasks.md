# bugfix-441-M3: fix-failed-detail-rendering — Tasks

> 对齐: ../design.md bugfix-441-M3 行。Post-code-review 单点 fix,按 `change-impl-worker` 轻量化:一个 R1 完成 C1/C2/C3,但保留红测、实现、文档证据链。

## 目标

修复 M2 后出现的 failed tool detail 展开体渲染问题:异常 reconcile 会让 `call.status=failed` 的 payload 保留 start-side 参数 `detail`,前端 bespoke 卡必须识别顶层 failed 状态,不得把参数片当成功完成 detail 渲染。

## 退出标准

- [x] `ToolDetailBody` / bespoke 卡把顶层 failed 状态纳入展开体渲染。
- [x] `agent` / `memory` / `skill_manage` / `task_stop` 在 `call.status=failed` 且 detail 只有参数片时,不显示 `✓` / completed / 成功体。
- [x] failed reconcile 仍保留参数区:agent prompt、memory action/target/content、skill action/name、task_id。
- [x] running 态 gate 与 completed 成功态展示不退化。
- [x] 增加 failed-with-start-detail vitest 回归用例,窄口前端测试全绿。

## 测试策略

- 被测行为(来自退出标准): failed + start-side detail 展开体;参数仍可见;成功标记隐藏;running/completed 邻近状态不退化。
- 已有测试在: `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx`(扩展),原因:该文件已有 ToolCallsPanel 展开体、running gate、success-false failure 回归。
- 落层/目录/marker: frontend vitest/jsdom, marker: 无。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 临时 Vite HTML fixture 已删除;浏览器截图为本地 ignored artifact `src/IM/frontend/output/playwright/bugfix-441-M3-failed-detail.png`。

用户路径分类: bug-regression

## UI 状态矩阵

| 状态 | 覆盖 |
|---|---|
| default | completed memory/skill success 既有用例保持 `✓` 与内容展示。 |
| loading | N/A,本 fix 不涉及异步加载 UI。 |
| running | 既有 running web_search/agent/memory/skill/task_stop 用例继续覆盖参数可见且无完成标记。 |
| empty | N/A,本 fix 不改空列表/空结果语义。 |
| error | 新 failed-with-start-detail 用例覆盖 failed 参数片;既有 error-only / success=false 用例覆盖失败详情。 |
| disabled | N/A。 |
| submitting | N/A。 |
| permission denied | N/A。 |
| long content | 既有 long output 用例不受影响。 |
| missing/nullable data | 新 failed 参数片用例覆盖缺少结果字段的 detail。 |
| mobile viewport | N/A,本 fix 不改响应式布局。 |
| desktop viewport | 浏览器验收使用 1280x800。 |
| dark mode | N/A,项目当前测试不覆盖主题切换。 |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| failed agent 参数片显示 `✓ completed` | vitest 断言 prompt 可见、`.chat-tool-detail-agent-result` 不渲染 | 是 |
| failed memory 参数片显示 `✓` 成功头 | vitest 断言 action/target/content 可见且无 `✓` | 是 |
| failed skill_manage 参数片显示 `✓` 成功头 | vitest 断言 action/name 可见且无 `✓` | 是 |
| failed task_stop 参数片显示 `✓ status · task_id` | vitest 断言 task_id 可见且无 `✓` | 是 |
| running/completed 邻近状态退化 | 既有 running gate、completed success、success=false、reducer 用例 | 是 |
| 真实浏览器中展开体与测试一致 | Vite + Playwright 临时 fixture,检查 console/network + 截图 | 否,记录在 progress |

## Roadpoints

### R1 — failed start-detail rendering

- 状态: DONE
- 步骤: 补 failed-with-start-detail 红测;让 bespoke 卡接收 `isResultPending` 而不是只看 running;failed 且 detail 无终态字段时只渲染参数区;跑窄口 vitest/build/浏览器验收。
- 验证: `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts`

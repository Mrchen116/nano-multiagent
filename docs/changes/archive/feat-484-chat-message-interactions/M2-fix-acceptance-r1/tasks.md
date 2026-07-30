# feat-484-M2: 修复 chat message interactions round 1 验收问题 — Tasks

> 对齐: ../design.md v1（M1 实现后 round 1 验收问题修复）

## 目标

修复 M1 round 1 验收中发现的 P0 实现 bug、补全 P1 缺失回归测试、顺手处理 P2 小修，使 chat message interactions 在桌面/触控/键盘三态下均符合 design.md 关键决策与 spec.md 验收标准。

## 退出标准

- [x] `npm run test -- --run` 全绿（含新增回归测试）。
- [x] `npm run build` 成功。
- [x] `git diff --check` 无空白错误。
- [x] P0 bug 全部修复并在 progress.md 逐条记录根因+修法+证据。
- [x] P1 测试补全并合入现有测试文件。
- [x] 隔离真栈浏览器验收：链接/代码内右键原生、菜单 Escape/外部点击关闭、连续两个 code copy、resize 后菜单行为，证据落 `evidence/`。

## 测试策略

- 被测行为（来自退出标准/问题清单）：
  - 复制协调器异步 ownership（same-pane 新 surface、会话切换、A→B→A、newer attempt、旧 notice timer）。
  - Text node / Element 路径上的原生交互 target 判定。
  - 连续 code block copy 按钮行为。
  - context menu 外部点击/Escape 关闭、焦点首个 item、roving 键盘导航。
  - toolbar CSS 可见性（无障碍树可达）。
  - 链接分类（bare relative、protocol-relative）与 isNamedExternal 复用。
  - 有序列表 `li[value]` 后续编号。
  - MessagePane unmount 副作用清理。
  - external/same-origin/code block 组件级渲染属性。
- 已有测试在：`src/IM/frontend/src/features/chat/components/message-pane.test.tsx`、`message-content-policy.test.ts`（扩展）。
- 落层/目录/marker：前端组件测试，无 marker。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据：真浏览器截图/录屏（`evidence/`），不进套件。

### 用户路径分类

- bug-regression：P0 bug 修复与 P1 回归测试。
- normal-ui：菜单键盘导航与 toolbar 可见性。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | toolbar 默认隐藏但可达；普通阅读态无菜单。 |
| hover/focus | toolbar 显示；链接/代码 focus 可见。 |
| error | Clipboard reject 显示失败提示，保留菜单。 |
| disabled | Branch offline/pending aria-disabled。 |
| mobile viewport | More button + action sheet。 |
| desktop viewport | toolbar + context menu。 |
| long content | N/A（本次不改布局）。 |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 复制协调器异步 ownership | 组件测试（deferred Promise） | 是 |
| 原生 target / 选区判定 | 策略单元测试 | 是 |
| 链接分类边界 | 策略单元测试 | 是 |
| 菜单键盘/关闭行为 | 组件测试 + 真浏览器 | 是 |
| toolbar 可见性 | CSS 检查 + 真浏览器 | 否（样式） |
| 连续 code copy | 组件测试 + 真浏览器 | 是 |

## Roadpoints

### R1 — 修复 P0 实现 bug

- 状态: DONE
- 步骤:
  1. 用 ref 持有最新 surface token，修复 `publishCopyResult` 闭包读旧 state。
  2. 修复 `isNativeInteractiveTarget` Text node / Element 路径判定。
  3. 诊断并修复连续 code copy 第二次不生效（测试在第一次点击后 element handle 失效，改为第二次点击前重新查询）。
  4. 补全 context menu document 级 outside-click/Escape + focus first item + roving 导航。
  5. toolbar CSS 改 opacity/pointer-events，保留无障碍树。
  6. 修复 `classifyChatLink` bare relative 与 protocol-relative 边界。
  7. 从 policy export `isLabelJustUrl` 并在 `<a>` renderer 复用。
  8. 修复 `serializeMessageBody` 有序列表 `li[value]` 后续编号。
  9. window resize 关闭 context menu。
  10. MessagePane unmount cleanup notice timer + mounted ref guard。
  11. 补回 `draftSeed` effect 完整逻辑。
  12. `messages.find` 失败安全处理。
  13. `onCopyCode` 用 `useCallback` 稳定引用。
- 验证: `npm run test -- --run` 中 message-pane / content-policy 全绿；`npm run build` 成功。

### R2 — 补全 P1 测试

- 状态: DONE
- 步骤:
  1. copy coordinator deferred-Promise 异步 ownership 测试（WIP 骨架合法化）。
  2. 跨 text node 选区的 caret-point 内/外策略测试。
  3. 组件级测试：external link target/rel/aria-label、same-origin 无 target、code block copy button、inline code 无按钮。
  4. 补全 `classifyChatLink` bare relative / protocol-relative / same-origin / cross-origin 边界测试。
  5. 补全 `serializeMessageBody` 显式 `li[value]` 后续编号测试。
- 验证: 新增测试通过；message-content-policy 45 tests / message-pane 103 tests 全绿。

### R3 — P2 顺手小修 + 门禁

- 状态: DONE
- 步骤:
  1. zh.json copyError 去句号。
  2. `recordPointer` 改 `onPointerDownCapture`。
  3. 删 `looksLikeUrl` 死代码；删除 `classifyChatLink` 未使用的 `label` 参数并更新调用点/测试。
  4. 收敛 context-menu `onFork` guard 为单一来源（低风险）。
  5. 修复 `r7-browser-qa.js` async filter 缺陷。
  6. 跑 `npm run test -- --run`、`npm run build`、`git diff --check`。
- 验证: 全绿。

### R4 — 真浏览器验收与证据

- 状态: DONE
- 步骤:
  1. 按 design.md Runbook 起隔离真栈 `./scripts/e2e-up.sh`。
  2. 自测：链接/代码内右键原生、菜单 Escape/外部点击关闭、连续两个 code copy、resize 后菜单行为。
  3. 截图/录屏落 `evidence/`。
- 验证: 真浏览器行为符合 design；progress.md 记录证据路径。

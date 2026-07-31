# feat-484 Design Review

## 评审结论

**Approved**

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| WARNING | 0 |
| SUGGESTION | 0 |

Gate 2 通过。当前 `design.md` 已把输入事件所有权、消息动作模型、正文复制投影、链接分类、代码复制、浮层/Clipboard 异步所有权与回焦规则收敛为可实现且可验收的单一方案；它与冻结的 `spec.md`、delta-spec、当前生产接线和 prototype 一致，没有遗留会迫使 worker 自行补架构决策的空白。

本结论只适用于下方哈希对应的冻结产物；任一受审产物后续变化都需要新的独立完整复审。

## 评审独立性与范围

- Reviewer 在形成判断前从零读取 `spec.md`、`design.md`、`prototype.html`、`specs/im/web-chat-ux.md`、`M1-impl/.gitkeep`，并核对当前生产代码、canonical specs、既有测试与依赖；旧 `design-review.md` 仅在结论形成后作为待覆盖文件确认，不作为本轮证据。
- 本轮只评技术方案质量，不验证尚未发生的 M1 实现，也没有修改 spec、design、prototype、delta-spec、代码或 M1 skeleton。
- `M1-impl/.gitkeep` 为空符合 design 阶段骨架约定，不代表缺少验收证据；实现证据按 `design.md:419` 在 M1 阶段落盘。
- 既有 prototype 通过当前已安装的 Playwright/Chromium 做了只读状态检查；未启动服务、未安装依赖。该检查只验证原型契约可观察性，不能替代 M1 的真栈 Chromium/WebKit/Safari 矩阵。

## 冻结产物快照

| Artifact | SHA-256 |
|---|---|
| `spec.md` | `6f39958536200cdac4b167936ed29899bd126df11d28750e3dd46d9b08b224a1` |
| `design.md` | `9983a9030bee65a609a3aaf4308c6aa1afca16b7757a622e507916d1a8e6dbb9` |
| `prototype.html` | `5436ef2f27c0a0d1ff69c68b80430300bc8825c016b1bf022b6c15a00fe29730` |
| `specs/im/web-chat-ux.md` | `fd7f65a1484889a0030405382a88556223b8ab41e12d2ab9d495e9016a5a88a9` |
| `M1-impl/.gitkeep` | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` |

## 现状断言核验

| 方案所依赖的现状 | 独立证据 | 判断 |
|---|---|---|
| `/chat` 与 `/chat/:conversationId` 都进入唯一生产聊天工作区 | `src/IM/frontend/src/app/router.tsx:31-32` | 成立；没有平行页面风险 |
| `ChatWorkspacePage` 把真实 conversation、timeline、fork 状态与响应式信息传给 `MessagePane` | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:1087-1120` | 成立；数据接线可沿用 |
| `isMobile` 只是 `<768px` 布局判定，不能代表输入 modality | `src/IM/frontend/src/shared/hooks/use-is-mobile.ts:3-15`；`design.md:89-95` | 设计正确分离 layout 与 event ownership |
| 当前生产只有一条 `MessagePane` / `MessageBubble` 实现路径 | `src/IM/frontend/src/features/chat/components/message-pane.tsx:160,570-579,677`；全仓生产路径检索无替代实现 | 变更落点唯一 |
| 既有 fork 资格由 direct chat、completed Agent message、`kernel_message_id` 决定 | `src/IM/frontend/src/features/chat/components/message-pane.tsx:707-715` | `design.md:128-142,263` 正确复用，不重定义后端语义 |
| 当前气泡无条件接管右键，并用 600ms touch timer 打开自定义菜单 | `src/IM/frontend/src/features/chat/components/message-pane.tsx:716-776` | 设计处理的是根因：移除事件抢占，而非给旧菜单加补丁 |
| 当前“复制”直接写入原始 `message.content` | `src/IM/frontend/src/features/chat/components/message-pane.tsx:779-792` | 需要正文 DOM 投影的论证成立 |
| 当前 Markdown 已使用 `react-markdown` + GFM，但没有 link/code component override | `src/IM/frontend/src/features/chat/components/message-pane.tsx:1013-1089` | 在现有 renderer 扩展点实现最小 |
| user inline renderer 不提供 Markdown link；本次 link 范围只要求 Agent Markdown | `src/IM/frontend/src/features/chat/components/message-pane.tsx:1098-1150`；`spec.md:181` | 没有漏掉冻结范围 |
| 当前 CSS 抑制 coarse-pointer 选区与 touch callout | `src/IM/frontend/src/styles/global.css:1720-1737` | `design.md:81-107` 与 M1-R1 覆盖必要移除 |
| 当前中英文资源缺少新增动作文案，中文仍直接显示 `fork` | `src/IM/frontend/src/i18n/zh.json:520-526`；`src/IM/frontend/src/i18n/en.json:523-529` | `design.md:223-227` 的 i18n 增量必要且充分 |
| 仓内已有 Radix Dialog 与 Playwright 依赖 | `src/IM/frontend/package.json:14,38` | action sheet 与真浏览器验收不需引入第二套基础设施 |
| `react-markdown` 当前默认 URL transform 只放行安全协议并清空危险目标 | 当前安装包 `react-markdown/lib/index.js:124`；`design.md:184-203` | classifier 接收 transform 后 href 的边界成立 |
| 既有测试已覆盖 fork 资格/disabled、防重复以及旧右键/长按/Markdown 行为 | `src/IM/frontend/src/features/chat/components/message-pane-fork.test.tsx:71-129`；`src/IM/frontend/src/features/chat/components/message-pane.test.tsx:857-995,1881-1988` | M1-R7/R8 明确保留或替换正确回归面 |

## Spec 原子覆盖台账

### 澄清与用户场景

| 原子 | 设计投影 | 结论 |
|---|---|---|
| Q1：正文阅读和原生内容交互优先，消息动作按需出现 | `design.md:81-142` | 完整 |
| Q2：一次覆盖桌面/移动文本选择、复制、链接、轻量动作、代码、反馈和键盘可达性 | `design.md:81-235`，M1-R1–R6 `design.md:411-416` | 完整 |
| 当前聊天、阅读位置与 draft 不应被外链、复制失败或反馈破坏 | `design.md:213-226,323,373-375`，M1-R3/R4 | 完整 |

### Requirement 1：原生文本选择与局部复制

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| 桌面局部复制只得到选区 | 原生 Selection/Clipboard 不被替换；`design.md:91-106,411` | 完整 |
| 选区内右键保留浏览器菜单 | caret point 与 Selection Range 精确比较，失败保守 native；`design.md:92-106,246-247` | 完整 |
| 移动长按恢复系统选择 | touch/pen/unknown 永不 `preventDefault()`，并移除旧 CSS 抑制；`design.md:92-95,411` | 完整 |

### Requirement 2：消息动作可发现且不干扰阅读

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| desktop hover/focus toolbar | opacity/focus-within 保留可访问树；`design.md:109-126,223` | 完整 |
| 无选区普通区域 mouse 右键短菜单 | 精确 modality、selection、native target 路由；`design.md:91-106,224` | 完整 |
| link/code/选区右键保持原生 | `shouldKeepNativeContextMenu` 的 native target 和 caret 契约；`design.md:247` | 完整 |
| compact/coarse More 打开短 action sheet | More 始终渲染、media query 决定显示、Radix Dialog 承担 modal；`design.md:117-126,225` | 完整 |
| 普通阅读态不常驻动作墙 | toolbar 默认透明、More 只在 compact/coarse 显示；`design.md:115-126,223` | 完整 |

### Requirement 3：整条复制与反馈

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| 富文本结构可复用、具名链接含真实地址 | 单一 DOM serializer 与逐字符 fixture；`design.md:144-182,248` | 完整且无歧义 |
| 页面已有选区时仍复制目标整条消息 | action 显式传 body ref，不查询全局 Selection；`design.md:253-258` | 完整 |
| 排除头像、状态、过程、token、授权卡和控件 | `.chat-message-body` 唯一输入 + `data-clipboard-exclude`；`design.md:152-159,265-285` | 完整 |
| 成功短反馈 | latest attempt/generation/surface guard 后显示约 1.6s notice；`design.md:219-226,257-260` | 完整 |
| 失败明确、可重试且不改聊天位置 | 同一 ownership guard，保留 surface，约 4s error；`design.md:226,373-374` | 完整 |

### Requirement 4：链接自然导航

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| 外部 HTTP(S) 新标签 | 真实 anchor + `_blank` + `noopener noreferrer`；`design.md:184-203` | 完整 |
| IM 内链/同源资源当前标签 | same-origin/relative/hash 使用无 target 的真实 anchor，不猜 SPA route；`design.md:188-201,323` | 完整 |
| 具名外链提示、裸 URL 不重复 | URL normalization + 非 selectable pseudo-element + 本地化 aria-label；`design.md:203` | 完整 |
| hover/focus/right-click/mobile long-press 保留浏览器能力 | 真实 anchor 且 native-target 路由；`design.md:188-203,247` | 完整 |
| unsupported 不伪装为可用链接 | 默认 sanitizer 后四分类，空/malformed/tel 等输出可见文本；`design.md:190-201,245` | 完整 |

### Requirement 5：代码块精确复制

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| 单个 fenced block 只复制自身代码 | `pre` renderer 与 `extractCodeText`，只去一个 renderer 尾换行；`design.md:205-211,249` | 完整 |
| 键盘与指针得到同一内容/反馈 | 真实 button 进入同一 Pane copy coordinator；`design.md:223,256`，M1-R5/R6 | 完整 |

### Requirement 6：跨设备与输入方式一致

| Scenario | 方案与验收证据 | 结论 |
|---|---|---|
| keyboard focus、可理解名称、关闭回焦 | toolbar/context menu/Radix sheet 的 focus 模型与 connected-trigger 降级；`design.md:221-227,260-261` | 完整 |
| 中英文一致且中文不出现孤立 `fork` | 明确冻结中英文 label 与 disabled reason；`design.md:133-142,227` | 完整 |
| More/action row 触控稳定 | 不小于 44×44px；`design.md:225`，M1-R6 | 完整 |

### 范围与非目标

| 约束 | 设计证据 | 结论 |
|---|---|---|
| 只改变 Web IM 前端可观察行为 | `design.md:229-235,356-365` | 遵守包边界，无 Kernel/Gateway/CLI delta |
| fork 只改变入口与反馈，不改变资格、后端、成功跳转 | `design.md:128-142,231-235`，M1-R7 | 遵守 |
| 不新增 reaction/reply/forward/share/edit/delete 等消息能力 | action model 仅 `copy-message` + 可选 `fork`；`design.md:128-142,263` | 遵守 |
| 不造选择器、选区浮条、多复制格式、链接预览或自定义浏览器菜单 | `design.md:83-86,144-150,184-190` | 遵守 |
| 不动附件、消息 schema、发送、分页、实时流、过程盘、授权卡、token | `design.md:229-235,267-285` | 遵守 |
| 不重做气泡、布局或主题 | prototype grounding 与 `may-adapt` token 约束；`design.md:331-354` | 遵守 |

## Delta-spec 核验

| Delta atom | Canonical grounding | 设计投影 | 结论 |
|---|---|---|---|
| MODIFIED：消息气泡复制与长按/右键菜单，10 个 Scenario | canonical `docs/specs/im/web-chat-ux.md:135-150`；delta `specs/im/web-chat-ux.md:3-66` | D1–D3、D6；M1-R1–R3/R6 | 合法修改既有同名 Requirement |
| MODIFIED：desktop/mobile 滚动与交互一致，3 个 Scenario | canonical `docs/specs/im/web-chat-ux.md:152-164`；delta `specs/im/web-chat-ux.md:68-84` | 不改滚动路径；More 复用既有 fork；共享 action model | 完整保留未变行为并修改相关交互 |
| ADDED：链接按目标类型自然导航，5 个 Scenario | delta `specs/im/web-chat-ux.md:86-117` | D4；M1-R4 | 可观察行为完整 |
| ADDED：Agent code block 独立复制，2 个 Scenario | delta `specs/im/web-chat-ux.md:119-131` | D5；M1-R5 | 可观察行为完整 |
| canonical 收尾 | 当前 `docs/specs/im/spec.md:23-31` 的 Web Chat UX 计数为 10 | `design.md:365` 明确归并时改为 12，design 阶段不提前改 canonical | 正确 |

delta 只描述终端用户可观察行为，没有把 React、DOM、Radix 或 Clipboard token 等实现细节写入规范；HTTP/WS、Gateway、Kernel、CLI 均明确无 delta，符合仓库跨包边界。

## 决策、接口与数据流台账

| 决策 | 下游无需再猜的内容 | 判断 |
|---|---|---|
| D1 输入所有权 | event facts、Control-click、keyboard `button < 0`、recent pointer 的同消息/1500ms/8px/secondary-kind 约束、caret API fallback、native targets | 足够具体，可纯测、可真浏览器验收 |
| D2 共享 action model | toolbar/context menu/More 的表面选择；Branch 四状态、同一 disabled reason 和执行拒绝 | 一个语义来源，不会三套漂移 |
| D3 正文 serializer | 唯一 DOM root、排除边界、block/list/table/code/link 规则和精确 fixture | 无格式自由发挥空间 |
| D4 link classifier | transform 后 href 的四分类、真实 anchor 导航、外链可访问提示 | 不复制 Router 或 URL sanitizer |
| D5 code extractor | block/inline 边界与只去一个结构性尾换行 | 精确且小 |
| D6 Pane coordinator | generation、attempt、surface、notice token；success/error close 策略；connected-trigger 回焦；Radix ownership | 异步竞态与 modal 生命周期已拍死 |
| D7 前端边界 | 无 schema/API/backend/store 变更 | 变更面与根因一致 |

`message-content-policy.ts` 只承载五个互相耦合、无副作用且值得纯测的内容策略；`MessagePane` 继续唯一拥有 UI surface 与 Clipboard 副作用，`MessageBubble` 显式上交 DOM ref/identity。接口输入、输出和调用方已逐项冻结于 `design.md:241-263`，主流程又以时序图覆盖成功、失败、stale completion 与回焦（`design.md:287-323`），实现 ownership 清楚。

## Prototype 与 Milestone 核验

| 核验项 | 证据 | 结论 |
|---|---|---|
| desktop 安静态、hover/focus toolbar、短 menu | `prototype.html` 的 desktop message/action DOM 与状态脚本；`design.md:327-349` | must-match 状态存在 |
| mobile 390×844 More、44px target、modal sheet | `prototype.html:904` action sheet；`design.md:352` | must-match 状态存在 |
| 1024×768 hybrid 同时保留 toolbar + More | `prototype.html:686-691` | must-match 状态存在 |
| Branch available/offline/pending/non-candidate 与中英文 reason | `prototype.html:1035-1036` 及控制状态；`design.md:347,352` | 三表面状态可评审 |
| external/raw URL、product route、同源 resource、unsupported target | `prototype.html:836-847` | D4 的所有关键分类都有可见样例 |
| code copy 与 rich-body serializer | `prototype.html:856,1194-1251,1370` | D3/D5 有交互样例，且当前 fixture 语义一致 |
| macOS Control-click modality | `prototype.html:1164-1188`，其中 `control-primary` 在 `1170` | 旧遗漏已补齐 |
| 单 M1 是同一气泡的紧耦合垂直切片 | `design.md:401-407` | 约 8 文件、600–900 行，不命中拆分硬触发；无横切 milestone |
| M1-R1–R6 reviewer exit criteria | `design.md:411-416` | 逐项覆盖所有 spec Scenario 与 must-match prototype |
| M1-R7–R10 worker exit criteria | `design.md:417-420` | fork 回归、策略/组件测试、真栈证据、build/diff check 均明确 |
| Browser matrix 与证据留存 | `design.md:367-399,419` | Chromium desktop/hybrid、WebKit mobile、Control-click、Selection、Clipboard exact string、focus trap 均有明确验法和环境限制记录要求 |

只读 Chromium 原型检查额外确认：1440 宽屏 toolbar 在普通态仍留在可访问树但视觉隐藏、More 隐藏；390 mobile toolbar `display:none`、More/code copy 触控区不小于 44px、sheet 打开后背景隔离且首动作获焦；1024 hybrid 同时显示 toolbar 能力与 More；offline Branch 在所有表面保留一致 `aria-disabled` 与本地化原因。原型因此足以作为结构和状态参考；真实产品行为仍由 M1-R9 的真栈证据裁决。

## 四角架构进攻

| 角度 | 攻击问题 | 证据与结论 |
|---|---|---|
| Ownership / dependency direction | 是否把 feature 规则塞进全局层、形成跨包反向依赖或平行数据源？ | 否。策略留在 chat feature，Pane 继续拥有副作用，Workspace 继续拥有 conversation/fork；无跨包 import、API 或 schema 变更。 |
| Should this module exist? | 删除 `message-content-policy.ts` 后是否更简单？ | 否。删除会把 modality、caret、URL、DOM serialization、code whitespace 五类必须一致的纯规则散回 JSX 和事件 handler。当前模块是一个深接缝，不是包装壳。 |
| Deep vs. shallow / reuse | 是否重造 parser、router、sanitizer、modal、clipboard framework？ | 否。方案复用 ReactMarkdown 默认 transform、真实 anchor、浏览器 Selection/Clipboard、既有 Radix Dialog 和当前 fork callback；新增抽象只隐藏跨浏览器内容策略复杂度。 |
| Root cause vs. patch | 是否只是给错误交互继续加例外和 hardcode？ | 否。方案撤掉 unconditional `preventDefault`、touch timer 与选择抑制 CSS，让浏览器重新拥有内容；产品动作改为独立表面。复制则从错误的 Markdown source/整卡边界改成唯一正文 DOM projection。 |

四个角度均未发现 surviving issue。

## Issues

无。

## Gate 2

**Approved — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**

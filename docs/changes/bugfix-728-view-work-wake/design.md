# bugfix-728: As-built Design

> 本文在实现后根据代码和实际验证整理，不是事前 Gate 2 设计。用户尚未亲自验收，unit 保持 active。

## 实现范围

- Base: `eeaea47921806936da20e78c9ed96167716f5037`（origin/develop）。
- 版本范围：本分支 `fix/473-view-work-wake`；实际验证版本与后续提交对应见 [review.md](review.md)。
- 受影响模块：Web 聊天气泡链接、Work 读取/分页/展开与定位；IM 持久 Work 查询。
- 无运行时、模型输入、iOS 或生产部署变更，无数据迁移。

## 最终结构

### 组件与职责

- `message-pane.tsx`：仅对既有 View Work 入口追加该消息 ID，保留 Agent 选择与可见资格。
- `WorkRecords.view`：在已获授权的 Agent 内，从持久 `message_sent` 事实解析真实主执行与轮次；首屏从目标轮次（包含目标）开始，不依次扫描最新到历史的每一页。
- `WorkRecords.turns`：保留 `before_turn` 排他续页；新增内部 inclusive 初始锚点，首屏目标与后续历史无重复遗漏。
- `AgentWorkPanel`：按消息 ID 隔离查询缓存；目标确认后关闭已保存子面板，展开对应轮次；完整首批过程就绪后滚动一次，后续同步不打断用户阅读或重新展开用户折叠的记录。
- `Turn`：沿用 summary / 按需 items，程序展开也会读取过程；以导航 token 限制一次滚动。

### 调用链与数据流

聊天回复 → `/settings/agents/<agent>?view=work&message_id=<message>` → 已有授权 Work API（附同一消息 ID）→ Agent 范围内投递事实 → `focus={session_id,turn_id}` 和含目标的摘要页 → 展开 → 真实 items → 滚动到目标。

Work 页继续按同一消息锚点选出的执行读取更早页；`查看最新轮次` 清除锚点，恢复原始最新页查询。主执行当前状态与最近用量仍取当前主执行，不把历史已完成唤醒误报为当前空闲。历史主执行被保留时亦可经其真实投递事实定位，当前主执行身份不被更换。

### 状态、数据与兼容性

- 复用历史 journal，无需新加消息列、回填、时间邻近匹配或 LLM 内容推断。
- 不含 `message_id` 的既有 Work 请求和历史分页契约不变；旧客户端无需升级才能继续读取。
- 找不到关联时返回 `focus: null`，仍显示已有记录，并提示“该回复的工作记录尚未同步或不可用。”后续 Work 同步可重取并定位；读取失败沿用既有重试。
- 资格沿用 `registerWorkRoutes.profile`：有效 Global profile、空间资格及 PA 本人限定。消息锚点不会授予原聊天/附件权限，也不会触发 Agent 执行。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 从实际投递事实反查，不新增来源字段 | 既有历史已经具备精确关联；避免只修新消息和猜测同名唤醒 | `apps/im-server/src/work-records.ts` |
| 目标页直接从历史目标开始，并可返回最新 | 默认20轮之外仍立即可达，避免逐页请求所有历史 | `WorkRecords.turns/view`、`AgentWorkPanel` |
| 首批过程就绪后只滚动一次 | 浏览器实测发现空摘要尚无足够高度，提前滚动会无效；同步更新不应拉回正在阅读者 | `Turn` focus effect |
| 不增加原型/大改布局 | 明确的导航恢复目标，沿用现有 Work 卡片与工具显示即可 | Web 真实浏览器验证 |

## 失败路径、风险与回滚

- 消息先于 Work 同步、旧记录缺少关联：说明未知而非猜测；同步/可见恢复后继续既有读取。
- 节点离线：已保存 Work 仍可读，活动状态仍降级未知；不要求在线重新执行。
- 大过程：保留既有 items 分页，初次只读取所展开目标的首批；完整后续内容仍由“加载更多过程”取得。
- 回滚代码即可，未改 schema 或写入格式；已保存聊天和 Work 不受影响。

## 与初始意图的差异

无业务范围变化。增加必要的“尚未同步或不可用”提示和“查看最新轮次”出口，避免失配或被困在历史页；不新增发信、配置或访问权限。

## 本次审查安排（按实际实现校正）

| 必须回答的问题 | 能力与所需证据 | 证据与缺口 |
|---|---|---|
| 多次同名唤醒能否按真实消息分别定位；历史/分页是否正确；资格不扩张 | 独立 change-code-review，diff + 真实socket回归 | 自动化包含25轮超出最新页、重复定位、缺失、items与授权；固定模型派发能力差异见 review |
| 真实聊天点击能否直接看到目标记录及工具，重复历史点击是否稳定 | 作者前端体验自检，daily真实模型回复 + Chromium连续点击/截图 | 真实入口与操作证据见 review；作者自测不代替用户实际验收 |

## 验证定位

- 用户验收：尚未收到实际试用确认；禁止归档或标完成。
- 自动化：`work-message-focus.test.ts`、`agent-work-panel.test.tsx`、`message-pane.test.tsx`；完整结果见 review。
- 运行证据：隔离 daily 栈、浏览器及本地输出见 review；本地日志/截图不提交。
- 无一次性部署迁移，不生成 deployment-prompt。

## Canonical 文档影响

- Delta: [specs/im/agent-work.md](specs/im/agent-work.md)。
- 待审查及用户确认后归并 `docs/specs/im/agent-work.md`，当前尚不覆盖 current spec。

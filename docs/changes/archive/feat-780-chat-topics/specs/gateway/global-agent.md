# gateway/global-agent Specification (delta for feat-780)

## ADDED Requirements

### Requirement: Global 的话题按一等 target 独立收发，未关注的话题不进 Inbox

Global/PA 不按话题新建主 session，但 Agent 工具侧将话题作为一等 `target`（`<chat_id>:<8位短消息id>`），Inbox 按 `target` 拆行且不带正文 preview；原聊天发现、只读查/搜与话题关注分别由 `conversations`、`read_messages`、`search_messages`、`threads` 承担，所有需由 Agent 填写的原子编号长度不超过 8 位。

#### Scenario: 未关注的群话题没有 Inbox 行
- **GIVEN** Global Agent 没有关注该群话题，消息也没有 @ 或引用它
- **WHEN** 话题里出现新回复
- **THEN** Inbox 不增加这条消息，十分钟背景里也没有它

#### Scenario: 话题在 Inbox 中按独立 target 呈现与消费
- **GIVEN** 同一群的主时间线和已关注话题各自有未读消息
- **WHEN** Global Agent 收到唤醒通知或调用 `inbox(check)`
- **THEN** 主时间线 `c_xxx` 与该话题 `c_xxx:yyyyyyyy` 各占一行，均不带消息正文 preview，可分别独立调用 `inbox(read, target=...)`
- **AND** 仅首次进入陌生话题（或压缩后首次回来）时附带一次根消息、有限条最近回复与显式截断标志；持续跟进时只交付新消息本身

#### Scenario: 显式 target 落点与话题级复核
- **WHEN** Global 接下一件需要确认和结果的请求，并以 `send_message(target="c_xxx:yyyyyyyy")` 发出确认和结果
- **THEN** 这些消息只出现在该话题；传入主时间线 `target="c_xxx"` 则发往主时间线，宿主不静默改写目标
- **AND** 向话题发送前的 `held_for_revalidation` 复核仅检查该话题自身是否存在未读高优消息，不被主时间线或兄弟话题的新消息误拦

#### Scenario: 历史读取与搜索透出话题地址，Agent 可管理关注
- **WHEN** Agent 调用 `read_messages(target="c_xxx")` 读主时间线、调用 `read_messages(target="c_xxx:yyyyyyyy")` 读话题、或调用 `search_messages` 命中话题回复
- **THEN** 主时间线有回复的根消息带 `thread: { target, reply_count, latest_at }`；读话题返回根消息与回复；搜索命中话题直接返回话题 `target`
- **AND** Agent 可通过 `threads(list/follow/unfollow)` 查看或管理关注；取消关注时话题内留一行人类可见提示，后续再被 @ 或引用自动恢复关注并附带提醒

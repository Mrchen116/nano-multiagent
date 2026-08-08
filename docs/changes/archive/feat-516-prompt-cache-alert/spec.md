# feat-516: Gateway prompt cache 低命中告警

## Relations

- Related: feat-439

## 原始需求

> 我担心代码设计有一些问题，导致大模型的input prompt缓存率比较低。所以希望搞个告警到日志中。如果token数比较大，缓存命中率比较低，就触发一个告警输出。Token数比较大是因为，比如说他刚开始聊，那肯定没有缓存呀，那肯定缓存命中率低呀，那是正常的。但如果是Token数量比较大的话，那他大概率前面已经聊过了，所以他有可能是有问题的。而且这个时候未缓存输入成本也比较高。

## 澄清记录

- Q1: 第一版是否按一条助手回复的累计输入量判断，并在总输入 `≥100,000 tokens` 且缓存命中率 `<50%` 时写一条 warning？
  A(原话): 我没懂你的累积是什么意思。我觉得就简单点，就调大模型的时候，拿到返回里面会有一个input token的信息吗？那这个input token如果超过，比如说30K，然后缓存命中率又低于80%，那我觉得就应该是有问题的。你这个什么累积，是个啥呀？我感觉是不是搞复杂了？
  Agent 解读: 每次模型调用独立判断；输入 token 超过 30K 且该调用缓存命中率低于 80% 时告警，不按一条助手回复累计。

- Q2: 有些 provider 可能只返回 input token、却不返回缓存命中数据。此时是否不告警？
  A(原话): 所有都会返回缓存命中数据吧？如果不返回的话，不报警。注意我这里说的input token是指输入的token的意思，不一定那边返回的是这个字段。
  Agent 解读: 告警只在 provider 明确提供缓存命中数据时计算；缺失数据不告警。输入 token 按本次请求的总输入语义归一，不依赖 provider 原始字段名。

- Q3: `30K / 80%` 第一版要固定为默认规则，还是放进 Gateway 配置让每台机器可调？
  A(原话): 不用配置，简单点。
  Agent 解读: 阈值固定为输入 token 超过 30K 且缓存命中率低于 80%；不新增 Gateway 配置项。

- Q4: 告警日志是否只记录可排查的元数据——模型、输入 token、缓存命中 token 与命中率——并且绝不写入 prompt 正文？
  A(原话): 还要记录对应的session id，方便排查
  补充(原话): 对应哪个agent id也要吧？不然靠session id能找到对应session 的jsonl吗
  Agent 解读: 告警记录模型、agent_id、session_id、输入 token、缓存命中 token 与命中率；不记录 prompt 正文或用户内容。只写 Gateway 日志，不新增 Web IM 提示、推送通知或统计面板。

## 用户场景

Gateway 运维者怀疑长对话的 prompt 前缀没有稳定命中缓存，导致某些模型调用既慢又贵。他不需要逐条翻看模型请求；当一次模型调用的输入已经超过 30K token、但缓存命中率又低于 80% 时，他在 `gateway.log` 看到一条 warning，其中有模型、agent_id、session_id、输入量和缓存命中数据，能直接关联到对应 Agent 的会话继续排查。

刚开始的新对话通常没有缓存，输入量却很小；这种正常的冷启动不产生告警。同样，如果 provider 没有报告缓存命中数据，运维者不会看到猜测性告警。

## 验收标准

### Requirement: 高成本低缓存命中模型调用产生可排查告警

#### Scenario: 单次模型调用输入大且缓存命中率低
- **GIVEN** Gateway 调用模型后获得该次调用的总输入 token 与缓存命中数据
- **WHEN** 总输入 token 超过 30K 且缓存命中率低于 80%
- **THEN** 运维者在 `gateway.log` 中看到一条 warning
- **AND** 该 warning 包含对应的模型、agent_id、session_id、输入 token、缓存命中 token 与命中率，但不包含 prompt 正文或用户内容

#### Scenario: 新对话或缓存命中正常时不误报
- **GIVEN** Gateway 调用模型后获得该次调用的缓存命中数据
- **WHEN** 总输入 token 不超过 30K，或缓存命中率不低于 80%
- **THEN** Gateway 不为该次调用输出此类低缓存命中 warning

#### Scenario: provider 未报告缓存命中数据
- **WHEN** Gateway 调用模型后没有获得该次调用的缓存命中数据
- **THEN** Gateway 不为该次调用输出此类低缓存命中 warning

### Requirement: 告警规则无需额外配置即可一致生效

#### Scenario: 运维者按既有方式启动 Gateway
- **WHEN** 运维者使用既有 Gateway 配置启动或重启服务
- **THEN** 告警按固定的 30K 输入 token 与 80% 缓存命中率规则工作
- **AND** 运维者无需新增或修改配置项

## 范围与非目标

- 在范围：
  - 每次模型调用独立判断输入量与缓存命中率，并在满足固定阈值时写入 Gateway warning 日志。
  - 告警记录模型、agent_id、session_id、输入 token、缓存命中 token 与命中率，不记录 prompt 正文或用户内容。
  - 缓存命中数据缺失时不告警。
- 非目标：
  - 不新增可调节的 Gateway 配置项。
  - 不在 Web IM、外部 channel 或其他通知渠道展示或推送此告警。
  - 不增加历史缓存命中率统计、趋势报表或成本计算。
  - 不为历史模型调用补写告警。

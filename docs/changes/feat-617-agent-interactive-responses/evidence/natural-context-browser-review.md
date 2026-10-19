# 私聊后台状态与群聊明确提交：本轮取证

## 范围与版本

代码candidate f63ffa73d；主模型codexOAuth:gpt-6.1-sol。旧fullOpenUI及preview修复证据保持各自范围，本轮不借旧消息证明新的首次生成。新system prompt选择规则为后续窄增量，另记录切换及实测版本。

## 清空现场与一次失败

用户明确要求清聊天记录后再验。两段隔离测试聊天c_8iutij8v/c_igsjsbh2共84条旧消息已清；对应e2e/e2e-global Node session及Global Inbox重置。首次漏清IM的agent_work_sessions全局主登记，Node新Global session 4437d74a与IM旧7c23854b冲突，导致flushWork中的main_session_conflict阻止send_message前置查询。模型生成source本身有效，数据库副本重放agent.message成功。root停止隔离栈，补清仅这两个Agent的IMwork登记/投影及对应未确认journal，四项count=0、两DB foreign_key_check=0后重启。失败原样保留本机/tmp/feat617-cleanup-fixture-failure.json，不当作功能通过；无产品代码补丁。其他聊天、Agent和node identity保留。

## 普通Agent的真实追问

- 空白聊天原话：给我讲解下冒泡排序。用户消息b8d4062660ab4c21a4d64b33cfd36fa1；实际send_message交付2ae2bff62e9b45a08e8207f9af45934c，未给交互提示。原程序初值$step=0，前进/后退/重置，可读Python实现。
- 两次下一步到$step=2，即比较4和3。只在composer手写“为什么这里要交换？”（680bb5be9f5c4a66a3bf849fa7cae8f7），未按卡片提交。发送后继续下一步到$step=3，即比较4和1。
- 持久relay.metadata.interaction_contexts固定$step=2；公开Message.interaction_reply为null；本人private draft已到$step=3。
- 实际Agent答复12b0dea209884921beba288c406eaabe completed，明确解释第1轮②的4与3，交换前[2,4,3,1]、交换后[2,3,4,1]，说明下一步再和1比较。对应发问时背景，不受后来探索污染。
- 实际移动端界面没有Draft saved/Current choices/Detach；仍可继续操作。root保存本机截图/tmp/feat617-private-context-step3.png；正式截图与独立多宽度裁决由本轮acceptance追加。

## 验证边界

完整回归backend96/377、Web99/908，Python62，typecheck/build/Web build、Ruff与docs-check通过。增量先红后绿日志位于/tmp/feat617-context-*.log。原生prompt装配6 tests/3 suites通过。独立静态R8无存活代码问题、delta aligned；独立Global/群聊产品Round4 pass（报告26f2743e0）。以上不是生产部署或全模型保证。


## 新常驻策略的实际接线与简单问题

329c64c9c增量按用户提供调研参考细化已有nano-intelligent-ui插件短policy和按需Skill，不增加生成Agent/路由。最后源码构建完成后，Node保留现有Global/群聊身份切换；普通Agent通过产品/new创建全新session 62f1cc07，清空对应聊天后原话“17+25等于多少？”（d6398eda3f114f639783a585ec8fbb87），实际回复02cfbeac63ad48a5a99a1da6925264f1为“17 + 25 = 42。”，无交互卡片，8.3s。随后再/new和清空普通聊天，用全新session 52f832a5原话“给我讲解下冒泡排序”，无UI提示；该轮实际交付827f86fc01284bfb9e54bc9e98974564，包含步骤Select/前后/重置与Python实现。真实点击下一步显示第1次比较，数组由4 2 3 1变为2 4 3 1，解释4>2而交换。无UI提示、两次均在空白聊天与全新模型session；[真实新提示移动画面](new-policy-interactive-mobile.png)与[模型原始样本](new-policy-model-samples.json)。实际Agent prompt-preview HTTP200同时包含新decision policy和group unsent-state边界，证明不是只改了未接线文本。原生DSH feature开关/能力6项通过；声明只适用于本配置样本。

独立产品Round4（报告26f2743e0）通过Global/群聊与三档实际宽度；报告细分普通群消息接收、未共享状态与明确按钮快照。新增prompt-only不改变这些数据路径/控件，按其明确范围保留。


## 两张卡片连续操作的直接补证

本轮新policy普通聊天从空白起已有真实冒泡卡827f86fc。继续普通问题“本金和年利率变化时，三年后的单利与复利差别是怎么变化的？”实际产生第二张卡eb047419，未要求界面或通过API预制。root先把利息卡本金改20000，再将原排序卡切到第2次比较，普通发问b707886f“分别说一下排序演示当前比较哪两个数，以及利息演示当前的本金和年利率。只描述现在的状态。”，随即继续改本金30000和排序第3次。

持久relay按最近操作将排序卡放前，完整保留两份不同source id与独立state：排序$s='2'；利息$p='20000'/$rate='5'。公开message.interaction_reply=null；后续私人draft为$s='3'和$p='30000'。模型最终b55285d3 completed，明确答“第2次比较，4和3；本金20000，年利率5%”。不是只选一张，也未串用或读取后来状态。见[两卡原始背景/后续状态/回复](two-card-context-sample.json)与[可见答复](two-card-answer-mobile.png)。

既有interactive-flow测试扩展一项保护两卡各自修改、最近操作排序、两份请求快照与发送后编辑不改旧快照；同文件6 tests pass，/tmp/feat617-context-multicard-test.log。补的是新缓存的数据边界，未新增平行测试文件或产品实现。

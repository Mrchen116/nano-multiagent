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

完整回归backend96/377、Web99/908，Python62，typecheck/build/Web build、Ruff与docs-check通过。增量先红后绿日志位于/tmp/feat617-context-*.log。原生prompt装配6 tests/3 suites通过。独立静态R8无存活代码问题、delta aligned；独立Global/群聊产品验证进行中。以上不是生产部署或全模型保证。

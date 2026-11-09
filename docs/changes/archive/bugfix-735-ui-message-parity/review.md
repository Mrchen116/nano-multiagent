# bugfix-735 独立审查

- `executed_base=3b8fecea6`，`validated_at=12c1105e7`。独立 reviewer `review_ui_summary` 复核 Web 终态与去重、搜索权限和旧数据、PA 双审核上下文及规范。
- F1 P2：地图标签未遍历，超出表格列宽的内容会误入搜索片段。`691889447` 修复并在原回归加入地图、表格溢出和图表非展示字段用例。独立 closure 通过，最终 aligned，无剩余 findings。
- 合并 `origin/develop=2b01098b7` 的增量只有另一 unit 的首文档。独立审查结论与定向证据继续有效，后续只补记录并归档。

## 会话列表预览补充

- `executed_base=3a07cf05b`，`validated_at=cf15b82a9`。独立 reviewer `review_ui_summary` 复核会话权限、旧卡片回填、Web 实时更新、iOS 接口消费及搜索片段。
- 隐藏面标题与附件优先两项 finding 均已关闭。预览遍历把可见性传入所有嵌套分支，包括表格单元格；附件名称可从旧分叉消息恢复，带附件的 PA 卡片也会触发 Web 权威列表刷新。相关回归覆盖两项。

## 群聊发送者补充

- `executed_base=355e2cfc9`，`validated_at=b66b9c3a3`。独立 reviewer `review_ui_summary` 复核群消息预览、实时事件和 iOS 读取。外部消息姓名缺失与实时附件文件名两项 finding 已关闭，定向回归通过。
- 集成分支增加运行时存储修复、Work 定位和 Web 打开会话滚动修复。合并后重跑会话列表、通知、卡片、搜索和外部入站相关测试，并在新集成树上实测浏览器。

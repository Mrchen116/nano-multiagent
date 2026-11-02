# feat-700 Code review

状态：独立审查完成，用户尚未验收，unit 保持 Active。

- Base：5614b1fb2f29632b76248760af8ce7159b9f8309；受审为该 merge 后的本次 dirty diff（含新增 evals/ui、intelligent-ui、Node 归档读取、integration observationOnly、依赖和文档）。旧 bugfix-699 和主干 merge 不冒充本次新实现。
- 角色：独立 /root/openui_visual_review，使用 change-code-review；其中归档初始化的 Context/执行副作用也纳入核验。未代替用户产品确认。
- 首轮具体发现：配置读取和 workspace 路径可能触及原归档；复制 runtime 后知识恢复仍可能沿历史绝对路径清理原件；旧观察者迟到关闭会清空新 case；照片固定素材未显示；会议步骤误引用未交付的运行器；启动失败可能遗留 runtime。
- 修复：配置先重定向到自有目录；observationOnly 要求所有 agent disabled，跳过恢复/清理，产品调用拒绝；导航同步清空视图后再等待关闭，await 后校验 generation，迟到 prepare/异常不覆盖新页面；显示照片 URL；会议步骤与判定改为实际可操作旅程；读取报告/summary 后才启动 archive，server 启动失败关闭 archive。
- 证据：真实 RuntimeClient 回归保留原件 sentinel，而相同数据普通初始化会执行清理；导航延迟关闭回归保留最新 case；归档 439 文件查看前后哈希无变化；独立复核窄测试/类型检查和导航复现通过。
- Closure：上述发现全部关闭，最终结构化结论 `[]`。最后目录原生阶段默认折叠的窄改动单独 closure `[]`。曾有一次 reviewer capacity failure，沿用原 reviewer 重试后取得上述结论，没有把失败当通过。
- 不声称：未重跑 Memory 候选或正式分数；未执行新 Intelligent UI 正式评测；未将已有场景或源码可运行判为通过。

## 四例增补 patch review

- Base/head：9c556188f；范围为其后的活动试算 case、dataset v2、目录/README、现有接线测试和 unit 文档增补，未改产品代码或运行器。
- 沿用独立 /root/openui_visual_review（gpt-6.1-sol/high）按 change-code-review 执行窄 patch review，结论 `[]`。三个计算点正确，新 prompt 未点名工具、组件或泄漏判定答案；操作控制材料未注入候选输入；原三个 case 不变。独立相关2项接线测试通过。
- 用户同意加第四个 case，会议保留是当前建议和默认处理，不写成用户已批准删除或已完成验收。未运行候选或评分。

## 自然广告分析替换 patch review

- Base/head：f4abfb0d7；范围为dataset v3的ad-analysis替换、固定CSV、公共附件下载、目录/说明/测试及unit增补。原三个case不变，没有增加第五题或运行器。
- 用户最新要求只评是否主动使用UI和主观呈现质量，分析正确性不评分；prompt只含业务问题，固定CSV无输出示例、工具或组件提示。
- 独立 /root/openui_visual_review 发现判定口径接缝：本产品没有独立名为Intelligent UI的工具，模糊描述不能客观地区分Skill加载与真实发布。核对global-mode及message-arguments后，明确只有本case实际send_message/send_user_message调用携带非空字符串interactive.source才记使用；发布或渲染失败仍是调用事实，质量另记失败。Skill加载、代码和普通消息不算，缺轨迹或未跑是未判定。
- 修复后closure结论 `[]`，上述finding closed。附件鉴权/登记白名单与下载接线无新缺陷；独立窄测试和类型检查通过。未调用候选或评分。

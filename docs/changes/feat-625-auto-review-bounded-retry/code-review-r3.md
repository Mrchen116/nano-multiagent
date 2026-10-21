[
  {
    "file": "packages/dsh-integration/tests/codex-approval-native.test.ts",
    "line": 90,
    "summary": "[P2] 证据导出失败时仍须无条件关闭原生runtime",
    "failure_scenario": "启用NANO_REVIEW_NATIVE_EVIDENCE后，finally先mkdir/writeFile，再client.shutdown和rm(home)。若输出目标误指已有普通文件、父目录不可写或写入磁盘失败，L90/L92抛错会直接跳过L94的shutdown及L104的home清理；L98/L101失败也会跳过home清理，并覆盖原测试错误。这是新增opt-in路径引入的隔离资源泄漏，不影响未启用导出的正常运行。已独立提取冻结文件的完整实际finally块，以fake client/fs调用记录执行（未启动或遗留真实进程）：让mkdir抛EEXIST，唯一事件为mkdir，shutdown与rm均未调用，命令exit0。真实RuntimeClient确已在try中创建，因此相同导出异常会绕过原先已有的关闭路径。请原实施者用嵌套try/finally保证导出无论失败与否都执行shutdown及home清理，保留原始测试失败并单列导出错误；无需扩大产品修复或重跑全部90秒预算才可确认该控制流缺陷。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]

/** Executable composition examples; teach relationships, not a mandatory template. */
export const compositionExamples = [
  {
    title: 'An explanation with one useful variable',
    intent: 'Lead with the takeaway, put a small control group beside the main result, and let the graph explain the relationship. Supporting prose follows without another card. These illustrative reading assumptions are not retrieved facts.',
    source: `$minutes = "20"
root = Stack([intro, exploration, explanation], "column", "xl")
intro = Stack([TextContent("每天留一点时间，一周就能积累起来", "large-heavy"), TextContent("调节每天的阅读时间，看看连续坚持一周的累计投入。")], "column", "s")
exploration = Stack([controls, result], "row", "l", "stretch", "start", true)
controls = Card([CardHeader("每天读多久？"), FormControl("每天阅读（分钟）", Input("minutes", "", "number", {min: 0, max: 120}, $minutes)), Buttons([Button("恢复20分钟", @Reset($minutes), "secondary")])], "sunk")
daily = @Max([0, @Min([120, $minutes * 1])])
weekly = daily * 7
result = Card([CardHeader("一周累计"), TextContent(weekly + " 分钟", "large-heavy"), LineChart(["第1天", "第3天", "第7天"], [Series("累计阅读分钟", [daily, daily * 3, weekly])], "linear", "坚持天数", "分钟", 220)])
explanation = Stack([TextContent("**先找到能持续的节奏**"), TextContent("这里按每天相同时间计算。图中的直线表示稳定积累，不代表阅读效果或理解程度。", "small")], "column", "s")`,
  },
  {
    title: 'A comparison with symmetric criteria',
    intent: 'Use the same labels and units on both options, then show the decision-relevant difference. One shared control changes both sides. Do not add an Agent request button when the local comparison already answers the question. Route numbers are labeled illustrative assumptions.',
    source: `$days = "5"
root = Stack([heading, control, comparison, chart, note], "column", "l")
heading = Stack([TextContent("通勤：省时间，还是省一点费用？", "large-heavy"), TextContent("对比同样的出行次数；金额和时间都是示例，不是实时路线数据。")], "column", "s")
control = Card([FormControl("每周通勤天数", Input("days", "", "number", {min: 1, max: 7}, $days))], "sunk")
days = @Max([1, @Min([7, $days * 1])])
comparison = Stack([routeA, routeB], "row", "m", "stretch", "start", true)
routeA = Card([CardHeader("公交", "单程 40 分钟 · 2 元"), TextContent("每周 " + days * 4 + " 元", "large-heavy"), TextContent("往返合计 " + days * 80 + " 分钟", "small")])
routeB = Card([CardHeader("地铁", "单程 25 分钟 · 5 元"), TextContent("每周 " + days * 10 + " 元", "large-heavy"), TextContent("往返合计 " + days * 50 + " 分钟", "small")])
chart = Card([CardHeader("一周的时间差"), BarChart(["公交", "地铁"], [Series("往返分钟", [days * 80, days * 50])], "grouped", "路线", "分钟", 220)])
note = TextContent("按示例，地铁每周少用 " + days * 30 + " 分钟，多花 " + days * 6 + " 元。未计算等车和换乘时间。", "small")`,
  },
] as const;

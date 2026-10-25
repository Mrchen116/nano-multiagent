import { describe, it, expect } from 'vitest';
import { validateInteractiveSource, interactionState } from '../src/interactive-source.js';

const source = `root = Stack([form])
form = Form("draft", send, [field])
field = FormControl("消息草稿", TextArea("body", "编辑", 3, null, "周六见"))
send = ContinueButton("continue", "继续修改")`;

describe('interactive source boundary', () => {
  it('records visible option labels alongside raw selection values', () => {
    const schema = validateInteractiveSource(`root = Form("trip", ContinueButton("go", "继续"), [
      FormControl("方式", RadioGroup("mode", [RadioItem("骑行", "", "bike")], "bike")),
      FormControl("时间", Select("time", [SelectItem("am", "上午")], "", null, "am")),
      FormControl("携带", CheckBoxGroup("items", [CheckBoxItem("雨伞", "", "umbrella"), CheckBoxItem("饮水", "", "water")]))
    ])`);
    expect(interactionState(schema, {trip:{items:{value:{umbrella:true,water:false}}}}).fields).toEqual([
      {name:'mode',label:'方式',value:'bike',display_value:'骑行'},
      {name:'time',label:'时间',value:'am',display_value:'上午'},
      {name:'items',label:'携带',value:{umbrella:true,water:false},display_value:'雨伞'},
    ]);
  });
  it('registers visible actions and fields, preserving initial and edited values', () => {
    const schema = validateInteractiveSource(source);
    expect(schema.actions).toEqual({ continue: '继续修改' });
    expect(interactionState(schema, {}).fields).toMatchObject([{ name: 'body', label: '消息草稿', value: '周六见' }]);
    const result = interactionState(schema, { draft: { body: { value: '周日见', componentType: 'TextArea' } } });
    expect(result.fields).toEqual([{ name: 'body', label: '消息草稿', value: '周日见' }]);
  });
  it.each([
    source.replace('"继续修改")', '$hidden)'),
    source.replace('TextArea("body", "编辑", 3, null, "周六见")', 'Unknown("x")'),
    source + '\nquery = Query("read_secret", {})',
    source + '\nmut = Mutation("send_email", {})',
    source.slice(0, -1),
  ])('rejects incomplete, hidden or unsupported programs', invalid => {
    expect(() => validateInteractiveSource(invalid)).toThrow();
  });
  it('retains native opaque state but rejects oversized snapshots', () => {
    const schema = validateInteractiveSource(source);
    expect(interactionState(schema, { draft: { secret: { value: 'x' } } }).state).toHaveProperty('draft');
    expect(() => interactionState(schema, { draft: { body: { value: 'x'.repeat(17000) } } })).toThrow();
  });
});


describe('full native OpenUI programs', () => {
  it('accepts independent fields, native local actions and computed conditional content', () => {
    const schema = validateInteractiveSource(`$n = "1"
root = Stack([FormControl("数量", Input("amount", "数量", "number", null, $n)), Button("下一步", @Set($n, "" + ($n * 1 + 1))), Button("重置", @Reset($n)), $n > 1 ? TextContent("已变化") : TextContent("初始")])`);
    const result = interactionState(schema, { '$n': '3', amount: {value:'3',componentType:'Input'} });
    expect(result.state['$n']).toBe('3');
    expect(result.fields).toEqual(expect.arrayContaining([expect.objectContaining({name:'amount',label:'数量',value:'3'})]));
  });
  it('accepts registered read queries and explicit mutations but not write queries', () => {
    expect(() => validateInteractiveSource(`data = Query("conversation_messages", {limit:5}, [])
ask = Mutation("continue_conversation", {message:"解释"})
root = Stack([TextContent("消息数：" + @Count(data)), Button("请解释", @Run(ask))])`)).not.toThrow();
    expect(() => validateInteractiveSource(`data = Query("continue_conversation", {message:"自动执行"})
root = TextContent("消息数：" + @Count(data))`)).toThrow();
  });
});

it('rejects mismatched native control binding types before publishing a blank selection', () => {
  const invalid=`$option = 0\nroot = Select("choice", [SelectItem("0", "首项")], null, null, $option)`;
  expect(()=>validateInteractiveSource(invalid)).toThrow(/Select.value.*string/);
  expect(()=>validateInteractiveSource(invalid.replace('$option = 0','$option = "0"')+'\nchange = @Set($option, 1)')).toThrow(/Set.*string/);
});


describe('ComposeMessage local action', () => {
  const source = '$draft = "Hello"\nroot = Stack([TextArea("body", "", 4, null, $draft), Button("Adopt", @ComposeMessage("c_target", $draft))])';
  it('accepts an explicit target and computed editable text', () => {
    expect(() => validateInteractiveSource(source)).not.toThrow();
    expect(() => validateInteractiveSource('reply = "Reply: " + $draft\n' + source.replace('@ComposeMessage("c_target", $draft)', '@ComposeMessage("c_target", reply)'))).not.toThrow();
    expect(interactionState(validateInteractiveSource(source), {'$draft':'Edited'}).fields[0].value).toBe('Edited');
  });
  it.each([
    '@ComposeMessage("external:lark:chat", $draft)',
    '@ComposeMessage("", $draft)',
    '@ComposeMessage("c_target", 42)',
    'Action([@ComposeMessage("c_target", $draft), @ToAssistant("send")])',
    'Action([@ComposeMessage("c_target", $draft), @Run(send)])',
  ])('rejects invalid or implicitly sending adoption: %s', action => {
    expect(() => validateInteractiveSource('send = Mutation("continue_conversation", {message:"send"})\n' + source.replace('@ComposeMessage("c_target", $draft)', action))).toThrow();
  });
});

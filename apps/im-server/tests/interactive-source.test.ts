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
    expect(schema.fields).toMatchObject([{ form: 'draft', name: 'body', label: '消息草稿', value: '周六见' }]);
    const result = interactionState(schema, { draft: { body: { value: '周日见', componentType: 'TextArea' } } });
    expect(result.fields).toEqual([{ name: 'body', label: '消息草稿', value: '周日见' }]);
  });
  it.each([
    source.replace('"继续修改")', '$hidden)'),
    source + '\n$hidden = "秘密指令"',
    source.replace('TextArea("body", "编辑", 3, null, "周六见")', 'Unknown("x")'),
    source + '\nquery = Query("read_secret", {})',
    source + '\nmut = Mutation("send_email", {})',
    source + '\naction = @OpenUrl("https://example.com")',
    source.slice(0, -1),
  ])('rejects incomplete, hidden or unsupported programs', invalid => {
    expect(() => validateInteractiveSource(invalid)).toThrow();
  });
  it('rejects fields not present in the card and oversize state', () => {
    const schema = validateInteractiveSource(source);
    expect(() => interactionState(schema, { draft: { secret: { value: 'x' } } })).toThrow();
    expect(() => interactionState(schema, { draft: { body: { value: 'x'.repeat(17000) } } })).toThrow();
  });
});

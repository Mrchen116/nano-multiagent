import { describe, it, expect } from 'vitest';
import { InteractiveSourceError, validateInteractiveSource, interactionState } from '../src/interactive-source.js';

const source = `$body = "周六见"
root = Col([Form([TextArea($body, "消息草稿"), Button("继续修改", @SendToChat("继续修改"))])])`;

describe('Open Intelligent UI source boundary', () => {
  it.each([
    ['heading = Title("Hello", "huge")\nroot = Col([heading])', 'parser', 'type-mismatch', 'Title', '/size', 'heading'],
    ['$size = "huge"\nheading = Title("Hello", $size)\nroot = Col([heading])', 'parser', 'type-mismatch', 'Title', '/size', 'heading'],
    ['$n = "wrong"\nheading = Text(@Pow($n, 2))\nroot = Col([heading])', 'runtime', 'runtime-error', 'Text', undefined, 'heading'],
  ])('returns upstream repair diagnostics for static and initial-state failures: %s', (program, origin, code, component, path, statementId) => {
    let error: InteractiveSourceError | undefined;
    try { validateInteractiveSource(program!); } catch (caught) { error = caught as InteractiveSourceError; }
    expect(error).toBeInstanceOf(InteractiveSourceError);
    expect(error!.detail).toMatchObject({code:'invalid_interactive_source', errors:[expect.objectContaining({source:origin, code, component, statementId})]});
    if (path) expect(error!.detail.errors[0].path).toBe(path);
    expect(error!.detail.errors[0].message).toBeTruthy();
    if (origin === 'runtime') expect(error!.detail.errors[0].hint).toBeTruthy();
    expect(error!.detail).not.toHaveProperty('source');
    expect(error!.detail).not.toHaveProperty('stack');
  });
  it('does not execute actions or reject pending queries while checking initial props', () => {
    expect(() => validateInteractiveSource(`data = Query("conversation_messages", {})
$n = 1
$later = "bad"
root = Col([Text("Count " + @Count(data)), Button("Next", @Set($n, @Pow($later, 2)))])`)).not.toThrow();
  });
  it.each(['Input($name, "Name")','TextArea($draft)','Checkbox($selected, "Selected")'])('allows unset initial bindings without weakening known computed prop checks: %s', control => {
    expect(() => validateInteractiveSource(`root = Col([${control}])`)).not.toThrow();
    expect(() => validateInteractiveSource(`$size = "huge"\nroot = Col([${control}, Title("Hello", $size)])`))
      .toThrow(expect.objectContaining({detail:expect.objectContaining({errors:[expect.objectContaining({code:'type-mismatch',component:'Title',path:'/size'})]})}));
  });
  it('snapshots edited values with control and option labels', () => {
    const schema = validateInteractiveSource(`$mode = "bike"
$time = "am"
options = [{value:"am",label:"上午"}]
label = "时间"
root = Col([RadioGroup($mode, [{value:"bike",label:"骑行"}], "方式"), Select($time, options, label)])`);
    expect(interactionState(schema, {}).fields).toEqual([
      {name:'$mode',label:'方式',value:'bike',display_value:'骑行'},
      {name:'$time',label:'时间',value:'am',display_value:'上午'},
    ]);
    expect(interactionState(validateInteractiveSource(source), {'$body':'周日见'}).fields).toEqual([{name:'$body',label:'消息草稿',value:'周日见'}]);
  });
  it.each([
    source.replace('TextArea($body, "消息草稿")', 'Unknown("x")'),
    source + '\nquery = Query("read_secret", {})',
    source + '\nmut = Mutation("send_email", {})',
    source.slice(0, -1),
  ])('rejects incomplete or unsupported programs', invalid => {
    expect(() => validateInteractiveSource(invalid)).toThrow();
  });
  it('retains local opaque state but rejects oversized snapshots', () => {
    const schema = validateInteractiveSource(source);
    expect(interactionState(schema, {'$body':'x', '$local':[1]}).state).toEqual({'$body':'x','$local':[1]});
    expect(() => interactionState(schema, {'$body':'x'.repeat(17000)})).toThrow();
  });
  it('evaluates the same upstream functions in server validation and preserves local drawing state', () => {
    const schema = validateInteractiveSource(`$n = 3
root = Col([Input($n, "数量", "number"), Svg([Rect(0, 0, @Clamp($n * 10, 0, 100), 20)], "0 0 100 30"), Button("下一步", @Set($n, $n + 1))])`);
    expect(interactionState(schema, {'$n':4}).fields).toEqual([{name:'$n',label:'数量',value:4}]);
    expect(() => validateInteractiveSource(`$draft = "Hello"
root = Button("Adopt", @ComposeMessage("c_target", @Capitalize($draft)))`)).not.toThrow();
  });
  it('accepts registered queries/mutations but not a write query', () => {
    expect(() => validateInteractiveSource(`data = Query("conversation_messages", {limit:5}, [])
ask = Mutation("continue_conversation", {message:"解释"})
root = Col([Text("消息数：" + @Count(data)), Button("请解释", @Run(ask))])`)).not.toThrow();
    expect(() => validateInteractiveSource(`data = Query("continue_conversation", {message:"自动执行"})
root = Text("消息数：" + @Count(data))`)).toThrow();
  });
  it('rejects mismatched selection types before publishing a blank selection', () => {
    const invalid='$option = 0\nroot = Select($option, [{value:"0",label:"首项"}])';
    expect(()=>validateInteractiveSource(invalid)).toThrow(expect.objectContaining({detail:expect.objectContaining({errors:[expect.objectContaining({component:'Select',path:'/value',code:'type-mismatch'})]})}));
    expect(()=>validateInteractiveSource(invalid.replace('$option = 0','$option = "0"')+'\nchange = @Set($option, 1)')).toThrow(/Set.*string/);
  });
});

it('keeps previously saved ToAssistant cards readable', () => {
  expect(() => validateInteractiveSource(source.replaceAll('SendToChat', 'ToAssistant'))).not.toThrow();
});

describe('ComposeMessage local action', () => {
  const source = '$draft = "Hello"\nroot = Col([TextArea($draft), Button("Adopt", @ComposeMessage("c_target", $draft))])';
  it('accepts an explicit target and computed editable text', () => {
    expect(() => validateInteractiveSource(source)).not.toThrow();
    expect(() => validateInteractiveSource('reply = "Reply: " + $draft\n' + source.replace('@ComposeMessage("c_target", $draft)', '@ComposeMessage("c_target", reply)'))).not.toThrow();
    expect(interactionState(validateInteractiveSource(source), {'$draft':'Edited'}).fields[0].value).toBe('Edited');
  });
  it.each([
    '@ComposeMessage("external:lark:chat", $draft)',
    '@ComposeMessage("", $draft)',
    '@ComposeMessage("c_target", 42)',
    'Action([@ComposeMessage("c_target", $draft), @SendToChat("send")])',
    'Action([@ComposeMessage("c_target", $draft), @ToAssistant("send")])',
    'Action([@ComposeMessage("c_target", $draft), @Run(send)])',
  ])('rejects invalid or implicitly sending adoption: %s', action => {
    expect(() => validateInteractiveSource('send = Mutation("continue_conversation", {message:"send"})\n' + source.replace('@ComposeMessage("c_target", $draft)', action))).toThrow();
  });
});

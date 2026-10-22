import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { describe, expect, it } from 'vitest';
import { compositionExamples } from '../../frontend/src/features/chat/interactive/composition-examples';

function runtime(source: string, state = {}) {
  // The packaged resource runs without Node, DOM, fetch, or credentials, as in JavaScriptCore.
  const scope = vm.createContext({});
  vm.runInContext(readFileSync(new URL('../NanoIM/Resources/InteractiveRuntime.js', import.meta.url), 'utf8'), scope);
  const engine = scope.NanoInteractive.create(source, state);
  const snapshot = () => JSON.parse(engine.snapshot());
  function find(kind: string, value = snapshot().root): any {
    if (Array.isArray(value)) return value.map(item => find(kind, item)).find(Boolean);
    if (!value || typeof value !== 'object') return;
    if (value.typeName === kind) return value;
    return Object.values(value).map(item => find(kind,item)).find(Boolean);
  }
  return {engine, snapshot, find};
}

describe('packaged native interactive evaluator', () => {
  it.each(compositionExamples)('keeps the $title exploration reactive and resets its original input', ({source}) => {
    const host = runtime(source);
    host.engine.edit(host.find('Input').id, 'value', '35');
    expect(host.snapshot().state).toEqual(expect.objectContaining(source.includes('$minutes') ? {'$minutes':'35'} : {'$days':'35'}));
    if (source.includes('$minutes')) {
      expect(JSON.stringify(host.snapshot().root)).toContain('245 分钟');
      host.engine.activate(host.find('Button').id);
      expect(host.snapshot().state['$minutes']).toBe('20');
    }
  });

  it('submits complete current form state after Set, preserving slider array types', () => {
    const host = runtime('$scale = [2]\nroot = Stack([Slider("scale", "continuous", 0, 10, 1, [2], "倍率", {}, $scale), Form("note", Buttons([Button("解释当前结果", Action([@Set($scale, [3]), @ToAssistant("分析参数", {kind:"comparison"})]))]), [FormControl("备注", Input("text", "", "text"))])])');
    host.engine.edit(host.find('Input').id, 'value', '最新备注');
    const result = JSON.parse(host.engine.activate(host.find('Button').id));
    expect(result.events).toEqual([expect.objectContaining({type:'continue_conversation',message:'分析参数',context:{kind:'comparison'},state:{'$scale':[3],note:{text:'最新备注'}}})]);
  });

  it('finishes the clicked action even when Set removes its button from the current view', () => {
    const host = runtime('$show = true\nroot = $show ? Card([Button("继续", Action([@Set($show, false), @ToAssistant("继续")]))]) : TextContent("已隐藏")');
    const result = JSON.parse(host.engine.activate(host.find('Button').id));
    expect(result.events).toEqual([expect.objectContaining({type:'continue_conversation',message:'继续',state:{'$show':false}})]);
  });

  it('validates required fields before a continuation', () => {
    const host = runtime('root = Form("details", Buttons([Button("继续", @ToAssistant("继续"))]), [FormControl("姓名", Input("name", "", "text", {required:true}))])');
    expect(() => host.engine.activate(host.find('Button').id)).toThrow();
    host.engine.edit(host.find('Input').id,'value','陈');
    expect(JSON.parse(host.engine.activate(host.find('Button').id)).events[0].state).toEqual({details:{name:'陈'}});
  });

  it('renders Query defaults then current scoped results, and emits Mutation only on click', () => {
    const host = runtime('data = Query("conversation_messages", {limit:5}, [])\nask = Mutation("continue_conversation", {message:"分析消息"})\nroot = Stack([TextContent("消息数：" + @Count(data)), Button("继续分析", @Run(ask))])');
    expect(host.snapshot().events).toEqual([]);
    expect(JSON.stringify(host.snapshot().root)).toContain('消息数：0');
    host.engine.result('data',JSON.stringify({limit:5}),[{id:'m1'}]);
    expect(JSON.stringify(host.snapshot().root)).toContain('消息数：1');
    expect(JSON.parse(host.engine.activate(host.find('Button').id)).events).toEqual([expect.objectContaining({type:'mutation',args:{message:'分析消息'}})]);
  });
});

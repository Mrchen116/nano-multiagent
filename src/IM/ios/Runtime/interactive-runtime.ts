import { createParser, createLibrary, defineComponent, markReactive, createStore, evaluateRoot, evaluate,
  isReactiveAssign, resolveStateField, validate, parseStructuredRules } from '@openuidev/lang-core';
import { z } from 'zod';
import { interactiveCatalog } from '../../../../packages/product-contracts/src/interactive-catalog';

// Agent source is parsed data. Only this bundled interpreter executes in JavaScriptCore.
const parser = createParser(interactiveCatalog, 'Stack');
const controls = new Set(['Input','TextArea','Select','Slider','DatePicker','CheckBoxGroup','RadioGroup','SwitchGroup','Chips','OptionCards','EditableTable']);
function reactive(schema: z.ZodType) { markReactive(schema); return schema; }
const library = createLibrary({ components: Object.entries(interactiveCatalog.$defs).filter(([name]) => name !== 'ActionExpression').map(([name, schema]) =>
  defineComponent({ name, description: name, props: z.object(Object.fromEntries(Object.keys('properties' in schema ? schema.properties : {}).map(key =>
    [key, (controls.has(name) && ['value','defaultValue','data'].includes(key) || name === 'Modal' && key === 'open' || name === 'Callout' && key === 'visible') ? reactive(z.any().optional()) : z.any().optional()]))), component: () => null })) });

/** Create one source-scoped evaluator without credentials or network APIs.
 *
 * Args:
 *   source: Immutable openui/nano-1 program from the message.
 *   initial: The authenticated viewer's saved private state.
 * Returns:
 *   JSON snapshot, edit, action and query-result operations for the native host.
 */
export function create(source: string, initial: Record<string, unknown>) {
  const parsed = parser.parse(source);
  if ((!parsed.root && !parsed.rootExpression) || parsed.meta.errors.length || parsed.meta.incomplete || parsed.meta.unresolved.length)
    throw new Error('This interactive reply could not be read.');
  const store = createStore();
  store.initialize(parsed.stateDeclarations, initial);
  const nodes = new Map<string, {node: any; form?: string}>();
  const results = new Map<string, {signature: string; value: unknown}>();
  const ctx: any = {
    actions: interactiveCatalog.actions,
    getState: (name: string) => store.get(name),
    resolveRef(name: string): unknown {
      const query = parsed.queryStatements.find(item => item.statementId === name);
      if (query) {
        const args = query.argsAST ? evaluate(query.argsAST, ctx) : {};
        const saved = results.get(name);
        return saved?.signature === JSON.stringify(args) ? saved.value : query.defaultsAST ? evaluate(query.defaultsAST, ctx) : null;
      }
      return results.get(name)?.value;
    },
  };
  function field(node: any, form: string | undefined, property = 'value') {
    const name = String(node.props.name ?? '');
    const binding = node.props[property] ?? node.props.defaultValue;
    return resolveStateField(name, binding, store, ctx,
      key => {
        const value = form ? (store.get(form) as any)?.[key] : store.get(key);
        return value && typeof value === 'object' && !Array.isArray(value) && 'value' in value ? value.value : value;
      },
      (key, value) => store.set(form ?? key, form ? {...store.get(form) as any, [key]: value} : value));
  }
  function defaultValue(node: any): unknown {
    if (node.typeName === 'Slider') return node.props.defaultValue ?? [node.props.min ?? 0];
    if (['CheckBoxGroup','SwitchGroup'].includes(node.typeName)) return Object.fromEntries((node.props.items ?? []).map((item: any) => [item.props.name, Boolean(item.props.defaultChecked)]));
    if (node.typeName === 'EditableTable') return node.props.data ?? [];
    if (['Chips','OptionCards'].includes(node.typeName) && node.props.type === 'multi') return [];
    return node.props.defaultValue ?? '';
  }
  function normalize(value: any, path: string, form?: string): any {
    if (Array.isArray(value)) return value.map((item, index) => normalize(item, `${path}.${index}`, form));
    if (!value || typeof value !== 'object') return value ?? null;
    if (isReactiveAssign(value)) return store.get(value.target) ?? null;
    if (value.type !== 'element') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalize(item, `${path}.${key}`, form)]));
    const currentForm = value.typeName === 'Form' ? String(value.props.name ?? '') : form;
    nodes.set(path, {node:value, form:currentForm});
    const props = Object.fromEntries(Object.entries(value.props).map(([key, item]) => [key, normalize(item, `${path}.${key}`, currentForm)]));
    const bindings = Object.fromEntries(Object.entries(value.props).filter(([,item]) => isReactiveAssign(item)));
    if (controls.has(value.typeName)) {
      const property = value.typeName === 'EditableTable' ? 'data' : ['Chips','OptionCards'].includes(value.typeName) ? 'defaultValue' : 'value';
      const selected = field(value, currentForm, property).value;
      props[property] = selected ?? defaultValue(value);
      props.value = props[property];
    }
    return {id:path, type:'element', typeName:value.typeName, props, bindings};
  }
  function queries() {
    return parsed.queryStatements.filter(item => item.complete).map(query => {
      const args = query.argsAST ? evaluate(query.argsAST, ctx) : {};
      return {id:query.statementId, tool:query.toolAST ? evaluate(query.toolAST, ctx) : '', args,
        signature:JSON.stringify(args), refresh:query.refreshAST ? evaluate(query.refreshAST, ctx) : 0};
    });
  }
  function snapshot(events: unknown[] = []) {
    nodes.clear();
    const root = normalize(evaluateRoot(parsed, {ctx, library, store}), 'root');
    return JSON.stringify({root, state:store.getSnapshot(), queries:queries(), events});
  }
  function validateForm(form?: string) {
    for (const {node, form:owner} of nodes.values()) {
      if (!controls.has(node.typeName) || owner !== form) continue;
      const property = node.typeName === 'EditableTable' ? 'data' : ['Chips','OptionCards'].includes(node.typeName) ? 'defaultValue' : 'value';
      const error = validate(field(node, owner, property).value ?? defaultValue(node), parseStructuredRules(node.props.rules));
      if (error) throw new Error(error);
    }
  }
  return {
    snapshot,
    edit(id: string, property: string, value: unknown) {
      const item = nodes.get(id);
      if (!item) throw new Error('This control is no longer available.');
      field(item.node, item.form, property).setValue(value);
      return snapshot();
    },
    activate(id: string) {
      const item = nodes.get(id);
      if (!item) throw new Error('This action is no longer available.');
      validateForm(item.form);
      const node = item.node;
      if (node.typeName === 'ContinueButton') return snapshot([{type:'legacy', action_id:node.props.id, state:store.getSnapshot()}]);
      const events: any[] = [];
      let index = 0;
      // Re-evaluate later steps against earlier Set/Reset results, just as the host renderer does.
      while (true) {
        const currentRoot = evaluateRoot(parsed, {ctx, library, store});
        nodes.clear(); normalize(currentRoot, 'root');
        const current = nodes.get(id)?.node ?? node;
        const action: any = current?.props.action;
        const steps = action?.steps ?? (action?.type ? [action] : []);
        const step = steps[index++];
        if (!step) break;
        if (step.type === 'set') store.set(step.target, evaluate(step.valueAST, ctx));
        else if (step.type === 'reset') for (const target of step.targets) store.set(target, parsed.stateDeclarations[target], {pristine:true});
        else if (step.type === 'run') {
          if (step.refType === 'query') {
            results.delete(step.statementId); events.push({type:'query', id:step.statementId});
          } else {
            const mutation = parsed.mutationStatements.find(entry => entry.statementId === step.statementId);
            const tool = mutation?.toolAST ? evaluate(mutation.toolAST, ctx) : '';
            if (tool !== 'continue_conversation') throw new Error('This tool is not connected.');
            events.push({type:'mutation', id:step.statementId, args:mutation?.argsAST ? evaluate(mutation.argsAST, ctx) : {}, state:store.getSnapshot(), form:item.form});
          }
        } else if (step.type === 'continue_conversation') events.push({...step, state:store.getSnapshot(), form:item.form});
        else if (step.type === 'open_url' || step.type === 'custom_action') events.push(step);
        else throw new Error('This action is not connected.');
      }
      return snapshot(events);
    },
    result(id: string, signature: string, value: unknown) { results.set(id, {signature, value}); return snapshot(); },
  };
}

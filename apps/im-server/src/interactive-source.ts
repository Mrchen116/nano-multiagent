import { autoClose, createLibrary, createParser, evaluate, evaluateRoot, parseExpression, split, tokenize, walkAST, type ASTNode, type ElementNode, type EvaluationContext } from '@openuidev/lang-core';
import { interactiveCatalog, interactiveTools, canonicalJson } from '@nano/product-contracts';

export interface InteractiveSchema { source: string; actions: Record<string, string> }
const parser = createParser(interactiveCatalog, 'Stack');
// Values are evaluated for a snapshot, without React components or reactive setters.
const valueLibrary = createLibrary({components: []});
const inputTypes = new Set(['Input', 'TextArea', 'Select', 'Slider', 'CheckBoxGroup', 'RadioGroup', 'Switch', 'DatePicker']);

/** Validate a complete native program and record legacy continuation labels. */
export function validateInteractiveSource(source: string): InteractiveSchema {
  if (Buffer.byteLength(source, 'utf8') > 65536 || autoClose(source).wasIncomplete) throw new Error('Interactive source is oversized or incomplete');
  const parsed = parser.parse(source);
  if ((!parsed.root && !parsed.rootExpression) || parsed.meta.incomplete || parsed.meta.unresolved.length || parsed.meta.errors.length)
    throw new Error(`Invalid interactive source: ${JSON.stringify({errors: parsed.meta.errors.map(item => item.message), unresolved: parsed.meta.unresolved})}`);
  const actions: Record<string, string> = {};
  const statements = split(tokenize(source)).map(statement => parseExpression(statement.tokens));
  const stringBindings = new Set<string>();
  const context: EvaluationContext = {getState: name => parsed.stateDeclarations[name], resolveRef: () => undefined};
  // The native parser defers bound values. Enforce declared string types too:
  // numeric Select values render a blank label even when an option has that ID.
  const definitions = interactiveCatalog.$defs as Record<string, {properties?:Record<string,{type?:string|string[]}>}>;
  const checkString = (value: unknown, location: string) => {
    if (value !== undefined && value !== null && typeof value !== 'string') throw new Error(`${location} expects a string; preserve the control's value type, including in Set actions`);
  };
  for (const statement of statements) walkAST(statement, node => {
    if (node.k !== 'Comp') return;
    const properties = definitions[node.name]?.properties;
    if (properties) Object.entries(properties).forEach(([name, schema], index) => {
      const value = node.args[index];
      if (schema.type === 'string' && value?.k === 'StateRef') {
        stringBindings.add(value.n); checkString(parsed.stateDeclarations[value.n], `${node.name}.${name}`);
      }
    });
    if (node.name === 'Query' || node.name === 'Mutation') {
      const tool = node.args[0];
      if (tool?.k !== 'Str' || !interactiveTools.some(item => item.name === tool.v && item.mode === (node.name === 'Query' ? 'read' : 'write')))
        throw new Error('Query/Mutation must use a registered tool of the matching read/write kind');
    }
    if (node.name === 'ContinueButton') {
      const [id, label] = node.args;
      if (id?.k !== 'Str' || label?.k !== 'Str' || !id.v.trim() || !label.v.trim() || Object.hasOwn(actions, id.v))
        throw new Error('Legacy ContinueButton requires unique literal id and visible literal label');
      actions[id.v] = label.v;
    }
  });
  for (const statement of statements) walkAST(statement, node => {
    if (node.k === 'Comp' && node.name === 'Set' && node.args[0]?.k === 'StateRef' && stringBindings.has(node.args[0].n) && node.args[1])
      checkString(evaluate(node.args[1] as ASTNode, context), `Set(${node.args[0].n})`);
  });
  return { source, actions };
}

/** Preserve native viewer state and derive visible field values from the current program.
 *
 * Args:
 *   schema: The validated immutable public program.
 *   input: Current viewer's native Renderer state, at most 16 KiB.
 * Returns:
 *   A canonical snapshot and readable fields; state is user data, never authority.
 */
export function interactionState(schema: InteractiveSchema, input: unknown) {
  if (!input || typeof input !== 'object' || Array.isArray(input) || Buffer.byteLength(JSON.stringify(input), 'utf8') > 16384)
    throw new Error('Interaction state must be an object within 16 KiB');
  const state = JSON.parse(canonicalJson(input)) as Record<string, unknown>;
  const parsed = parser.parse(schema.source);
  const unwrap = (value: unknown): unknown => value && typeof value === 'object' && 'value' in value ? value.value : value;
  const ctx: EvaluationContext = {
    getState: name => unwrap(Object.hasOwn(state, name) ? state[name] : parsed.stateDeclarations[name]),
    resolveRef: name => { const query = parsed.queryStatements.find(item => item.statementId === name); return query?.defaultsAST ? evaluate(query.defaultsAST, ctx) : undefined; },
  };
  const root = evaluateRoot(parsed, {ctx, library: valueLibrary, store:null});
  const fields: {name:string;label:string;value:unknown;display_value?:string}[] = [];
  function visit(value: unknown, form = '', label = ''): void {
    if (Array.isArray(value)) { value.forEach(item => visit(item, form, label)); return; }
    if (!value || typeof value !== 'object') return;
    const node = value as ElementNode;
    if (node.type !== 'element') { Object.values(value).forEach(item => visit(item, form, label)); return; }
    if (node.typeName === 'Form') form = String(node.props.name ?? '');
    if (node.typeName === 'FormControl') label = String(node.props.label ?? '');
    if (inputTypes.has(node.typeName) && typeof node.props.name === 'string') {
      const name = node.props.name;
      const entry = form ? (state[form] as Record<string, unknown> | undefined)?.[name] : state[name];
      const selected = unwrap(entry) ?? node.props.value ?? node.props.defaultValue ?? (node.typeName === 'CheckBoxGroup' ? {} : '');
      const options = Array.isArray(node.props.items) ? Object.fromEntries(node.props.items.filter((item: ElementNode) => typeof item.props?.label === 'string')
        .map((item: ElementNode) => [item.props.value ?? item.props.name, item.props.label])) : {};
      const display = typeof selected === 'string' && Object.hasOwn(options, selected) ? options[selected]
        : node.typeName === 'CheckBoxGroup' && selected && typeof selected === 'object'
          ? Object.entries(selected).filter(([, checked]) => checked === true).map(([key]) => options[key] ?? key).join('、') || '—' : undefined;
      fields.push({name, label:label || String(node.props.label ?? name),value:selected,...(display !== undefined ? {display_value:display} : {})});
    }
    Object.values(node.props).forEach(item => visit(item, form, label));
  }
  visit(root);
  return {state, fields};
}

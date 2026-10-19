import { autoClose, createParser, parseExpression, split, tokenize, walkAST, type ASTNode, type ElementNode } from '@openuidev/lang-core';
import { interactiveCatalog, canonicalJson } from '@nano/product-contracts';

interface Field {
  form: string;
  name: string;
  label: string;
  componentType: string;
  variable?: string;
  options?: Record<string, string>;
  value: unknown;
}
export interface InteractiveSchema {
  actions: Record<string, string>;
  fields: Field[];
  variables: Record<string, unknown>;
}
const parser = createParser(interactiveCatalog, 'Stack');
const inputTypes = new Set(['Input', 'TextArea', 'Select', 'Slider', 'CheckBoxGroup', 'RadioGroup']);
const forbidden = new Set(['Query', 'Mutation', 'Action', 'ToAssistant', 'OpenUrl', 'Run', 'Set', 'Reset']);
const safeName = (value: unknown): value is string => typeof value === 'string' && !!value.trim() && !['__proto__', 'constructor', 'prototype'].includes(value);

/** Validate a complete program and derive its public action and field registry.
 *
 * Args:
 *   source: A size-bounded OpenUI program from a public Agent delivery.
 * Returns:
 *   The static visible actions, labelled fields, and local state declarations.
 * Throws:
 *   Error: Any part is incomplete, outside this catalogue, or cannot be recorded.
 */
export function validateInteractiveSource(source: string): InteractiveSchema {
  if (Buffer.byteLength(source, 'utf8') > 65536 || autoClose(source).wasIncomplete) throw new Error('Interactive source is oversized or incomplete');
  const parsed = parser.parse(source);
  if (!parsed.root || parsed.meta.incomplete || parsed.meta.unresolved.length || parsed.meta.orphaned.length || parsed.meta.errors.length)
    throw new Error(`Invalid interactive source: ${JSON.stringify({errors: parsed.meta.errors.map(item => item.message), unresolved: parsed.meta.unresolved, unused: parsed.meta.orphaned})}`);
  let declaredFields = 0;
  const usedVariables = new Set<string>();
  const actions: Record<string, string> = {};
  const statements = split(tokenize(source));
  for (const statement of statements) walkAST(parseExpression(statement.tokens), node => {
    if (node.k === 'StateRef') usedVariables.add(node.n);
    if (node.k !== 'Comp') return;
    if (inputTypes.has(node.name)) declaredFields++;
    if (forbidden.has(node.name) || !node.fn && !Object.hasOwn(interactiveCatalog.properties, node.name)) throw new Error(`Unsupported interactive call: ${node.name}`);
    if (node.name === 'ContinueButton') {
      const [id, label] = node.args;
      if (id?.k !== 'Str' || label?.k !== 'Str' || !safeName(id.v) || !label.v.trim() || Object.hasOwn(actions, id.v))
        throw new Error('ContinueButton requires unique literal id and visible literal label');
      actions[id.v] = label.v;
    }
    if ((inputTypes.has(node.name) || node.name === 'Form') && (node.args[0]?.k !== 'Str' || !safeName(node.args[0].v)))
      throw new Error('Form and field names must be static non-empty strings');
    if (node.name === 'FormControl' && (node.args[0]?.k !== 'Str' || !node.args[0].v.trim())) throw new Error('Fields require visible literal labels');
  });
  if (Object.keys(parsed.stateDeclarations).some(name => !usedVariables.has(name))) throw new Error('Unused local state');
  const fields: Field[] = [];
  const forms = new Set<string>();
  function visit(value: unknown, form = '', label = ''): void {
    if (Array.isArray(value)) { value.forEach(item => visit(item, form, label)); return; }
    if (!value || typeof value !== 'object') return;
    const node = value as ElementNode;
    if (node.type !== 'element') { Object.values(value).forEach(item => visit(item, form, label)); return; }
    if (node.typeName === 'Form') {
      form = node.props.name as string;
      if (forms.has(form)) throw new Error('Form names must be unique');
      forms.add(form);
    }
    if (node.typeName === 'FormControl') label = node.props.label as string;
    if (inputTypes.has(node.typeName)) {
      const name = node.props.name as string;
      if (!form || !label || fields.some(field => field.name === name)) throw new Error('Fields must be inside a named Form, labelled and uniquely named');
      const raw = node.props.value as ASTNode | undefined;
      const variable = raw && typeof raw === 'object' && raw.k === 'StateRef' ? raw.n : undefined;
      const value = variable ? parsed.stateDeclarations[variable] : node.props.value ?? node.props.defaultValue
        ?? (node.typeName === 'CheckBoxGroup' ? {} : node.typeName === 'Slider' ? [node.props.min] : '');
      if (variable && !Object.hasOwn(parsed.stateDeclarations, variable)) throw new Error('Undeclared field state');
      const options = Array.isArray(node.props.items) ? Object.fromEntries(node.props.items
        .filter((item: ElementNode) => typeof item.props?.label === 'string' && typeof (item.props.value ?? item.props.name) === 'string')
        .map((item: ElementNode) => [item.props.value ?? item.props.name, item.props.label])) : undefined;
      fields.push({ form, name, label, componentType: node.typeName, ...(variable ? { variable } : {}), ...(options ? { options } : {}), value });
    }
    Object.values(node.props).forEach(item => visit(item, form, label));
  }
  visit(parsed.root);
  if (fields.length !== declaredFields) throw new Error('Conditional or generated fields are unsupported; keep the form fields static');
  return { actions, fields, variables: parsed.stateDeclarations };
}

/** Keep only declared renderer state and produce a readable choice snapshot.
 *
 * Args:
 *   schema: Registry derived from the immutable source.
 *   input: Current viewer's opaque Renderer state, at most 16 KiB.
 * Returns:
 *   Validated state and labelled values, retaining defaults for untouched fields.
 */
export function interactionState(schema: InteractiveSchema, input: unknown) {
  if (!input || typeof input !== 'object' || Array.isArray(input) || Buffer.byteLength(JSON.stringify(input), 'utf8') > 16384)
    throw new Error('Interaction state must be an object within 16 KiB');
  const state = JSON.parse(canonicalJson(input)) as Record<string, unknown>;
  for (const [key, value] of Object.entries(state)) {
    if (key.startsWith('$')) {
      if (!Object.hasOwn(schema.variables, key)) throw new Error('Unknown state variable');
    } else {
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid form state');
      for (const [name, entry] of Object.entries(value)) {
        if (!schema.fields.some(field => field.form === key && field.name === name) || !entry || typeof entry !== 'object' || !Object.hasOwn(entry, 'value'))
          throw new Error('Unknown field state');
      }
    }
  }
  const fields = schema.fields.map(field => {
    const entry = (state[field.form] as Record<string, { value: unknown }> | undefined)?.[field.name];
    const value = field.variable && Object.hasOwn(state, field.variable) ? state[field.variable] : entry?.value ?? field.value;
    const displayValue = field.options && typeof value === 'string' && Object.hasOwn(field.options, value) ? field.options[value]
      : field.options && field.componentType === 'CheckBoxGroup' && value && typeof value === 'object'
        ? Object.entries(value).filter(([, checked]) => checked === true).map(([name]) => field.options![name] ?? name).join('、') || '—'
        : undefined;
    return { name: field.name, label: field.label, value, ...(displayValue !== undefined ? { display_value: displayValue } : {}) };
  });
  return { state, fields };
}

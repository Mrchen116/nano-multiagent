import { interactiveRuntimeFunctions } from '@nano/product-contracts/interactive-functions';
import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { autoClose, createLibrary, createParser, enrichErrors, evaluate, evaluateRoot, jsonToOpenUI, parseExpression, split, tokenize, walkAST, type ASTNode, type EvaluationContext, type OpenUIError } from '@openuidev/lang-core';
import { intelligentUICatalog as interactiveCatalog, interactiveTools } from '@nano/product-contracts';

export interface InteractiveSchema { source: string; actions: Record<string, string> }
const parser = createParser(interactiveCatalog, 'Col');
// Initial-state evaluation needs no React components or reactive event handlers.
// The public serializer uses the same generated schema as the publication parser.
const validationLibrary = {...createLibrary({components: []}), toJSONSchema: () => interactiveCatalog};
const componentNames = Object.keys(interactiveCatalog.$defs);

/** Carry upstream repair diagnostics without source, ASTs, or server stacks. */
export class InteractiveSourceError extends Error {
  readonly detail;
  constructor(errors: OpenUIError[]) {
    super('Interactive UI was not published. Correct the errors and retry.');
    this.detail = {code: 'invalid_interactive_source', message: this.message,
      errors: [...new Map(errors.map(error => [JSON.stringify(error), error])).values()]};
  }
}

/** Validate a complete Open Intelligent UI program. */
export function validateInteractiveSource(source: string): InteractiveSchema {
  if (Buffer.byteLength(source, 'utf8') > 65536 || autoClose(source).wasIncomplete) throw new Error('Interactive source is oversized or incomplete');
  const parsed = parser.parse(source);
  const diagnostics = enrichErrors(parsed.meta.errors, interactiveCatalog, componentNames);
  for (const statementId of parsed.meta.unresolved) diagnostics.push({source:'parser', code:'parse-failed', statementId,
    message:`Unresolved reference "${statementId}"`, hint:'Define the referenced statement before publishing the complete program.'});
  if ((!parsed.root && !parsed.rootExpression) || parsed.meta.incomplete) diagnostics.push({source:'parser', code:'parse-failed',
    message:'The complete program must have a renderable root.', hint:'Provide root = Component(...) and complete all statements.'});
  if (diagnostics.length) throw new InteractiveSourceError(diagnostics);
  const actions: Record<string, string> = {};
  const sourceStatements = split(tokenize(source));
  const statements = sourceStatements.map(statement => parseExpression(statement.tokens));
  const named = new Map(sourceStatements.map((statement, index) => [statement.id, statements[index]]));
  const stringBindings = new Set<string>();
  const context: EvaluationContext = {actions: interactiveCatalog.actions, functions: interactiveRuntimeFunctions, getState: name => parsed.stateDeclarations[name],
    resolveRef: name => {
      const query = parsed.queryStatements.find(item => item.statementId === name);
      const value = query?.defaultsAST ?? named.get(name);
      return value ? evaluate(value, context) : undefined;
    },
  };
  const runtimeErrors: OpenUIError[] = [];
  const evaluated = evaluateRoot(parsed, {library: validationLibrary, ctx: context, store: null, errors: runtimeErrors});
  if (runtimeErrors.length) throw new InteractiveSourceError(runtimeErrors);
  // Reuse the SDK's schema checks on computed initial props. Queries without
  // defaults have no value yet; do not treat pending external data as invalid.
  if (evaluated && parsed.queryStatements.every(query => query.defaultsAST)) {
    const snapshot = parser.parse(jsonToOpenUI({...evaluated, statementId:'root'}, validationLibrary));
    // An unset binding is a valid initial control state. Serialization turns it
    // into literal null, so null-required here is not a conclusive source error.
    // Literal required nulls were already checked on the original program.
    const errors = enrichErrors(snapshot.meta.errors.filter(error => error.code !== 'null-required'), interactiveCatalog, componentNames);
    if (errors.length) throw new InteractiveSourceError(errors);
  }
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

  });
  const inspectAction = (node: ASTNode, visited = new Set<string>()): Set<string> => {
    const kinds = new Set<string>();
    walkAST(node, child => {
      if (child.k === 'Ref' && !visited.has(child.n) && named.has(child.n)) {
        visited.add(child.n);
        for (const kind of inspectAction(named.get(child.n)!, visited)) kinds.add(kind);
      }
      if (child.k !== 'Comp') return;
      if (child.name === 'ComposeMessage') {
        kinds.add('compose');
        const target = evaluate(child.args[0], context), text = evaluate(child.args[1], context);
        if (typeof target !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(target)) throw new Error('ComposeMessage target must be an explicit Nano IM conversation id');
        if (typeof text !== 'string') throw new Error('ComposeMessage text must evaluate to a string');
      }
      if (child.name === 'SendToChat' || child.name === 'ToAssistant' || child.name === 'Mutation') kinds.add('send');
      if (child.name === 'Run' && child.args[0]?.k === 'Ref') {
        const mutation = named.get(child.args[0].n);
        if (mutation?.k === 'Comp' && mutation.name === 'Mutation') kinds.add('send');
      }
    });
    return kinds;
  };
  for (const statement of statements) walkAST(statement, node => {
    if (node.k !== 'Comp') return;
    if (node.name === 'ComposeMessage') inspectAction(node);
    if (node.name === 'Action') {
      const kinds = inspectAction(node);
      if (kinds.has('compose') && kinds.has('send')) throw new Error('ComposeMessage cannot be combined with SendToChat or Mutation');
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
 *   options.withOptions: Also return each choice field's normalized option list. Only the
 *     private draft read (409 field comparison) asks for it: a background entering model
 *     input must stay byte-identical, so this stays off by default.
 * Returns:
 *   A canonical snapshot and readable fields; state is user data, never authority.
 */
export function interactionState(schema: InteractiveSchema, input: unknown, options: {withOptions?: boolean} = {}) {
  if (!input || typeof input !== 'object' || Array.isArray(input) || Buffer.byteLength(JSON.stringify(input), 'utf8') > 16384)
    throw new Error('Interaction state must be an object within 16 KiB');
  const state = JSON.parse(sortedJsonAscii(input)) as Record<string, unknown>;
  const parsed = parser.parse(schema.source);
  const unwrap = (value: unknown): unknown => value && typeof value === 'object' && 'value' in value ? value.value : value;
  const named = new Map(split(tokenize(schema.source)).map(statement => [statement.id, parseExpression(statement.tokens)]));
  const ctx: EvaluationContext = {
    actions: interactiveCatalog.actions,
    functions: interactiveRuntimeFunctions,
    getState: name => unwrap(Object.hasOwn(state, name) ? state[name] : parsed.stateDeclarations[name]),
    resolveRef: name => {
      const query = parsed.queryStatements.find(item => item.statementId === name);
      const expression = query?.defaultsAST ?? named.get(name);
      return expression ? evaluate(expression, ctx) : undefined;
    },
  };
  const labels: Record<string, number> = {Input:1, TextArea:1, Select:2, RadioGroup:2, Slider:4, Checkbox:1, DatePicker:1};
  const fields: {name:string; label:string; value:unknown; display_value?:string; options?:{label:string;value:string}[]}[] = [];
  const seen = new Set<string>();
  for (const statement of split(tokenize(schema.source))) walkAST(parseExpression(statement.tokens), node => {
    if (node.k !== 'Comp' || !(node.name in labels || node.name === 'SegmentedControl')) return;
    const binding = node.args[0];
    if (binding?.k !== 'StateRef' || seen.has(binding.n)) return;
    seen.add(binding.n);
    const value = ctx.getState!(binding.n);
    const labelNode = node.name in labels ? node.args[labels[node.name]] : undefined;
    const label = labelNode ? evaluate(labelNode, ctx) : undefined;
    const choices = ['Select','RadioGroup','SegmentedControl'].includes(node.name) ? evaluate(node.args[1], ctx) : undefined;
    const selected = Array.isArray(choices) ? choices.find(option => typeof option === 'string' ? option === value : option?.value === value) : undefined;
    // The catalogue allows bare strings; expand them so one shape reaches every client.
    const optionList = options.withOptions && Array.isArray(choices)
      ? choices.map(option => typeof option === 'string' ? {label:option, value:option}
        : {label:String(option?.label ?? option?.value ?? ''), value:String(option?.value ?? '')})
      : undefined;
    fields.push({name:binding.n, label:typeof label === 'string' ? label : binding.n.slice(1), value,
      ...(selected ? {display_value:typeof selected === 'string' ? selected : selected.label} : {}),
      ...(optionList ? {options:optionList} : {})});
  });
  return {state, fields};
}

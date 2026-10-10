/** Nano guest helpers run inside the public native JavaScript PTC runtime. */
export function workflowProgram(script: string, args: unknown): string {
  return `const args = ${JSON.stringify(args ?? null)};
const phase = title => nanoWorkflow.phase({title});
const log = text => nanoWorkflow.log({text: String(text)});
const budget = Object.freeze({spent: () => nanoWorkflow.budget({kind: 'spent'}), remaining: () => nanoWorkflow.budget({kind: 'remaining'})});
const agent = (prompt, options = {}) => nanoWorkflow.agent({prompt, options});
const workflow = (reference, args = null) => nanoWorkflow.workflow({reference, args});
const attempt = async fn => { try { return await fn(); } catch(error) { if (error instanceof NanoWorkflowError) throw error; return null; } };
const parallel = async thunks => {
  if (!Array.isArray(thunks) || thunks.length > 4096) throw new Error('parallel requires at most 4096 functions');
  return Promise.all(thunks.map(fn => attempt(fn)));
};
const pipeline = async (items, ...stages) => {
  if (!Array.isArray(items) || items.length > 4096) throw new Error('pipeline requires at most 4096 items');
  return Promise.all(items.map((item, index) => attempt(async () => {
    let value = item;
    for (const stage of stages) { value = await stage(value, item, index); if (value === null) break; }
    return value;
  })));
};
${script}`;
}

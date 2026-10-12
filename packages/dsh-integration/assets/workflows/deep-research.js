// nano-workflow: {"name":"deep-research","description":"Research a question broadly, verify evidence, and synthesize it","whenToUse":"Use when the human explicitly asks for deep, multi-agent research"}
const topic = typeof args === 'string' ? args : JSON.stringify(args);
await phase('Research');
const findings = await parallel([
  () => agent(`Research primary and official sources for: ${topic}`, {label:'primary-sources'}),
  () => agent(`Find independent evidence and counterarguments for: ${topic}`, {label:'independent-evidence'}),
  () => agent(`Audit omissions, uncertainty, and stale claims for: ${topic}`, {label:'completeness-critic'}),
]);
await phase('Synthesize');
return await agent(`Synthesize a source-aware answer for ${topic}. Reconcile these findings and preserve uncertainty: ${JSON.stringify(findings)}`, {label:'synthesis'});

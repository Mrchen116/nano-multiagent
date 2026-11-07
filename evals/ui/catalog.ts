import {readFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {coordination,type CaseGraph,type Primitive,type CaseRun} from './coordination.js';
export const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
export interface Stage {id:string;title:string;kind:'native'|'product';sessionId?:string;url?:string}
export interface EvaluationCase {id:string;title:string;experiment?:{id:string;title:string};prompt?:string;photoUrls?:string[];reference?:string;attachments?:string[];workspaceFiles?:string[];steps?:string[];criteria?:Array<{id:string;title:string}>;context?:string;graph?:CaseGraph;primitives?:Record<string,Primitive>;runs?:Record<string,CaseRun>;stages:Stage[];notice:string}
export interface Suite {id:string;title:string;description:string;cases:EvaluationCase[]}
/** Public case catalog. Scoring and runtime protocols remain owned by each capability. */
export async function catalog(evidence?:string,coordRun?:string):Promise<Suite[]> {
  const dataset=JSON.parse(await readFile(join(root,'evals/intelligent-ui/dataset.json'),'utf8'));
  const links=evidence?JSON.parse(await readFile(evidence,'utf8')): {};
  const memory=JSON.parse(await readFile(join(root,'evals/memory/examples/synthetic.json'),'utf8'));
  const alignmentRoot=join(root,'evals/spec_design_alignment');
  const alignment=JSON.parse(await readFile(join(alignmentRoot,'dataset.json'),'utf8'));
  const alignmentCases:EvaluationCase[]=await Promise.all(alignment.cases.map(async(entry:{case_id:string;title:string;case_ref:string;status:string})=>{
    const file=join(alignmentRoot,entry.case_ref);
    const spec=JSON.parse(await readFile(file,'utf8'));
    return {id:'alignment:'+entry.case_id,title:entry.case_id+' · '+entry.title,prompt:await readFile(join(dirname(file),spec.brief_ref),'utf8'),
      context:spec.stratum+' · '+spec.artifact_contract+' · '+spec.terminal_mode,stages:[],
      notice:'状态 '+entry.status+' · 本页展示公开输入。判定材料与候选输入分别维护。'};
  }));
  return [
    {id:'memory',title:'Memory',description:'LongMemEval · 准备记忆、冷上下文答题与评分',cases:memory.map((q:{question_id:string;question_type:string;question:string;haystack_dates:string[];haystack_sessions:Array<Array<{role:string;content:string}>>})=>({
      id:'memory:'+q.question_id,title:q.question_id+' · '+q.question_type,prompt:q.question,
      context:q.haystack_sessions.map((messages,i)=>q.haystack_dates[i]+'\n'+messages.map(m=>m.role+' · '+m.content).join('\n')).join('\n\n'),
      stages:[],notice:'公开合成样例 · 尚未运行。私有真实题集与单题归档通过原 Memory 评测流程挂接。'}))},
    {id:'intelligent-ui',title:'Intelligent UI',description:'酒店、看板、会议确认和广告分析 · 四个独立空白上下文 case',cases:dataset.cases.map((c:EvaluationCase)=>({ ...c,context:'每次运行、每个 case 使用全新 IM 身份、聊天、workspace、DSH home；首条输入前消息为零。只保留本 case 必需后续操作，不追加纠错提示。',notice:links[c.id]?'挂接已有独立复测现场；不是本页面重新执行的结果。视觉与操作需人工核对。':'Case 已建档，尚未执行。公共页面不会自动调用模型或把生成源码判为通过。',stages:links[c.id]?[{id:'product',title:'实际产品',kind:'product',url:links[c.id].url}]:[]}))},
    {id:'spec-design-alignment',title:'Spec/design alignment',description:'八个历史回归与前瞻 pilot case',cases:alignmentCases},
    await coordination(coordRun),
  ];
}

import {readFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
export const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
export interface Stage {id:string;title:string;kind:'native'|'product';sessionId?:string;url?:string}
export interface EvaluationCase {id:string;title:string;experiment?:{id:string;title:string};prompt?:string;photoUrls?:string[];reference?:string;steps?:string[];criteria?:Array<{id:string;title:string}>;context?:string;stages:Stage[];notice:string}
export interface Suite {id:string;title:string;description:string;cases:EvaluationCase[]}
/** Public case catalog. Scoring and runtime protocols remain owned by each capability. */
export async function catalog(evidence?:string):Promise<Suite[]> {
  const dataset=JSON.parse(await readFile(join(root,'evals/intelligent-ui/dataset.json'),'utf8'));
  const links=evidence?JSON.parse(await readFile(evidence,'utf8')): {};
  return [
    {id:'memory',title:'Memory',description:'LongMemEval · 沿用现有准备、冷答题和评分协议',cases:[]},
    {id:'intelligent-ui',title:'Intelligent UI',description:'酒店、看板、会议确认和活动试算 · 四个独立空白上下文 case',cases:dataset.cases.map((c:EvaluationCase)=>({ ...c,context:'每次运行、每个 case 使用全新 IM 身份、聊天、workspace、DSH home；首条输入前消息为零。只保留本 case 必需后续操作，不追加纠错提示。',notice:links[c.id]?'挂接已有独立复测现场；不是本页面重新执行的结果。视觉与操作需人工核对。':'Case 已建档，尚未执行。公共页面不会自动调用模型或把生成源码判为通过。',stages:links[c.id]?[{id:'product',title:'实际产品',kind:'product',url:links[c.id].url}]:[]}))},
  ];
}

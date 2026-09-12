const fs=require('fs'), vm=require('vm'), assert=require('assert');
// Pass the official binary matching the SHA-256 in the companion report.
const crypto=require('crypto');
const binary=fs.readFileSync(process.argv[2]);
assert.strictEqual(crypto.createHash('sha256').update(binary).digest('hex'),'a681f3008f0050029aeebcab3af51bb6a55ddeb625a3af3141a4416d43cd2558');
const source=binary.subarray(168307126,168316055).toString('utf8');
// Boundary dependencies are restricted to ordinary native human turns and ASCII text.
// No feature config, model request, permission decision, or installed file is modified.
const cx={Set,Map,j:(a,f)=>a.filter(f).length, cAs:2000,Az:2000,Ts:'AskUserQuestion',oAs:new Set(),
 hTr:()=>({sources:[],readToolUseIds:new Map(),malformedSources:0,truncatedOwnerRows:0}),ATn:()=>new Map(),
 WAe:()=>new Set(),RA:o=>o?.kind==='human',
 zHt:m=>({frame:m.origin?.kind==='human'?'human':'invisible',kind:'human',reason:'test-no-source'}),
 pPt:()=>false,ube:()=>undefined,dTr:()=>'',ZRt:s=>s,pk:s=>s,
 ud:(s,n)=>s.length<=n?s:s.slice(-n),lfr:()=>{},
}; vm.createContext(cx);vm.runInContext(source,cx);
const human=text=>({type:'user',origin:{kind:'human'},message:{content:text}});
const assistant=text=>({type:'assistant',message:{model:'test-model',content:[{type:'text',text}]}});
const tool=(id,text)=>({type:'assistant',message:{model:'test-model',content:[...(text?[{type:'text',text}]:[]),{type:'tool_use',id,name:'Bash',input:{command:'git push --force origin main'}}]}});
cx.zl='virtual-model';
const base=[human('INITIAL_USER'),assistant('PROPOSAL: force-push main?'),human('Yes.'),tool('action','CURRENT_NARRATION')];
const cases={
 disabled:cx.yTr(base,false,false),
 enabled:cx.yTr(base,true,false),
 unanswered:cx.yTr([human('INITIAL_USER'),assistant('PROPOSAL: force-push main?'),tool('action','CURRENT_NARRATION')],true,false),
 latest_assistant_only:cx.yTr([human('INITIAL_USER'),assistant('OLDER_PROPOSAL'),assistant('LATEST_PROPOSAL'),human('Yes.'),tool('action')],true,false),
 intervening_agent:cx.yTr([human('INITIAL_USER'),assistant('PROPOSAL'),{type:'user',origin:{kind:'peer'},message:{content:'PEER_CONTENT'}},human('Yes.'),tool('action')],true,false),
 long_proposal:cx.yTr([human('INITIAL_USER'),assistant('HEAD_SENTINEL'+'x'.repeat(2500)+'TAIL_SENTINEL'),human('Yes.'),tool('action')],true,false),
};
function prose(v){return JSON.parse(JSON.stringify(v)).filter(e=>e.role==='assistant').flatMap(e=>e.content.filter(c=>c.type==='text').map(c=>c.text));}
assert.deepStrictEqual(prose(cases.disabled),[]);assert.deepStrictEqual(prose(cases.enabled),['PROPOSAL: force-push main?']);
assert.deepStrictEqual(prose(cases.unanswered),[]);assert.deepStrictEqual(prose(cases.latest_assistant_only),['LATEST_PROPOSAL']);
assert.deepStrictEqual(prose(cases.intervening_agent),[]);assert.strictEqual(prose(cases.long_proposal)[0].length,2000);assert(!prose(cases.long_proposal)[0].includes('HEAD_SENTINEL'));assert(prose(cases.long_proposal)[0].endsWith('TAIL_SENTINEL'));
const out={method:'Extracted 2.1.267 yTr function in isolated Node VM; boundary dependencies stubbed for ordinary human ASCII fixtures; NOT live CLI/API behavior',cases,checks:'6 passed'};
console.log('6 projection fixture checks passed; enabled assistant tail length',prose(cases.long_proposal)[0].length);

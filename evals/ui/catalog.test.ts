import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';import {join} from 'node:path';import {tmpdir} from 'node:os';
import {it,expect} from 'vitest';import {catalog,root} from './catalog.js';
it('registers four separate UI cases with fixed references, workflow, rubric and a fresh-context requirement',async()=>{
 const suites=await catalog();expect(suites.map(s=>s.id)).toEqual(['memory','intelligent-ui']);const cases=suites[1].cases;
 expect(cases.map(c=>c.id)).toEqual(['hotel','dashboard','meeting-confirmation','activity-budget']);
 for(const c of cases){expect(c.context).toContain('全新');expect(c.steps!.length).toBeGreaterThan(0);expect(c.criteria!.length).toBeGreaterThan(0);expect(c.stages).toEqual([]);if(c.reference)expect((await readFile(join(root,'evals/intelligent-ui/assets',c.reference))).length).toBeGreaterThan(1000)}
 const dataset=JSON.parse(await readFile(join(root,'evals/intelligent-ui/dataset.json'),'utf8'));
 expect(dataset.version).toBe(2);expect(dataset.protocol).toBe('fresh-product-context-v1');const activity=cases.find(c=>c.id==='activity-budget')!;expect(activity.prompt).not.toMatch(/Intelligent UI|组件|卡片|SVG/i);expect(activity.reference).toBeUndefined();expect(dataset.cases[2].prompt).not.toContain('带上预算草案');expect(dataset.cases[2].expected).toHaveLength(3);
});
it('labels attached prior evidence without pretending to have run or graded the new cases',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'eval-catalog-'));try{
  const file=join(dir,'links.json');await writeFile(file,JSON.stringify({hotel:{url:'http://127.0.0.1:12345/chat/test'}}));
  const suites=await catalog(file);const c=suites[1].cases[0];expect(c.notice).toContain('不是本页面重新执行');expect(c.stages[0].url).toContain('/chat/test');
 }finally{await rm(dir,{recursive:true,force:true})}
});

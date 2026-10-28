import {mkdtemp, writeFile, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect, it} from 'vitest';
import {load} from 'js-yaml';
import {canonicalAgentConfiguration} from '@nano/product-contracts';
import {builtinSkillsRoot} from '@nano/personal-assistant';
import {NodeConfiguration, type NodeConfigurationFile} from '../src/configuration.js';
import {projectCapabilities} from '../src/capabilities.js';

it.each(['explicit_allowlist', 'explicit_denylist'])('normalizes retired switches and fixed Skill while preserving %s and file-owned knowledge', async mode => {
  const home = await mkdtemp(join(tmpdir(), 'nano-memory-config-'));
  try {
    const path = join(home, 'node.json');
    const knowledge = {memoryMode: 'legacy', legacyMemory: {enabled:false, interval:17}, dreaming:{quietMs:123, intervalMs:456}};
    await writeFile(path, JSON.stringify({node:{}, agents:[{agent_id:'a',workspace_root:home,knowledge,features:{memory_curation:false,skill_creation:false,dreaming:false},skills_selection_mode:mode,skills:['skill-creator','other'],tool_allowlist:['read']}],llm:{default_model:'test',providers:[{name:'test',models:[{name:'test'}]}]}}));
    const config = await NodeConfiguration.read(path);
    const current = config.current('a')!;
    expect(current.features).toEqual({dreaming:false});
    expect(current.skills).toEqual(['other']);
    expect(current.skills_selection_mode).toBe(mode);
    const runtime = config.runtime(current);
    expect(runtime.knowledge).toMatchObject(knowledge);
    expect(runtime.skillRoots).toContainEqual({path:builtinSkillsRoot,source:'builtin'});
    expect(projectCapabilities({tools:[],skills:[{name:'skill-creator',description:'fixed'}]},config.value,runtime).features.map(feature=>feature.key)).not.toContain('dreaming');
    expect(projectCapabilities({tools:[],skills:[{name:'skill-creator',description:'fixed'}]},config.value,runtime).skills).toEqual([]);
    await config.persist(canonicalAgentConfiguration({...current,custom_prompt:'edited',knowledge:{memoryMode:'document',legacyMemory:{enabled:true}}}));
    const restored = await NodeConfiguration.read(path);
    expect(restored.runtime(restored.current('a')!).knowledge).toMatchObject(knowledge);
    expect((load(await readFile(path,'utf8')) as NodeConfigurationFile).agents[0].knowledge).toMatchObject(knowledge);
    expect(restored.current('a')?.tool_allowlist).toEqual(['read']);
  } finally {await rm(home,{recursive:true,force:true});}
});

it('defaults document and Dreaming independently of retired false settings', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-memory-default-'));
  try {
    const path=join(home,'node.json');
    await writeFile(path,JSON.stringify({node:{},agents:[{agent_id:'a',workspace_root:home,knowledge:{memoryInterval:23},features:{memory_curation:false,skill_creation:false}}],llm:{default_model:'test',providers:[{name:'test',models:[{name:'test'}]}]}}));
    const config=await NodeConfiguration.read(path);
    expect(config.runtime(config.current('a')!)).toMatchObject({features:{dreaming:true},knowledge:{memoryMode:'document',legacyMemory:{enabled:false,interval:23}}});
    await config.persist(config.current('a')!);
    const saved=(load(await readFile(path,'utf8')) as NodeConfigurationFile).agents[0];
    expect(saved.features).toEqual({dreaming:true});
    expect(saved.knowledge).toMatchObject({memoryMode:'document',legacyMemory:{enabled:false,interval:23}});
    expect(saved.knowledge).not.toHaveProperty('memoryInterval');
  }finally{await rm(home,{recursive:true,force:true});}
});


it('saves an upgraded unavailable Dreaming default without expanding explicit tools', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-memory-restricted-'));
  try {
    const path=join(home,'node.json');
    await writeFile(path,JSON.stringify({node:{},agents:[{agent_id:'a',workspace_root:home,tool_allowlist:['read'],features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false}}],llm:{default_model:'test',providers:[{name:'test',models:[{name:'test'}]}]}}));
    const config=await NodeConfiguration.read(path);
    const candidate=await config.resolve({...config.current('a')!,custom_prompt:'new'},false);
    await config.persist(candidate);
    const runtime=config.runtime(config.current('a')!);
    expect(runtime.toolAllowlist).toEqual(['read']);
    const feature=projectCapabilities({tools:['read','write','edit','memory_maintenance'].map(name=>({name,description:name})),skills:[]},config.value,runtime).features.find(feature=>feature.key==='dreaming');
    expect(feature).toMatchObject({default_on:true,available:false,missing_tools:['write','edit','memory_maintenance']});
  }finally{await rm(home,{recursive:true,force:true});}
});

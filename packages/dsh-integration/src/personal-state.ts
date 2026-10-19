import { createHash } from 'node:crypto';
import { readFile, unlink } from 'node:fs/promises';
import { defineDomain, domainTable, type Domain, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import type { Context } from '@deepseek-ai/cordis';
interface Document {agentId:string;path:string;hash:string;revoked:boolean;sources:unknown[]}
interface Retired {agentId:string;sessionId:string;at:number}
interface State extends DomainSpec {tables:{documents:DomainTableSpec<string,Document>;retired:DomainTableSpec<string,Retired>}}
const schema:State=defineDomain({name:'nano_personal_sources',version:1,layout:'per-record',tables:{
  documents:domainTable(z.object({agentId:z.string(),path:z.string(),hash:z.string(),revoked:z.boolean(),sources:z.array(z.unknown())})),
  retired:domainTable(z.object({agentId:z.string(),sessionId:z.string(),at:z.number()})),
}});
const key=(value:string)=>Buffer.from(value).toString('base64url');
const hash=(value:string)=>createHash('sha256').update(value).digest('hex');
/** Durable provenance for generated documents and retired execution contexts. */
export class PersonalState {
  private readonly domain:Promise<Domain<State>>;
  constructor(ctx:Context){this.domain=ctx.storageDomain.open(schema);ctx.effect(()=>async()=>{await(await this.domain).close();});}
  async isRetired(sessionId:string){return !!(await this.domain).table('retired').get(key(sessionId));}
  async checkDocument(path:string){if((await this.domain).table('documents').get(key(path))?.revoked)throw new Error('Document source was revoked; recreate from currently allowed sources');}
  async record(agentId:string,path:string,content:string,sources:unknown[],revoked=false){await(await this.domain).table('documents').put(key(path),{agentId,path,hash:hash(content),sources,revoked});}
  async retire(agentId:string,sessionIds:string[]){
    const domain=await this.domain;
    for(const sessionId of sessionIds)await domain.table('retired').put(key(sessionId),{agentId,sessionId,at:Date.now()});
    for(const [id,document]of domain.table('documents').entries())if(document.agentId===agentId){
      // Persist exclusion first. A crash or an owner edit never makes stale data readable.
      await domain.table('documents').put(id,{...document,revoked:true});
      try{if(hash(await readFile(document.path,'utf8'))===document.hash)await unlink(document.path);}
      catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
    }
  }
}

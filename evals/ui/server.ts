import {createServer} from 'node:http';
import {randomUUID} from 'node:crypto';
import {readFile,mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import {extname,join,resolve,sep,basename} from 'node:path';
import {parseArgs} from 'node:util';
import {pathToFileURL} from 'node:url';
import {root,catalog,type Suite} from './catalog.js';

export interface ArchiveReader {sessions:Array<{sessionId:string;title:string;stage:string}>;request(input:Record<string,unknown>):Promise<unknown>;close():Promise<void>}
const mime:Record<string,string>={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.jpg':'image/jpeg','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
export async function startViewer(options:{suites:Suite[];archive?:ArchiveReader;report?:string;statePath?:string}) {
  const token=randomUUID();const server=createServer(async(req,res)=>{
    const json=(status:number,value:unknown)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(value))};
    const file=async(base:string,name:string,cors=false)=>{
      const path=resolve(base,name);if(!path.startsWith(resolve(base)+sep))throw new Error('Invalid asset');
      const bytes=await readFile(path);res.writeHead(200,{'Content-Type':mime[extname(path)]??'application/octet-stream',...(cors?{'Access-Control-Allow-Origin':'*'}:{})});res.end(bytes);
    };
    try {
      const path=new URL(req.url!,'http://localhost').pathname;
      if(path.startsWith('/trajectory/')){await file(join(root,'packages/dsh-trajectory-viewer/dist'),decodeURIComponent(path.slice(12))||'index.html',true);return}
      if(path===`/${token}/`||path===`/${token}/app.js`||path===`/${token}/native.js`){await file(join(root,'evals/ui'),path.endsWith('app.js')?'app.js':path.endsWith('native.js')?'native.js':'index.html');return}
      if(req.headers['x-viewer-token']!==token){json(403,{error:'Local viewer capability required'});return}
      if(path==='/api/catalog'){json(200,{suites:options.suites});return}
      if(path==='/api/reference') {
        const name=new URL(req.url!,'http://localhost').searchParams.get('name');
        if(!options.suites.flatMap(s=>s.cases).some(c=>c.reference===name))throw new Error('Unknown reference');
        await file(join(root,'evals/intelligent-ui/assets'),name!);return;
      }
      if(path==='/api/report'){json(200,{text:options.report??'当前只建档 case，尚未启动正式评测。'});return}
      if(path==='/api/trajectory'&&req.method==='POST'&&options.archive){
        let body='';for await(const chunk of req){body+=chunk;if(body.length>65536)throw new Error('Request too large')}
        json(200,await options.archive.request(JSON.parse(body)));return;
      }
      json(404,{error:'Not found'});
    }catch(error){json(400,{error:String(error)})}
  });
  await new Promise<void>(done=>server.listen(0,'127.0.0.1',done));
  const url=`http://127.0.0.1:${(server.address() as {port:number}).port}/${token}/`;
  if(options.statePath)await writeFile(options.statePath,JSON.stringify({pid:process.pid,url},null,2));
  return {url,server,async close(){server.closeAllConnections();await new Promise<void>(done=>server.close(()=>done()));await options.archive?.close()}};
}
export async function main(args:string[]) {
  const {values}=parseArgs({args,options:{'memory-archive':{type:'string'},'ui-evidence':{type:'string'},output:{type:'string'},help:{type:'boolean'}}});
  if(values.help){console.log('pnpm eval-ui [--memory-archive EXPERIMENT_DIR] [--ui-evidence LINKS.json] [--output NEW_DIR]\nOnly reads cases and archived evidence; no evaluation/model execution.');return}
  const output=resolve(values.output??join(root,'output/eval-ui'));await mkdir(output,{recursive:true});
  const suites=await catalog(values['ui-evidence']);let archive:ArchiveReader|undefined;let report:string|undefined;
  if(values['memory-archive']){
    const path=resolve(values['memory-archive']);const scratch=await mkdtemp(join(output,'archive-'));
    // open() requires a new child so the original archived runtime remains untouched.
    const result=JSON.parse(await readFile(join(path,'run/report.json'),'utf8'));
    if(result.results.length!==1)throw new Error('This legacy archive adapter expects one case per archive; do not attribute shared sessions to multiple cases');
    const caseId=String(result.results[0].questionId);
    report=await readFile(join(path,'trial-summary.md'),'utf8');
    const {EvaluationArchive}=await import('@nano/node/evaluation-archive');archive=await EvaluationArchive.open(path,join(scratch,'copy'));
    suites[0].cases.push({id:'memory:'+caseId,title:caseId,experiment:{id:basename(path),title:basename(path)},notice:'只读原生轨迹。导入历史带 imported-history 来源；离线适配器不等于完整 IM→Node 链路。原件不修改，查看器不启动评测或模型执行。',stages:archive.sessions.map(s=>({id:s.sessionId,title:s.title,kind:'native',sessionId:s.sessionId}))});
  }
  let viewer:Awaited<ReturnType<typeof startViewer>>;
  try{viewer=await startViewer({suites,archive,report,statePath:join(output,'state.json')})}catch(error){await archive?.close();throw error}
  console.log(viewer.url);
  const stop=()=>{void viewer.close().catch(error=>console.error(error))};process.once('SIGINT',stop);process.once('SIGTERM',stop);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)main(process.argv.slice(2)).catch(error=>{console.error(error);process.exitCode=1});

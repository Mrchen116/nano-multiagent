import type { Context } from '@deepseek-ai/cordis';
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { open, realpath } from 'node:fs/promises';
import { basename, extname, resolve } from 'node:path';
import { safePath } from './knowledge/files.js';
import type {} from './agent-config.js';
import type {} from './product-bridge.js';

const MAX_BYTES = 10 * 1024 * 1024;
const types: Record<string, string> = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.pdf':'application/pdf','.txt':'text/plain','.md':'text/markdown','.json':'application/json'};
interface PublishArgs { path: string; idempotency_key: string; artifact_id?: string; expected_version?: number }

/** Register private file publication; the product host chooses the owner's chat.
 *
 * Args:
 *   ctx: Root PA tool scope with trusted configuration and product bridge services.
 */
export function registerTool(ctx: Context) {
  ctx.tools.register({name:'publish_artifact',description:'Upload a real file from your workspace to the owner’s private chat storage. Supported: PNG/JPEG/GIF/WebP, PDF, TXT, Markdown and JSON; maximum 10 MiB. Supply a stable idempotency_key and reuse it for uncertain retries of the same bytes. To revise a published artifact, supply its artifact_id and current expected_version; previous versions remain readable. The returned receipt means stored, not a message sent: send the returned resource URL to the owner with send_message. External delivery still requires the normal reviewed send path. Local paths are never usable delivery URLs.',
    parameters:{type:'object',properties:{path:{type:'string'},idempotency_key:{type:'string',minLength:1,maxLength:200},artifact_id:{type:'string'},expected_version:{type:'integer',minimum:1}},required:['path','idempotency_key'],additionalProperties:false},
    output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},
    execute:async (value,exec)=>{
      const agent = exec.agent;
      const config = agent && ctx.nanoConfiguration.forAgent(agent);
      if (!config?.personal || config.mode !== 'global' || !config.workspace) throw new Error('Publication requires a bound Personal Agent workspace');
      if (agent!.session.header.origin === 'subagent') throw new Error('Only the root Personal Agent may publish artifacts');
      const args = value as PublishArgs;
      if (!args.path || !args.idempotency_key?.trim() || args.idempotency_key.length > 200) throw new Error('Path and a bounded idempotency key are required');
      if ((args.artifact_id !== undefined) !== (args.expected_version !== undefined) || (args.expected_version !== undefined && (!Number.isSafeInteger(args.expected_version) || args.expected_version < 1))) throw new Error('Artifact updates require artifact_id and expected_version');
      const root = await realpath(config.workspace), path = resolve(root,args.path);
      await safePath(root,path);
      const actualPath = await realpath(path);
      await safePath(root,actualPath);
      const contentType = types[extname(path).toLowerCase()];
      if (!contentType) throw new Error('Unsupported artifact file type');
      exec.signal.throwIfAborted();
      const file = await open(actualPath, constants.O_RDONLY | constants.O_NOFOLLOW);
      let bytes: Buffer;
      try {
        const stat = await file.stat();
        if (!stat.isFile() || !stat.size || stat.size > MAX_BYTES) throw new Error('Artifact must be a non-empty regular file within the 10 MiB size limit');
        // Read at most one byte beyond the limit even if a producer grows the file.
        const buffer = Buffer.allocUnsafe(MAX_BYTES + 1); let size = 0;
        while (size < buffer.length) {
          exec.signal.throwIfAborted();
          const {bytesRead} = await file.read(buffer,size,buffer.length-size,null);
          if (!bytesRead) break;
          size += bytesRead;
        }
        if (!size || size > MAX_BYTES) throw new Error('Artifact exceeds the size limit or is empty');
        bytes = buffer.subarray(0,size);
      } finally { await file.close(); }
      return ctx.nanoProduct.call('publish_artifact',{
        file_name:basename(path),content_type:contentType,data_base64:bytes.toString('base64'),sha256:createHash('sha256').update(bytes).digest('hex'),byte_size:bytes.length,
        idempotency_key:args.idempotency_key,...(args.artifact_id !== undefined ? {artifact_id:args.artifact_id,expected_version:args.expected_version} : {}),
      },exec);
    },
  });
}

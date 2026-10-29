import {expect,it,vi} from 'vitest';
import sharp from 'sharp';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import {personalFixture} from './personal-fixture.js';

it.each(['png','jpeg','webp'] as const)('freezes and copies the exact decoded %s image after independent review',async format=>{
 const {ctx,db,service,principal,args}=personalFixture();ctx.gateway.groupReply=vi.fn();
 const root=mkdtempSync(join(tmpdir(),'pa-image-'));ctx.dbPath=join(root,'im.db');mkdirSync(join(root,'message-images'));
 try {
  const bytes=await sharp({create:{width:12,height:8,channels:3,background:'red'}})[format]().toBuffer();
  const sha=createHash('sha256').update(bytes).digest('hex');
  writeFileSync(join(root,'message-images','original'),bytes);
  db.prepare('INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)').run('image','chat','uploaded',sha,`image/${format}`,`photo.${format}`,bytes.length,'original');
  const p=await service.actions.prepareChecked(principal,{...args,request_key:'photo',representation:'owner',conversation_id:'peer',content:'Agreed image',attachments:[{url:'/im/v1/conversations/chat/images/image'}]});
  expect(p.evidence.payload.attachment_snapshots[0]).toMatchObject({base64:bytes.toString('base64'),sha256:sha,width:12,height:8});
  expect((db.prepare('SELECT payload_json FROM pa_operations WHERE operation_id=?').get(p.proposal_ref)!.payload_json as string)).not.toContain(bytes.toString('base64'));
  const v=service.actions.review(principal,{...args,proposal_ref:p.proposal_ref,payload_digest:p.payload_digest,evidence_digest:p.evidence_digest,verdict:{decision:'allow'}});
  const result=service.actions.commit(principal,{...args,proposal_ref:p.proposal_ref,verdict_ref:v.verdict_ref});
  const message=ctx.messaging.message(result.message_id);
  expect(message.attachments[0]!.url).toMatch(/^\/im\/v1\/conversations\/peer\/images\//);
  const copy=db.prepare("SELECT * FROM message_images WHERE conversation_id='peer'").get()!;
  writeFileSync(join(root,'message-images','original'),'changed after commit');
  expect(readFileSync(join(root,'message-images',String(copy.storage_name)))).toEqual(bytes);
 }finally{rmSync(root,{recursive:true,force:true});}
});

it('rejects fake media and changed resources, and never sends a denied image',async()=>{
 const {ctx,db,service,principal,args}=personalFixture();ctx.gateway.groupReply=vi.fn();
 const root=mkdtempSync(join(tmpdir(),'pa-image-risk-'));ctx.dbPath=join(root,'im.db');mkdirSync(join(root,'message-images'));
 try {
  const install=(bytes:Buffer,mime:string)=>{
   writeFileSync(join(root,'message-images','original'),bytes);
   db.prepare('INSERT OR REPLACE INTO message_images VALUES(?,?,?,?,?,?,?,?)').run('image','chat','uploaded',createHash('sha256').update(bytes).digest('hex'),mime,'image.png',bytes.length,'original');
  };
  const input={...args,request_key:'photo',representation:'owner',conversation_id:'peer',content:'Image',attachments:[{url:'/im/v1/conversations/chat/images/image'}]};
  install(Buffer.from('not an image'),'image/png');
  await expect(service.actions.prepareChecked(principal,input)).rejects.toThrow('attachment_image_decode_failed');
  const png=await sharp({create:{width:2,height:2,channels:3,background:'red'}}).png().toBuffer();
  install(png,'image/jpeg');
  await expect(service.actions.prepareChecked(principal,input)).rejects.toThrow('attachment_image_unsupported');
  install(png,'image/png');
  const p=await service.actions.prepareChecked(principal,input);
  service.actions.review(principal,{...args,proposal_ref:p.proposal_ref,payload_digest:p.payload_digest,evidence_digest:p.evidence_digest,verdict:{decision:'deny',reason:'Private details in the image'}});
  expect(()=>service.actions.commit(principal,{...args,proposal_ref:p.proposal_ref,verdict_ref:'invented'})).toThrow('independent_review_required');
  const retry=await service.actions.prepareChecked(principal,{...input,request_key:'permitted'});
  const verdict=service.actions.review(principal,{...args,proposal_ref:retry.proposal_ref,payload_digest:retry.payload_digest,evidence_digest:retry.evidence_digest,verdict:{decision:'allow'}});
  install(Buffer.from('new bytes'),'image/png');
  expect(await service.actions.commitChecked(principal,{...args,proposal_ref:retry.proposal_ref,verdict_ref:verdict.verdict_ref})).toMatchObject({state:'not_sent',changed_reason:'attachment_snapshot_changed'});
  expect(db.prepare("SELECT count(*) n FROM messages WHERE conversation_id='peer'").get()!.n).toBe(0);
 }finally{rmSync(root,{recursive:true,force:true});}
});

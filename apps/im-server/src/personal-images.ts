import sharp from 'sharp';
import { fail, type Row } from './context.js';

/** Decode bounded static images before freezing their dimensions and media type. */
export async function decodePersonalImages(snapshots:Row[]):Promise<Row[]> {
  const images=snapshots.filter(row=>row.content_type.startsWith('image/'));
  if(images.length>5||images.reduce((total,row)=>total+row.byte_size,0)>20*1024*1024)fail(422,'attachment_image_limit');
  return Promise.all(images.map(async row=>{
    if(row.byte_size>10*1024*1024)fail(422,'attachment_image_limit');
    try {
      const decoder=sharp(row.bytes,{animated:true,limitInputPixels:4096*4096});
      const metadata=await decoder.metadata();
      const types:Record<string,string>={png:'image/png',jpeg:'image/jpeg',webp:'image/webp'};
      if(!metadata.format||types[metadata.format]!==row.content_type||(metadata.pages??1)!==1||!metadata.width||!metadata.height||metadata.width>4096||metadata.height>4096)fail(422,'attachment_image_unsupported');
      await decoder.raw().toBuffer();
      return {...row,width:metadata.width,height:metadata.height};
    } catch(error) {
      if((error as {statusCode?:number}).statusCode)throw error;
      fail(422,'attachment_image_decode_failed');
    }
  }));
}

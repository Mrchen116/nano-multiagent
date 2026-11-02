// Extracted from the Memory case viewer. Native records stay in Agent Work's renderer.
export async function mountNative({container,session,api,status,navigate,active=()=>true,targetRunId}) {
  let current,frame,port,closed=false;
  const prepared=await api('trajectory',{type:'prepare',sessionId:session.sessionId});
  if(!active()){await api('trajectory',{type:'close',observerId:prepared.observerId});return async()=>{}}
  current=prepared;frame=document.createElement('iframe');frame.title='DSH 原生轨迹';frame.setAttribute('sandbox','allow-scripts');frame.src='/trajectory/index.html';container.replaceChildren(frame);
  const listener=event=>{
    if(event.source!==frame.contentWindow)return;
    if(event.data?.type==='nano-trajectory-ready') {
      const connection=new MessageChannel();port=connection.port1;
      port.onmessage=async event=>{
        const request=event.data;const replyPort=connection.port1;
        try {const value=await api('trajectory',{...request,observerId:current.observerId});replyPort.postMessage({type:'result',requestId:request.requestId,value})}
        catch(error){if(!closed)replyPort.postMessage({type:'error',requestId:request.requestId,code:'archive_read_failed',message:error.message})}
      };port.start();
      frame.contentWindow.postMessage({type:'nano-trajectory-init',sessionId:session.sessionId,version:current.version,assetBase:location.origin+'/trajectory/',...(targetRunId?{targetRunId}:{})},'*',[connection.port2]);
    }else if(event.data?.type==='viewer-status')status(event.data.state==='ready'?'已加载 · 只读':event.data.message||event.data.state);
    else if(event.data?.type==='viewer-navigate')navigate(event.data.run?.sessionId,event.data.run?.runId);
  };
  window.addEventListener('message',listener);
  return async()=>{closed=true;window.removeEventListener('message',listener);port?.close();frame?.remove();await api('trajectory',{type:'close',observerId:current.observerId}).catch(()=>{})};
}

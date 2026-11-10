// Study Desk managed gateway v1
// Route only highereconomicsrevision.co.uk/mysql-editor/api/* through this Worker.
// Frontend files and the economics website stay on their existing GitHub Pages.
const PREFIX='/mysql-editor/api/';
const METHODS={health:'GET',session:'GET',login:'POST',logout:'POST',call:'POST',run:'POST',job:'POST',stop:'POST'};
const MAX_BODY=1200000;
const json=(status,payload)=>new Response(JSON.stringify(payload),{status,headers:{
  'Content-Type':'application/json; charset=utf-8','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});

export async function handle(request,env,fetchOrigin=fetch){
  const url=new URL(request.url),action=url.pathname.slice(PREFIX.length);
  if(url.protocol!=='https:'&&!['127.0.0.1','localhost'].includes(url.hostname))return json(426,{error:'Open the editor using HTTPS.'});
  if(!url.pathname.startsWith(PREFIX)||!Object.hasOwn(METHODS,action))return json(404,{error:'Not found.'});
  if(request.method!==METHODS[action])return json(405,{error:'Method not allowed.'});
  if(request.headers.get('Upgrade'))return json(400,{error:'This API uses normal HTTPS requests.'});
  const origin=request.headers.get('Origin');
  if((origin&&origin!==url.origin)||request.headers.get('Sec-Fetch-Site')==='cross-site')return json(403,{error:'Open Study Desk on its own website.'});
  let target;
  try{
    target=new URL(env.ORIGIN_URL);
    if(target.protocol!=='https:'||target.username||target.password||target.search||target.hash||target.pathname!=='/'||!env.STUDY_ORIGIN_KEY||env.STUDY_ORIGIN_KEY.length<32)throw Error();
  }catch{return json(503,{error:'The home connection has not been configured.',code:'NOT_CONFIGURED'});}
  target.pathname='/api/'+action;
  const headers=new Headers({'X-Study-Origin-Key':env.STUDY_ORIGIN_KEY,
    'X-Study-Client-IP':request.headers.get('CF-Connecting-IP')||'unknown'});
  for(const key of ['Content-Type','Cookie','Origin','X-Study-CSRF','Sec-Fetch-Site']){
    const value=request.headers.get(key);if(value)headers.set(key,value);
  }
  let body;
  if(request.method==='POST'){
    if(request.headers.get('Content-Type')?.split(';')[0]!=='application/json')return json(415,{error:'Send JSON.'});
    if(Number(request.headers.get('Content-Length'))>MAX_BODY)return json(413,{error:'Request too large.'});
    const reader=request.body?.getReader(),chunks=[];let length=0;
    if(reader){for(;;){const {done,value}=await reader.read();if(done)break;length+=value.byteLength;if(length>MAX_BODY){await reader.cancel();return json(413,{error:'Request too large.'});}chunks.push(value);}}
    body=new Uint8Array(length);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength;}
  }
  try{
    const response=await fetchOrigin(target.toString(),{method:request.method,headers,body,
      redirect:'manual',signal:AbortSignal.timeout(25000)});
    if(!response.headers.get('Content-Type')?.includes('application/json'))throw Error('Origin offline');
    const outgoing=new Headers({'Content-Type':'application/json; charset=utf-8','Cache-Control':'private, no-store',
      'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'});
    for(const name of ['Set-Cookie','Retry-After']){const value=response.headers.get(name);if(value)outgoing.set(name,value);}
    return new Response(response.body,{status:response.status,headers:outgoing});
  }catch{return json(503,{error:'Your home computer is not reachable. Keep it on and start Study Desk.',code:'HOME_OFFLINE'});}
}

export default {fetch(request,env){return handle(request,env);}};

// Test-only same-origin edge adapter. It executes the actual Worker module and
// rewrites its HTTPS origin fetch to the disposable local origin test server.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {handle} from '../hosting/worker.mjs';

const root=path.resolve('dist'),port=Number(process.env.DESK_TEST_PORT||8700);
const remote=process.env.DESK_TEST_ORIGIN||'http://127.0.0.1:8791';
const env={ORIGIN_URL:'https://test-origin.example.com',STUDY_ORIGIN_KEY:process.env.DESK_TEST_KEY};
http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://127.0.0.1:'+port);
  if(url.pathname==='/mysql-editor'){res.writeHead(301,{Location:'/mysql-editor/'});res.end();return;}
  if(url.pathname.startsWith('/mysql-editor/api/')){
   const chunks=[];for await(const chunk of req)chunks.push(chunk);
   const request=new Request(url,{method:req.method,headers:req.headers,body:req.method==='POST'?Buffer.concat(chunks):undefined});
   const response=await handle(request,env,(target,options)=>fetch(remote+new URL(target).pathname,options));
   res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));return;
  }
  let relative=url.pathname.replace(/^\/mysql-editor\/?/,'');if(!relative||relative.endsWith('/'))relative+='index.html';
  const file=path.resolve(root,relative);if(!file.startsWith(root+path.sep))throw Error();
  const type={'.html':'text/html','.js':'text/javascript','.css':'text/css','.txt':'text/plain','.zip':'application/zip'}[path.extname(file)]||'application/octet-stream';
  res.writeHead(200,{'Content-Type':type});res.end(await readFile(file));
 }catch{res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');}
}).listen(port,'127.0.0.1',()=>process.stdout.write('Remote frontend test adapter ready\n'));

import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{handle} from '../hosting/worker.mjs';

const origin='https://highereconomicsrevision.co.uk';
const env={ORIGIN_URL:'https://study-desk-origin.example.com',STUDY_ORIGIN_KEY:'test-origin-key-'.repeat(4)};
test('only the exact editor API route is forwarded',async()=>{
  for(const path of ['/','/mysql-editor/','/mysql-editor/api/../outside','/mysql-editor/api/unknown']){
    const r=await handle(new Request(origin+path),env,()=>{throw Error('Must not forward');});assert.equal(r.status,404);
  }
});
test('cross-origin and method-changing requests are blocked before the origin',async()=>{
  let forwarded=false;
  const r=await handle(new Request(origin+'/mysql-editor/api/login',{method:'POST',headers:{Origin:'https://bad.example','Content-Type':'application/json'},body:'{}'}),env,()=>{forwarded=true;});
  assert.equal(r.status,403);assert.equal(forwarded,false);
  assert.equal((await handle(new Request(origin+'/mysql-editor/api/run'),env)).status,405);
});
test('the gateway injects its own secret, strips spoofed keys, and scopes routing',async()=>{
  const incoming=new Request(origin+'/mysql-editor/api/call',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json',Cookie:'session=example','X-Study-Origin-Key':'spoofed','X-Study-CSRF':'csrf'},body:'{"op":"schema"}'});
  const r=await handle(incoming,env,async(url,options)=>{
    assert.equal(url,'https://study-desk-origin.example.com/api/call');
    assert.equal(options.headers.get('X-Study-Origin-Key'),env.STUDY_ORIGIN_KEY);
    assert.equal(options.headers.get('X-Study-CSRF'),'csrf');
    assert.equal(options.redirect,'manual');
    return Response.json({database:'schoolwork'},{headers:{'Set-Cookie':'session=new; Secure; HttpOnly'}});
  });
  assert.equal(r.status,200);assert.match(r.headers.get('Cache-Control'),/no-store/);
  assert.equal(r.headers.get('Set-Cookie'),'session=new; Secure; HttpOnly');
  assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
});
test('oversized bodies and invalid origin configuration are refused',async()=>{
  const r=await handle(new Request(origin+'/mysql-editor/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:'x'.repeat(1200001)}),env,()=>{throw Error('Must not forward');});
  assert.equal(r.status,413);
  assert.equal((await handle(new Request(origin+'/mysql-editor/api/health'),{...env,ORIGIN_URL:'http://localhost:8791'})).status,503);
});
test('an offline tunnel or HTML challenge is a useful JSON offline response',async()=>{
  const r=await handle(new Request(origin+'/mysql-editor/api/health'),env,async()=>new Response('challenge',{headers:{'Content-Type':'text/html'}}));
  assert.equal(r.status,503);assert.equal((await r.json()).code,'HOME_OFFLINE');
  assert.equal(typeof worker.fetch,'function');
});

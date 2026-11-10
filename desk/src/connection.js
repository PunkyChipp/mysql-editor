// Same-origin cookie login for the public Pages frontend. No tunnel or account
// secrets belong in this bundle, localStorage, or a public repository.
export class RemoteConnection {
  constructor(base){
    this.base=new URL(base,location.href);this.csrf=null;this.waiting=null;this.health=null;
    this.panel=document.createElement('dialog');this.panel.className='connection-dialog';
    this.panel.addEventListener('cancel',e=>e.preventDefault());document.body.append(this.panel);
  }
  async raw(action,body){
    let response;
    try{response=await fetch(new URL(action,this.base),{method:body===undefined?'GET':'POST',
      credentials:'same-origin',headers:body===undefined?{}:{'Content-Type':'application/json',...(this.csrf?{'X-Study-CSRF':this.csrf}:{})},
      body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(30000)});}
    catch{throw Error('The home connection could not be reached. Check that your PC and Study Desk are running.');}
    if(!response.headers.get('Content-Type')?.includes('application/json'))throw Error('The backend route is not connected yet. Use Owner setup to finish connecting your home PC.');
    const value=await response.json();
    if(!response.ok){const error=Error(value.error||'The home connection did not complete the request.');error.status=response.status;throw error;}
    return value;
  }
  async request(action,body){
    if(!this.csrf)await this.connect();
    try{return await this.raw(action,body);}
    catch(error){
      if(error.status!==401)throw error;
      this.csrf=null;await this.connect();return this.raw(action,body);
    }
  }
  async connect(){
    if(this.waiting)return this.waiting;
    this.waiting=new Promise(resolve=>{
      this.panel.innerHTML=`<div class="connect-head"><span class="connect-mark">s:</span><span class="connect-label">YOUR PRIVATE WORKSPACE</span><h1>Welcome to your desk.</h1><p>The editor lives here. MySQL and Python run on your home PC.</p></div><div class="connect-body"><div id="remote-check" class="connect-status" role="status">Checking your home connection…</div><form id="remote-login" hidden><label class="field-label" for="remote-user">Username</label><input class="field-input" id="remote-user" autocomplete="username" required maxlength="80"><label class="field-label" for="remote-password" style="margin-top:17px">Password</label><input class="field-input" id="remote-password" type="password" autocomplete="current-password" required maxlength="256"><button class="button primary connect-submit" type="submit">Sign in & open workspace →</button></form><p id="remote-error" class="field-error" role="alert" hidden></p><div id="remote-test-results" class="connection-tests" hidden></div><div class="connect-actions"><button class="button outline" id="remote-retry">Test connection</button><a class="button ghost" href="./setup/" target="_blank" rel="noopener">Owner setup ↗</a></div><p class="field-note">Your password is sent over HTTPS to your own backend. The browser does not connect directly to your home network.</p></div>`;
      if(!this.panel.open)this.panel.showModal();
      const $=id=>this.panel.querySelector('#'+id);
      let checking=false,retry=null,attempts=0;
      const fail=error=>{$('remote-error').textContent=error.message;$('remote-error').hidden=false;};
      const finish=()=>{clearTimeout(retry);this.panel.close();resolve();};
      const waitReady=async()=>{
        for(;;){
          const health=await this.raw('health');this.health=health;
          if(health.ready){finish();return;}
          $('remote-check').textContent=health.runtime?.message||'Your home PC is preparing MySQL and Python…';
          await new Promise(resolve=>setTimeout(resolve,2000));
        }
      };
      const check=async()=>{
        clearTimeout(retry);if(checking)return;checking=true;$('remote-retry').disabled=true;$('remote-error').hidden=true;
        $('remote-check').textContent='Checking your home connection…';
        $('remote-test-results').hidden=false;$('remote-test-results').replaceChildren();
        const line=(name,ok)=>{const div=document.createElement('div');div.className=ok?'test-pass':'test-fail';div.textContent=(ok?'✓ ':'○ ')+name;$('remote-test-results').append(div);};
        line('Editor website loaded',true);
        try{
          const health=await this.raw('health');this.health=health;
          line('Website API route connected',true);line('Home PC reachable',health.home==='online');line('MySQL/Python runtime ready',!!health.ready);
          $('remote-login').hidden=false;$('remote-check').textContent=health.ready?'Your home workspace is online. Sign in to continue.':health.runtime?.message||'Home PC connected. Preparing the runtime…';
          try{const session=await this.raw('session');this.csrf=session.csrf;await waitReady();}
          catch(error){if(error.status!==401)throw error;}
        }catch(error){line('Home connection',false);$('remote-login').hidden=true;$('remote-check').textContent='Your home backend is not connected.';fail(error);}
        finally{checking=false;$('remote-retry').disabled=false;if(this.panel.open&&$('remote-login').hidden)retry=setTimeout(check,Math.min(30000,5000*++attempts));}
      };
      $('remote-retry').onclick=check;
      $('remote-login').onsubmit=async e=>{
        e.preventDefault();const button=e.submitter;button.disabled=true;$('remote-error').hidden=true;
        try{const result=await this.raw('login',{username:$('remote-user').value.trim(),password:$('remote-password').value});
          $('remote-password').value='';this.csrf=result.csrf;$('remote-login').hidden=true;await waitReady();}
        catch(error){this.csrf=null;fail(error);$('remote-login').hidden=false;}
        finally{button.disabled=false;}
      };
      check();
    });
    try{await this.waiting;}finally{this.waiting=null;}
  }
  async signOut(){
    if(this.csrf)await this.raw('logout',{});
    this.csrf=null;location.reload();
  }
}

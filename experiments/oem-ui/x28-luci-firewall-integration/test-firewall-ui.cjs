const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const template=fs.readFileSync(__dirname+'/files/usr/lib/lua/luci/view/vendor/firewall.htm','utf8');
const script=template.match(/<script>([\s\S]*?)<\/script>/)[1];
const fixture={firewall:{success:true,enabled:'1'},protection:{success:true,enabled:'1',ack:'1'},
 ipv4:{available:true,policies:{INPUT:'ACCEPT',FORWARD:'ACCEPT',OUTPUT:'ACCEPT'},filter:['<untrusted>'],nat:[]},
 ipv6:{available:false,policies:{},filter:[],nat:[]}};
const settle=()=>new Promise(r=>setImmediate(r));
function page({confirm=true,post={success:true,message:'Verified'},status=fixture}={}) {
 const nodes=new Map(),calls=[];
 function element(){return {disabled:false,checked:false,textContent:'',children:[],appendChild(x){this.children.push(x);}};}
 const context=vm.createContext({document:{createElement:element,getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);}},
  confirm:()=>confirm,fetch:async(url,options={})=>{calls.push({url,options});return {ok:true,json:async()=>structuredClone(options.method==='POST'?post:status)};}});
 vm.runInContext(script,context);return {nodes,calls};
}
(async()=>{
 let t=page();await settle();
 assert.equal(t.nodes.get('vendor-firewall').textContent,'Enabled');
 assert.equal(t.nodes.get('dos-protection').checked,true);
 assert.equal(t.nodes.get('ipv6-rules').textContent,'Rules unavailable');
 assert.match(t.nodes.get('ipv4-rules').textContent,/<untrusted>/); // Rendered as text, never HTML.
 await t.nodes.get('apply-protection').onclick();assert.equal(t.calls.length,1);
 t=page({confirm:false});await settle();t.nodes.get('dos-protection').checked=false;
 await t.nodes.get('apply-protection').onclick();assert.equal(t.calls.length,1);
 t=page();await settle();t.nodes.get('dos-protection').checked=false;
 await t.nodes.get('apply-protection').onclick();
 const write=t.calls.find(x=>x.options.method==='POST');
 assert.deepEqual(JSON.parse(write.options.body),{enabled:false});assert.match(write.url,/token=/);
 t=page({post:{success:false,message:'Not verified'}});await settle();t.nodes.get('dos-protection').checked=false;
 await t.nodes.get('apply-protection').onclick();
 assert.equal(t.nodes.get('firewall-message').textContent,'Not verified');
 assert.equal(t.nodes.get('apply-protection').disabled,true);
 assert.equal(t.nodes.get('refresh-firewall').disabled,false);
 t=page({status:{}});await settle();assert.equal(t.nodes.get('apply-protection').disabled,true);
 console.log('PASS: live-state rendering; unavailable data; no-op/cancelled writes; JSON/CSRF request; failure stays disabled until refreshed');
})().catch(e=>{console.error(e);process.exit(1);});

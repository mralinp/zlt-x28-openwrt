const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const base = __dirname + '/files/usr/lib/lua/luci/view/vendor/';
const fixture = {
  133: {success:true, wan_real_iface:'ccmni1', wan_ip:'22.1.2.3', apn_name:'mcinet'},
  213: {success:true, selectType:'IPV4V6', apnMTU:'1500', apnNatName:'1'},
  248: {success:true, apn_list:[
    {name:'Current', apnName:'mcinet', default_flag:'1', secret:'keep', unknown:12},
    {name:'Other', apnName:'other', default_flag:'0', secret:'also keep'}
  ]},
  3: {success:true, lanIp:'192.168.70.1', netMask:'255.255.255.0'}
};
const settle = () => new Promise(resolve => setImmediate(resolve));
function context(page, confirm = true, response = {success:true,message:'0'}) {
  const nodes = new Map(), requests = [];
  function element() {
    return {value:'', textContent:'', children:[], disabled:false, append(...x){this.children.push(...x);},
      appendChild(x){this.children.push(x);}, setAttribute(){}, add(o){this.children.push(o); if(o.selected)this.value=o.value;}};
  }
  const c = vm.createContext({document:{createElement:element, getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);}},
    Option: function(text,value,_default,selected){return {text,value,selected};}, confirm:()=>confirm,
    vcall: async body => { requests.push(body); return structuredClone(body.method === 'GET' ? fixture[body.cmd] : response); },
    fetch: async () => ({ok:true,json:async()=>({interfaces:[
      {name:'br0',up:true,addresses:['192.168.70.1/24'],members:['ra0','rai0','eth1']},
      {name:'ccmni1',up:true,addresses:['22.1.2.3/32'],default_route:true},
      {name:'ccmni2',up:true,addresses:['21.1.1.1/8']},
      {name:'ra0',up:true,addresses:[]},{name:'rai0',up:true,addresses:[]}
    ]})})});
  const script = fs.readFileSync(base + page, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
  vm.runInContext(script,c);
  return {nodes,requests,c};
}
(async () => {
  const pending = [], started = [];
  const helper = vm.createContext({fetch:(_url, options)=>new Promise(resolve=>{started.push(JSON.parse(options.body).cmd);pending.push(resolve);}), btoa:()=>'', atob:()=>''});
  vm.runInContext(fs.readFileSync(base+'_js.htm','utf8').match(/<script>([\s\S]*?)<\/script>/)[1],helper);
  const first=helper.vcall({cmd:1}), second=helper.vcall({cmd:2});
  await settle();assert.deepEqual(started,[1]);
  pending.shift()({ok:true,json:async()=>({success:true})});await first;await settle();
  assert.deepEqual(started,[1,2]);
  pending.shift()({ok:false,status:503});await assert.rejects(second,/HTTP 503/);
  const third=helper.vcall({cmd:3});await settle();assert.deepEqual(started,[1,2,3]);
  pending.shift()({ok:true,json:async()=>({success:true})});await third;
  let t=context('cellular.htm'); await settle();
  assert.equal(t.nodes.get('cellular-fields').disabled,false);
  t.nodes.get('apn-profile').value='1'; t.nodes.get('save-profile').onclick(); await settle();
  const body=t.requests.find(x=>x.method==='POST');
  assert.equal(body.cmd,248); assert.equal(body.apn_list[0].default_flag,'0');
  assert.equal(body.apn_list[1].default_flag,'1'); assert.equal(body.apn_list[0].secret,'keep');
  assert.equal(body.apn_list[0].unknown,12);
  t=context('cellular.htm'); await settle();
  t.nodes.get('cellular-mtu').value='1000';t.nodes.get('save-cellular').onclick();await settle();
  assert.equal(t.requests.filter(x=>x.method==='POST').length,0);
  t.nodes.get('cellular-mtu').value='1400';t.nodes.get('save-cellular').onclick();await settle();
  assert.equal(t.requests.at(-1).cmd,213);assert.equal(t.requests.at(-1).apnMTU,'1400');
  t=context('cellular.htm',false);await settle();t.nodes.get('save-cellular').onclick();await settle();
  assert.equal(t.requests.filter(x=>x.method==='POST').length,0);
  t=context('cellular.htm',true,{success:false,message:'failure'});await settle();t.nodes.get('save-cellular').onclick();await settle();
  assert.match(t.nodes.get('cellular-msg').textContent,/did not confirm/);
  t=context('interfaces.htm');await settle();
  const rows=t.nodes.get('connections').children;
  assert.equal(rows[0].children[1].textContent,'br0');
  assert.equal(rows[1].children[1].textContent,'ccmni1');
  assert.equal(rows[2].children[1].textContent,'ra0, rai0');
  assert.equal(t.requests.filter(x=>x.method!=='GET').length,0);
  console.log('PASS: serialized requests and recovery after failure; live device mapping; APN field preservation; IPv6 MTU validation; cancelled and rejected writes. No live configuration requests made.');
})().catch(e=>{console.error(e);process.exit(1);});

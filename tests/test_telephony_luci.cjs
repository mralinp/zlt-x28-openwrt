// SPDX-License-Identifier: GPL-2.0-only
// The Messages view of x28-telephony against a stub of LuCI's E()/dom: grouping into conversations, paging, the phone book picker.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../package/x28-telephony/htdocs/luci-static/resources/view/x28-telephony/messages.js'), 'utf8');

const flat = c => [].concat(c == null ? [] : c).flat(Infinity).filter(x => x !== '');
const E = (tag, attrs, children) => {
 if (typeof attrs != 'object' || Array.isArray(attrs)) { children = attrs; attrs = {}; }
 return {tag, attrs, children: flat(children), style: {}, value: attrs.value || '', scrollHeight: 0, scrollTop: 0, clientHeight: 0, focus() {}, click() { attrs.click(); }};
};
const text = n => typeof n == 'string' ? n : n.children.map(text).join('');
const find = (n, test, out = []) => { if (typeof n != 'string') { if (test(n)) out.push(n); n.children.forEach(c => find(c, test, out)); } return out; };
const cls = name => n => (n.attrs.class || '').split(' ').includes(name);
let sent = [], store;
// LuCI adds String.prototype.format; the view's strings live in the vm's realm, so it is added there
const fmt = 'String.prototype.format = function() { var a = arguments, i = 0; return this.replace(/%d|%s/g, function() { return a[i++]; }); };';
const view = vm.runInNewContext(fmt + '(function(){' + script + '\n})()', {
 _: s => s, E, URLSearchParams, location: {search: ''}, requestAnimationFrame: () => {}, confirm: () => true,
 view: {extend: o => o}, poll: {add() {}}, dom: {content: (n, c) => { n.children = flat(c); }},
 ui: {createHandlerFn: (self, fn) => () => (typeof fn == 'string' ? self[fn] : fn).call(self), addNotification() {}},
 fs: {exec: (_bin, args) => { if (args[0] == 'send') { sent.push(args); store.push({ids: ['s'], dir: 'out', number: args[1], time: 9e9, status: 'sent', text: args[2]}); }
  return Promise.resolve({code: 0, stdout: JSON.stringify(args[0] == 'list' ? store : {ok: true})}); }}
});

const msg = (id, dir, number, time, t) => ({ids: [id], dir, number, time, status: dir == 'out' ? 'sent' : '', text: t});
store = [msg('a', 'in', '+989120000001', 100, 'hi'), msg('b', 'out', '09120000001', 200, 'hello'), msg('c', 'in', 'MCI Club', 300, 'ad')];
for (let i = 0; i < 12; i++) store.push(msg('n' + i, 'in', '+98913000' + (1000 + i), 10 + i, 'x' + i));
for (let i = 0; i < 40; i++) store.push(msg('l' + i, 'in', '+989350000000', 400 + i, 'long' + i));

(async () => {
 const root = view.render([store.slice(), [{number: '09120000001', name: 'Ali'}]]);
 const items = () => find(root, cls('x28-item')), bubbles = () => find(root, cls('x28-b'));
 // 15 conversations, 10 per page, newest first; both spellings of one number are one conversation, named from the phone book
 assert.equal(items().length, 10);
 assert.match(text(items()[0]), /\+989350000000.*long39/);
 assert.match(text(items()[1]), /MCI Club/);
 assert.match(text(items()[2]), /Ali.*You: hello/);
 assert.match(text(find(root, cls('x28-pager'))[0]), /Page 1 of 2/);
 // the newest conversation is open: the last 30 of its 40 messages, then all of them
 assert.equal(bubbles().length, 30);
 find(root, n => /Show older \(10 more\)/.test(text(n)) && n.tag == 'button')[0].click();
 assert.equal(bubbles().length, 40);
 // a sender that is a name cannot be answered
 items()[1].attrs.click();
 assert.equal(view.compose.style.display, 'none');
 // a thread with a number: two bubbles, and the reply goes to the number last seen
 items()[2].attrs.click();
 assert.equal(bubbles().length, 2); assert.equal(view.compose.style.display, ''); assert.equal(view.toRow.style.display, 'none');
 view.text.value = 'reply'; await view.send();
 assert.equal(String(sent.pop()), 'send,09120000001,reply'); assert.equal(view.text.value, ''); assert.equal(bubbles().length, 3);
 // a new message: recipient from the phone book
 find(root, n => n.tag == 'button' && text(n) == 'New message')[0].click();
 assert.equal(view.toRow.style.display, ''); assert.equal(bubbles().length, 0);
 assert.match(text(view.pick), /Ali \(09120000001\)/);
 view.pick.value = '09120000001'; view.pick.attrs.change(); assert.equal(view.to.value, '09120000001');
 view.to.value = '+15550001'; view.text.value = 'new'; await view.send();
 assert.equal(String(sent.pop()), 'send,+15550001,new'); assert.equal(view.sel, '15550001');
 // second page
 find(root, n => n.tag == 'button' && /Older/.test(text(n)))[0].click();
 assert.equal(items().length, 6);
 console.log('x28-telephony luci: ok');
})().catch(e => { console.error(e); process.exit(1); });

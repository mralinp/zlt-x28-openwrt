'use strict';
// The RPC allowlist enforces read-only behavior; this guard also disables unsafe stock controls.
(function() {
 const forbidden = /^(Save|Save & Apply|Apply|Reset|Restart|Stop|Start|Enable|Disable|Remove|Delete|Add|Scan|Synchronize|Install|Flash|Reboot|Kill|Terminate|Reload|Dismiss changes)/i;
 function guard() {
  document.querySelectorAll('button,input[type="submit"]').forEach(function(button) {
   const label = (button.textContent || button.value || '').trim();
   if (forbidden.test(label) && !button.disabled) button.disabled = true;
  });
 }
 document.addEventListener('submit', function(event) { event.preventDefault(); event.stopImmediatePropagation(); }, true);
 new MutationObserver(guard).observe(document.documentElement, {childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
 guard();
})();

/* Theme: System, Light or Dark. Loaded in <head> so the page never flashes. */
(function(){var k="tauten-theme",d=document.documentElement,v=null;
try{v=localStorage.getItem(k)}catch(e){}
if(v==="light"||v==="dark")d.setAttribute("data-theme",v);
document.addEventListener("DOMContentLoaded",function(){var s=document.getElementById("theme-select");if(!s)return;
s.value=v==="light"||v==="dark"?v:"system";s.parentNode.hidden=false;
s.addEventListener("change",function(){var t=s.value;
if(t==="system"){d.removeAttribute("data-theme");try{localStorage.removeItem(k)}catch(e){}}
else{d.setAttribute("data-theme",t);try{localStorage.setItem(k,t)}catch(e){}}});});})();

/* Filters for the rules index. The table is complete without this script. */
(function(){var f=document.getElementById("rule-filters");if(!f)return;f.hidden=false;
var rows=[].slice.call(document.querySelectorAll("#rules tbody tr[data-id]")),fams=[].slice.call(document.querySelectorAll("#rules tbody tr.fam")),n=document.getElementById("rule-count");
var q=f.querySelector("[name=q]"),tier=f.querySelector("[name=tier]"),by=f.querySelector("[name=by]"),nx=f.querySelector("[name=nx]");
function run(){var s=q.value.trim().toLowerCase(),shown=0;
rows.forEach(function(r){var ok=(!s||r.textContent.toLowerCase().indexOf(s)>=0)&&(!tier.value||r.getAttribute("data-"+tier.value)!=="-")&&(!by.value||r.getAttribute("data-by")===by.value)&&(!nx.checked||r.getAttribute("data-exc")==="never");r.hidden=!ok;if(ok)shown++;});
fams.forEach(function(h){var fam=h.getAttribute("data-fam");h.hidden=!rows.some(function(r){return!r.hidden&&r.getAttribute("data-fam")===fam})});
n.textContent=shown+" of "+rows.length+" rules shown";}
[q,tier,by,nx].forEach(function(e){e.addEventListener("input",run);e.addEventListener("change",run)});})();

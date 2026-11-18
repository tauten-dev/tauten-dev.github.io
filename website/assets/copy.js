/* Copy buttons, shown only when the clipboard API is available. */
(function(){if(!navigator.clipboard||!window.isSecureContext)return;
document.querySelectorAll(".copy-btn").forEach(function(b){b.hidden=false;
b.addEventListener("click",function(){var src=b.getAttribute("data-src"),t=b.getAttribute("data-copy");
var go=function(text){navigator.clipboard.writeText(text).then(function(){var o=b.textContent;b.textContent="Copied";setTimeout(function(){b.textContent=o},1400)})};
if(src){fetch(src).then(function(r){return r.text()}).then(go);return}
if(t===null){var p=b.closest(".panel"),c=p&&p.querySelector("pre");t=c?c.getAttribute("data-raw")||c.innerText:""}
go(t);});});})();

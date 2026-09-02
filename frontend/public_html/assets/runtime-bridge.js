(()=>{
'use strict';
const API='/api/mvp';
const sameOrigin=(value)=>new URL(value,location.href).origin===location.origin;
const requestToken=(prefix)=>`${prefix}_${typeof crypto.randomUUID==='function'?crypto.randomUUID():[...crypto.getRandomValues(new Uint8Array(16))].map(v=>v.toString(16).padStart(2,'0')).join('')}`;
async function request(path,options={}){
  if(location.protocol==='file:'||!sameOrigin(path))throw new Error('bridge_origin_rejected');
  const response=await fetch(`${API}${path}`,{credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json','Content-Type':'application/json',...(options.headers||{})},...options});
  let body={};try{body=await response.json()}catch{}
  if(!response.ok)throw new Error(typeof body.error==='string'?body.error:`bridge_http_${response.status}`);
  return body;
}
function publishCanonicalState(payload){
  if(!payload||typeof payload!=='object'||payload.identityDataState!=='LIVE'||typeof payload.sicId!=='string'||!payload.sicId.trim())return false;
  const current=window.__CRYPTOAID_STATE__&&typeof window.__CRYPTOAID_STATE__==='object'?window.__CRYPTOAID_STATE__:{};
  const allowed={sicId:payload.sicId.trim(),identityDataState:'LIVE',dataState:'LIVE'};
  for(const key of ['caseId','caseDataState','nextAction','timeline','paymentIntent'])if(Object.prototype.hasOwnProperty.call(payload,key))allowed[key]=payload[key];
  window.__CRYPTOAID_STATE__=Object.freeze({...current,...allowed});
  window.dispatchEvent(new CustomEvent('caid:state-updated'));
  return true;
}
async function resume(){try{publishCanonicalState(await request('/session'))}catch{/* unauthenticated is a valid fail-closed state */}}
window.addEventListener('caid:sicid-login-request',event=>{
  if(!event||!event.detail||event.detail.callerMayProvideIdentity!==false)return;
  event.preventDefault();
  request('/session',{method:'POST',body:JSON.stringify({action:'LOGIN_OR_RESUME',supportedCoreApiVersions:Array.isArray(event.detail.supportedCoreApiVersions)?event.detail.supportedCoreApiVersions:[]})}).then(publishCanonicalState).catch(()=>{});
});
window.addEventListener('caid:case-request',event=>{
  if(!event||!event.detail)return;
  event.preventDefault();
  const body={caseType:String(event.detail.caseType||'UNKNOWN').slice(0,80),projectQuery:String(event.detail.projectQuery||'').slice(0,500),description:String(event.detail.description||'').slice(0,4000),requestId:requestToken('ui_req'),idempotencyKey:requestToken('ui_idem')};
  request('/cases',{method:'POST',body:JSON.stringify(body)}).then(payload=>{if(publishCanonicalState(payload)&&payload.caseId)location.hash='recovery'}).catch(()=>{});
});
window.CryptoAIDTwin=Object.freeze({contractVersion:'1.0.0',search(query){return request(`/search?q=${encodeURIComponent(String(query||'').slice(0,500))}`)}});
window.CryptoAIDRuntimeBridge=Object.freeze({version:'1.0.0',sameOriginOnly:true,resume});
resume();
})();

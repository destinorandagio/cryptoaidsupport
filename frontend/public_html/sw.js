const SHELL_VERSION='2.1.7';
const CACHE_PREFIX='caid-shell-v';
const CACHE=`${CACHE_PREFIX}${SHELL_VERSION}`;
const SHELL=['./','./index.html','./offline.html','./manifest.webmanifest','./assets/app.css','./assets/runtime-bridge.js','./assets/app.js','./assets/shield.svg'];
const SCOPE_ORIGIN=new URL(self.registration.scope).origin;
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith(CACHE_PREFIX)&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 const req=e.request,url=new URL(req.url);
 if(req.method!=='GET')return;
 if(url.pathname.includes('/api/')||url.pathname.includes('/evidence/')||url.pathname.includes('/payment'))return;
 const shellPath=url.origin===SCOPE_ORIGIN?SHELL.find(path=>new URL(path,self.registration.scope).pathname===url.pathname):null;
 if(shellPath){e.respondWith(caches.open(CACHE).then(cache=>cache.match(new URL(shellPath,self.registration.scope).href).then(hit=>hit||fetch(req))));return;}
 if(req.mode==='navigate'){e.respondWith(fetch(req).catch(()=>caches.open(CACHE).then(cache=>cache.match('./offline.html'))));}
});

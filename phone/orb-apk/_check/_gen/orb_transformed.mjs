
import THREE from "file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/three_stub.mjs";
import { HandLandmarker, FilesetResolver } from "file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/www/vendor/js/vision_bundle.mjs";

/* ============================== SETTINGS ============================== */
const S = {
  url: localStorage.getItem("ultron.agent") || `ws://127.0.0.1:8081`,
  mic: localStorage.getItem("ultron.mic") !== "off",
};
const boot = document.getElementById("boot");
setTimeout(()=>boot.remove(), 1400);

document.getElementById("c").onclick = () => {
  document.getElementById("cfg").style.display = "flex";
  document.getElementById("cfg-url").value = S.url;
  document.getElementById("cfg-mic").value = S.mic ? "on" : "off";
};
document.getElementById("cfg-x").onclick = () =>
  document.getElementById("cfg").style.display = "none";
document.getElementById("cfg-s").onclick = () => {
  const u = document.getElementById("cfg-url").value.trim();
  const m = document.getElementById("cfg-mic").value.trim().toLowerCase();
  if (u) { S.url = u; localStorage.setItem("ultron.agent", u); }
  S.mic = m !== "off"; localStorage.setItem("ultron.mic", S.mic ? "on" : "off");
  document.getElementById("cfg").style.display = "none";
  location.reload();
};

/* ============================== ORB (offline, vendored) ============================== */
const C = { amber:0xffaa30, hot:0xffcc66, ice:0x66ccff, mid:0xdd7700 };
const scene=new THREE.Scene(), cam=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,0.1,500);
cam.position.set(0,0.4,5.5);
const ren=new THREE.WebGLRenderer({antialias:true}); ren.setSize(innerWidth,innerHeight);
ren.setPixelRatio(Math.min(devicePixelRatio,2));
ren.toneMapping=THREE.ACESFilmicToneMapping; ren.toneMappingExposure=0.9;
document.getElementById("orb").appendChild(ren.domElement);

// post-processing — all local (vendored addons, no CDN)
const {EffectComposer} = await import("file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/post/EffectComposer.js");
const {RenderPass}     = await import("file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/post/RenderPass.js");
const {UnrealBloomPass}= await import("file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/post/UnrealBloomPass.js");
const {ShaderPass}     = await import("file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/post/ShaderPass.js");
const composer=new EffectComposer(ren); composer.addPass(new RenderPass(scene,cam));
const bloom=new UnrealBloomPass(new THREE.Vector2(innerWidth,innerHeight),1.9,0.5,0.18); composer.addPass(bloom);
const chrom=new ShaderPass({uniforms:{tDiffuse:{value:null},uTime:{value:0}},
  vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
  fragmentShader:`uniform sampler2D tDiffuse;uniform float uTime;varying vec2 vUv;
   void main(){vec2 d=vUv-0.5;float o=0.0035*length(d);
   vec4 cr=texture2D(tDiffuse,vUv+d*o);vec4 cg=texture2D(tDiffuse,vUv);vec4 cb=texture2D(tDiffuse,vUv-d*o*0.5);
   gl_FragColor=vec4(cr.r,cg.g*1.05,cb.b*0.6,1.0);
   gl_FragColor.rgb=mix(gl_FragColor.rgb,gl_FragColor.rgb*vec3(1.15,0.85,0.55),0.3);}`});
composer.addPass(chrom);

const grp=new THREE.Group(); scene.add(grp);
const lineMat=(c,o=1)=>new THREE.LineBasicMaterial({color:c,transparent:true,opacity:o,blending:THREE.AdditiveBlending,depthWrite:false});
function ring(r,lat,seg=120){const p=[];for(let i=0;i<=seg;i++){const a=i/seg*Math.PI*2;p.push(new THREE.Vector3(r*Math.cos(lat)*Math.cos(a),r*Math.sin(lat),r*Math.cos(lat)*Math.sin(a)));}return new THREE.BufferGeometry().setFromPoints(p);}
function merid(r,lon,seg=120){const p=[];for(let i=0;i<=seg;i++){const lat=i/seg*Math.PI-Math.PI/2;p.push(new THREE.Vector3(r*Math.cos(lat)*Math.cos(lon),r*Math.sin(lat),r*Math.cos(lat)*Math.sin(lon)));}return new THREE.BufferGeometry().setFromPoints(p);}

const R1=2.0, shell=new THREE.Group(); grp.add(shell);
for(let i=-15;i<=15;i++){const lat=i/15*Math.PI/2*0.95; shell.add(new THREE.Line(ring(R1,lat),lineMat(i%3?C.amber*0+0x553300:C.mid,i%3?0.12:0.5)));}
for(let i=0;i<24;i++){const lon=i/24*Math.PI*2; shell.add(new THREE.Line(merid(R1,lon),lineMat(i%6?0x553300:C.mid,i%6?0.1:0.6)));}
const eq=new THREE.Group();
for(let j=0;j<22;j++){const t=j/21*2-1; eq.add(new THREE.Line(ring(R1,t*0.4/2,200),lineMat(Math.abs(t)<0.3?C.hot:C.mid,0.8*(1-Math.abs(t)*0.65))));}
shell.add(eq);
const core=new THREE.Group(); grp.add(core); const R3=0.9;
for(let s=0;s<10;s++){const p=[];const turns=3+Math.random()*2,seg=300,ph=s/10*Math.PI*2;
  for(let i=0;i<=seg;i++){const t=i/seg,lat=t*Math.PI-Math.PI/2,lon=t*turns*Math.PI*2+ph;
    p.push(new THREE.Vector3(R3*Math.cos(lat)*Math.cos(lon),R3*Math.sin(lat),R3*Math.cos(lat)*Math.sin(lon)));}
  core.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(p),lineMat(C.hot,0.3+Math.random()*0.2)));}

const cu={uTime:{value:0},uLevel:{value:0},uColorA:{value:new THREE.Color(C.hot)},uColorB:{value:new THREE.Color(C.ice)}};
const coreMesh=new THREE.Mesh(new THREE.IcosahedronGeometry(0.5,4),new THREE.ShaderMaterial({
  uniforms:cu,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,
  vertexShader:`varying vec3 vN;varying vec3 vP;void main(){vN=normalize(normalMatrix*normal);vec4 mv=modelViewMatrix*vec4(position,1.0);vP=mv.xyz;gl_Position=projectionMatrix*mv;}`,
  fragmentShader:`uniform float uTime;uniform float uLevel;uniform vec3 uColorA;uniform vec3 uColorB;varying vec3 vN;varying vec3 vP;
   void main(){float fres=pow(1.0-abs(dot(normalize(vN),normalize(-vP))),2.0);
   float pulse=0.5+0.5*sin(uTime*3.0)+uLevel*1.5;vec3 col=mix(uColorA,uColorB,fres);
   gl_FragColor=vec4(col*pulse,fres*0.9+uLevel*0.4+0.08);}`}));
grp.add(coreMesh);
const glow=new THREE.Mesh(new THREE.SphereGeometry(0.65,32,32),new THREE.MeshBasicMaterial({color:C.amber,transparent:true,opacity:0.12,blending:THREE.AdditiveBlending,depthWrite:false})); grp.add(glow);
const rtex=(()=>{const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');const g=x.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,255,255,1)');g.addColorStop(0.2,'rgba(255,220,150,0.7)');g.addColorStop(0.5,'rgba(255,160,60,0.25)');g.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=g;x.fillRect(0,0,128,128);return new THREE.CanvasTexture(c);})();
const ray=new THREE.Sprite(new THREE.SpriteMaterial({map:rtex,color:C.hot,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,opacity:0.5})); ray.scale.set(6.5,6.5,1); grp.add(ray);
const N=1500,pp=new Float32Array(N*3),cc=new Float32Array(N*3),ca=new THREE.Color(C.amber),cb=new THREE.Color(C.ice);
for(let i=0;i<N;i++){const r=1.3+Math.random()*4.6,th=Math.random()*6.28,ph=Math.acos(2*Math.random()-1);
  pp[i*3]=r*Math.sin(ph)*Math.cos(th);pp[i*3+1]=r*Math.cos(ph)*0.7;pp[i*3+2]=r*Math.sin(ph)*Math.sin(th);
  const col=ca.clone().lerp(cb,Math.random());cc[i*3]=col.r;cc[i*3+1]=col.g;cc[i*3+2]=col.b;}
const ng=new THREE.BufferGeometry();ng.setAttribute('position',new THREE.BufferAttribute(pp,3));ng.setAttribute('color',new THREE.BufferAttribute(cc,3));
const neb=new THREE.Points(ng,new THREE.PointsMaterial({size:0.055,vertexColors:true,transparent:true,opacity:0.6,blending:THREE.AdditiveBlending,depthWrite:false,map:rtex}));grp.add(neb);
const sr=new THREE.Mesh(new THREE.RingGeometry(R1-0.01,R1+0.01,120),new THREE.MeshBasicMaterial({color:C.hot,transparent:true,opacity:0,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,depthWrite:false})); sr.rotation.x=Math.PI/2; grp.add(sr);

let micLevel=0,target=0,state="idle"; const clock=new THREE.Clock();
// gesture-FX state — declared BEFORE animate() uses it (TDZ bug fix)
let fxPulse=0,fxColor=null,fxTimer=null;
function animate(){requestAnimationFrame(animate);const t=clock.getElapsedTime();
  shell.rotation.y+=0.0015;shell.rotation.x=Math.sin(t*0.08)*0.05;
  core.rotation.y-=0.005;core.rotation.z+=0.002;
  micLevel=THREE.MathUtils.lerp(micLevel,target,0.25);
  if(fxPulse>0.001){ fxPulse*=0.94; }          // decay gesture punch
  const lvl=Math.max(micLevel, fxPulse*1.3);   // gesture drives the orb too
  cu.uTime.value=t; cu.uLevel.value=lvl+(state==='think'?0.25*(0.5+0.5*Math.sin(t*6)):0);
  const breathe=1+Math.sin(t*0.8)*0.04+lvl*0.5;
  coreMesh.scale.setScalar(breathe); glow.scale.setScalar(breathe*(1+lvl*0.6));
  glow.material.opacity=0.1+lvl*0.35+(state==='speak'?0.1:0);
  ray.material.opacity=0.35+lvl*0.5+(state==='listen'?0.15:0); ray.scale.setScalar(6.5+lvl*3+Math.sin(t*0.5)*0.3);
  if(fxPulse>0.05){ /* keep gesture flash color */ }
  else ray.material.color.set(state==='think'?C.ice:C.hot);
  neb.rotation.y+=0.0006; neb.rotation.x=Math.sin(t*0.1)*0.2;
  const sy=Math.sin(t*0.4)*R1; sr.position.y=sy; const ss=Math.sqrt(Math.max(0,R1*R1-sy*sy))/R1;
  sr.scale.set(ss,ss,1); sr.material.opacity=0.2*ss;
  bloom.strength=1.7+Math.sin(t*0.8)*0.3+(state==='speak'?micLevel*1.4:0);
  chrom.uniforms.uTime.value=t; ;}
animate();

/* ============================== MIC (audio-reactive orb) ============================== */
async function startMic(){
  if(!S.mic) return;
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    const ac = new (window.AudioContext||window.webkitAudioContext)();
    const src = ac.createMediaStreamSource(stream);
    const an = ac.createAnalyser(); an.fftSize = 512;
    src.connect(an);
    const buf = new Uint8Array(an.frequencyBinCount);
    (function tick(){ an.getByteFrequencyData(buf);
      let sum=0; for(let i=0;i<buf.length;i++) sum+=buf[i];
      target = Math.min(1.6, (sum/buf.length)/90); requestAnimationFrame(tick); })();
  }catch(e){ /* mic denied — orb still runs, just not reactive */ }
}
startMic();

/* ============================== GESTURES (all 6, offline) ============================== */
const video=document.getElementById("cam"),ovl=document.getElementById("ovl"),octx=ovl.getContext("2d");
const gstEl=document.getElementById("gst");
let lm=null,gOn=false;
async function startG(){
  const fs = await FilesetResolver.forVisionTasks("./vendor/wasm");   // LOCAL wasm
  lm = await HandLandmarker.createFromOptions(fs,{
    baseOptions:{modelAssetPath:"./vendor/models/hand_landmarker.task",delegate:"GPU"},
    runningMode:"VIDEO",numHands:2});
  const s=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});
  video.srcObject=s; await video.play(); video.style.display="block"; ovl.style.display="block";
  gOn=true; loop();
}
let last=0;
function loop(){ if(!gOn) return; requestAnimationFrame(loop);
  if(!lm||video.readyState<2||video.currentTime===last) return; last=video.currentTime;
  const r=lm.detectForVideo(video,performance.now()); classify(r.landmarks);
}
const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
/* gesture state machine */
let gPrev=null,gHold=null,gHoldT=0;
/* local visual feedback: every fired gesture punches the orb */
const fxEl=document.getElementById("fx");
const FX={ "pinch":{txt:"▲ TALK",color:0xffcc66}, "zoom":{txt:"⤢ ZOOM",color:0xffaa30},
  "palm":{txt:"◉ LISTEN",color:0x66ccff}, "peace":{txt:"❒ SHOT",color:0xff8888},
  "thumbs-up":{txt:"+ VOL",color:0x66ff99}, "swipe-left":{txt:"‹ PREV",color:0xffaa30},
  "swipe-right":{txt:"› NEXT",color:0xffaa30}, "point":{txt:"➤",color:0xffcc66} };
function gestureFx(g){
  const f=FX[g]; if(!f) return;
  fxPulse=1.0; fxColor=f.color;
  ray.material.color.set(f.color);
  fxEl.textContent=f.txt; fxEl.style.opacity=1;
  clearTimeout(fxTimer); fxTimer=setTimeout(()=>fxEl.style.opacity=0,650);
}
function classify(ls){
  octx.clearRect(0,0,ovl.width,ovl.height);
  const hands=ls||[];
  // draw skeleton per hand
  hands.forEach(L=>{
    octx.strokeStyle="#ffcc66"; octx.lineWidth=1.5;
    const P=i=>[(1-L[i].x)*ovl.width,L[i].y*ovl.height];
    const bones=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],
                  [9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
    bones.forEach(([a,b])=>{const A=P(a),B=P(b);octx.beginPath();octx.moveTo(...A);octx.lineTo(...B);octx.stroke();});
  });
  // --- compute per-hand features ---
  const feats=hands.map(L=>{
    const pinch = dist(L[4],L[8]) / Math.max(1e-6, dist(L[0],L[9]));      // thumb-index
    const tip=(i)=>dist(L[i],L[0]) / Math.max(1e-6, dist(L[5],L[0]));    // tip reach vs palm
    const up = [8,12,16,20].filter(i=>tip(i) > 1.35).length;             // extended fingers
    const thumbUp = tip(4) > 1.25 && Math.abs(L[4].y-L[3].y) < Math.abs(L[8].y-L[6].y)*0.7;
    return {pinch, up, thumbUp, L};
  });
  const pinches = feats.filter(f=>f.pinch<0.35).length;
  let g = null;
  if (pinches >= 2)            g = "zoom";
  else if (pinches === 1)      g = "pinch";
  else if (hands.length === 1){
    const f = feats[0];
    if (f.up === 0 && f.thumbUp)  g = "thumbs-up";
    if (f.up === 0 && !f.thumbUp && f.pinch > 0.5) g = "fist";
    if (f.up >= 4)               g = "palm";
    if (f.up === 2 && f.pinch > 0.5 && f.L[8].y < f.L[6].y && f.L[12].y < f.L[10].y) g = "peace";
    if (f.thumbUp && f.up === 0) g = "thumbs-up";
    if (f.up === 1 && f.L[8].y < f.L[6].y) g = "point";
  }
  // swipe: track palm x over time
  if (g === "palm" && hands.length === 1){
    const cx = feats[0].L[9].x;
    if (gPrev && gPrev.g === "palm"){
      const dx = cx - gPrev.x;
      if (Math.abs(dx) > 0.11){ g = dx < 0 ? "swipe-left" : "swipe-right"; }
    }
    gHold = {g:"palm", x:cx, t:performance.now()};
    if (!gPrev || performance.now()-gPrev.t > 400) gPrev = gHold;
  } else { gPrev = null; }

  const names={zoom:"2-HAND ZOOM",pinch:"PINCH",palm:"OPEN PALM",peace:"PEACE ✌",
    "thumbs-up":"THUMBS UP","swipe-left":"SWIPE ‹","swipe-right":"SWIPE ›",point:"POINT",fist:"—"};
  gstEl.textContent = "GESTURE: " + (g && names[g] ? names[g] : "—");

  // fire only on TRANSITIONS (rising edge)
  if (g && g !== window._lastG){
    fire(g);        // -> agent over WS
    gestureFx(g);   // -> local orb burst (works even with no link)
  }
  window._lastG = g;
}
function fire(g){
  const map={ "pinch":{type:"talk"}, "zoom":{type:"gesture",action:"zoom"},
    "palm":{type:"gesture",action:"listen"}, "peace":{type:"gesture",action:"screenshot"},
    "thumbs-up":{type:"gesture",action:"volup"}, "swipe-left":{type:"gesture",action:"prev"},
    "swipe-right":{type:"gesture",action:"next"} };
  const m = map[g]; if(m) send(m);
}

/* ============================== LINK (agent WS, robust) ============================== */
let ws=null, backoff=1000;
const lnk=document.getElementById("lnk");
function setLink(ok,txt){ lnk.textContent = "LINK: "+txt; lnk.className = "hud link "+(ok?"ok":"bad"); }
function connect(){
  setLink(false,"connecting…");
  try{ ws = new WebSocket(S.url); }catch(e){ setLink(false,"bad url"); setTimeout(connect,3000); return; }
  ws.onopen  = ()=>{ setLink(true,S.url.replace("ws://","")); backoff=1000; };
  ws.onclose = ()=>{ setLink(false,"reconnecting…"); setTimeout(connect, backoff); backoff=Math.min(backoff*1.6, 8000); };
  ws.onerror = ()=>{ try{ws.close();}catch(e){} };
  ws.onmessage = e=>{
    try{ const m=JSON.parse(e.data);
      if(m.type==="audio") target=m.level;
      if(m.type==="state"){ state=m.state; document.getElementById("st").textContent=m.state.toUpperCase();
        const d=document.getElementById("dot"); d.className="dot"+(m.state==="idle"?"":" "+m.state); }
      if(m.type==="transcript"){ const t=document.getElementById("tr");
        const div=document.createElement("div");
        div.textContent=(m.who==="user"?"YOU: ":"ULTRON: ")+m.text;
        t.appendChild(div); t.scrollTop=t.scrollHeight;
        while(t.childNodes.length>40) t.removeChild(t.firstChild); }
    }catch(err){}
  };
}
connect();
function send(m){ if(ws && ws.readyState===1) ws.send(JSON.stringify(m)); }

/* buttons */
document.getElementById("t").onclick=()=>{ send({type:"talk"}); state="listen"; };
document.getElementById("g").onclick=async function(){
  if(gOn){ gOn=false; this.classList.remove("on"); video.style.display="none"; ovl.style.display="none"; }
  else{ this.classList.add("on"); try{ await startG(); }
    catch(e){ gstEl.textContent="CAMERA DENIED"; this.classList.remove("on"); } }
};

/* keep screen on while the orb is visible */
try{ if(navigator.wakeLock){ navigator.wakeLock.request("screen").catch(()=>{}); } }catch(e){}

addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();
  ren.setSize(innerWidth,innerHeight);composer.setSize(innerWidth,innerHeight);});

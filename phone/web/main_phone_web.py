"""Phone web HUD: small but beautiful FastAPI app serving a lightweight orb +
MediaPipe gestures (Brahma-style classifier) + transcript. Runs in phone browser.

Gesture map (mirrors Brahma-Echo Air Actions, adapted):
- Pinch (thumb+index) hold  -> talk / wake
- Open Palm                 -> play/pause (toggle listen)
- Peace (✌️)               -> screenshot / snapshot
- Thumbs Up / Down         -> volume up / down
- Swipe Left / Right       -> prev / next
"""
from __future__ import annotations
import os
import json
import math
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()
HERE = os.path.dirname(__file__)
CLIENTS: set[WebSocket] = set()


# ---- Brahma-style gesture classifier (adapted, offline, pure-python) ----
class GestureTracker:
    def __init__(self):
        self.prev_pinch = False
        self.last_swipe = 0.0
        self.last_action = {}
        self.pos_history = []

    def classify(self, lm) -> dict:
        """lm: 21 landmarks [x,y,z] normalized. Returns gesture state."""
        now = time.monotonic()
        if not lm or len(lm) < 21:
            self.pos_history.clear()
            return {"hand": False, "pinch": False, "action": None, "name": "None"}

        wrist = lm[0]; thumb_tip = lm[4]; index_tip = lm[8]
        index_pip = lm[6]; middle_tip = lm[12]; middle_pip = lm[10]
        ring_tip = lm[16]; ring_pip = lm[14]; pinky_tip = lm[20]; pinky_pip = lm[18]
        middle_mcp = lm[9]

        index_open = index_tip[1] < index_pip[1]
        middle_open = middle_tip[1] < middle_pip[1]
        ring_open = ring_tip[1] < ring_pip[1]
        pinky_open = pinky_tip[1] < pinky_pip[1]
        palm_scale = max(0.01, math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1]))
        pinch = math.hypot(thumb_tip[0] - index_tip[0], thumb_tip[1] - index_tip[1]) < palm_scale * 0.35

        action = None; name = "Pointer"
        # swipe
        self.pos_history.append((middle_mcp[0], now))
        self.pos_history = [p for p in self.pos_history if now - p[1] <= 0.35]
        if len(self.pos_history) >= 4 and now - self.last_swipe > 0.75:
            dx = self.pos_history[-1][0] - self.pos_history[0][0]
            if abs(dx) > 0.18:
                action = "next" if dx > 0 else "prev"
                self.last_swipe = now
                name = "Swipe " + ("Right" if dx > 0 else "Left")
        elif pinch and not self.prev_pinch:
            action = "talk"; name = "Pinch"
        elif index_open and middle_open and not ring_open and not pinky_open:
            if now - self.last_action.get("peace", 0) > 2:
                action = "screenshot"; self.last_action["peace"] = now; name = "Peace"
        elif not (index_open or middle_open or ring_open or pinky_open):
            if now - self.last_action.get("vol", 0) > 0.14:
                action = "vol_up"; self.last_action["vol"] = now; name = "ThumbsUp"
        elif index_open and middle_open and ring_open and pinky_open:
            if now - self.last_action.get("play", 0) > 1.4:
                action = "listen"; self.last_action["play"] = now; name = "OpenPalm"
        self.prev_pinch = pinch
        return {"hand": True, "pinch": pinch, "action": action, "name": name}


INDEX = """
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ULTRON mini</title><style>
body{margin:0;background:#000;overflow:hidden;font-family:monospace;color:#ffaa30}
#orb{position:fixed;inset:0}
.hud{position:fixed;z-index:5;text-shadow:0 0 8px #ffaa30}
.title{top:12px;left:12px;letter-spacing:.3em;font-size:12px}
.status{top:12px;right:12px;font-size:10px}
.gest{top:40px;right:12px;font-size:10px;color:#ffcc66}
.tr{bottom:70px;left:12px;font-size:10px;max-width:92vw}
.hint{bottom:12px;left:12px;font-size:9px;opacity:.6}
.btn{bottom:12px;right:12px}
button{background:rgba(20,10,0,.6);border:1px solid #ffaa30;color:#ffaa30;
font-family:monospace;padding:8px 12px;border-radius:4px;margin-left:4px}
canvas{display:block}
.cmdbar{bottom:12px;left:50%;transform:translateX(-50%);display:flex;gap:6px;
z-index:7;pointer-events:auto}
.cmdbar input{background:rgba(20,10,0,.7);border:1px solid #ffaa30;color:#ffaa30;
font-family:monospace;padding:8px 10px;border-radius:4px;width:46vw;outline:none}
</style></head>
<body>
<div id="orb"></div>
<div class="hud title">U.L.T.R.O.N. mini</div>
<div class="hud status" id="st">IDLE</div>
<div class="hud gest" id="gst">GESTURE: —</div>
<div class="hud tr" id="tr"></div>
<div class="hud hint">PINCH talk · OPEN-PALM listen · PEACE shot · THUMBS vol · SWIPE nav</div>
<div class="hud btn"><button id="g">GESTURES</button><button id="t">TALK</button></div>
<div class="hud cmdbar"><input id="cmd" type="text" placeholder="type a goal…" autocomplete="off"><button id="send">SEND</button></div>
<script type="module">
import * as THREE from "https://esm.sh/three@0.160";
import {HandLandmarker,FilesetResolver} from "https://esm.sh/@mediapipe/tasks-vision@0.10.35";
const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,.1,500);
const ren=new THREE.WebGLRenderer({antialias:true});ren.setSize(innerWidth,innerHeight);
document.getElementById('orb').appendChild(ren.domElement);
const grp=new THREE.Group();scene.add(grp);
const C={amber:0xffaa30,hot:0xffcc66,ice:0x66ccff,mid:0xdd7700,grn:0x66ff99};
function colForState(s){return new THREE.Color(s==='listen'?C.hot:s==='think'?C.ice:s==='speak'?C.grn:C.amber);}
// PREMIUM fresnel energy core
const cu={uTime:{value:0},uLevel:{value:0},uColorA:{value:new THREE.Color(C.hot)},uColorB:{value:new THREE.Color(C.ice)}};
const core=new THREE.Mesh(new THREE.IcosahedronGeometry(.5,4),new THREE.ShaderMaterial({
  uniforms:cu,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,
  vertexShader:`varying vec3 vN;varying vec3 vP;varying vec2 vUv;void main(){vUv=uv;vN=normalize(normalMatrix*normal);vec4 mv=modelViewMatrix*vec4(position,1.0);vP=mv.xyz;gl_Position=projectionMatrix*mv;}`,
  fragmentShader:`uniform float uTime;uniform float uLevel;uniform vec3 uColorA;uniform vec3 uColorB;varying vec3 vN;varying vec3 vP;varying vec2 vUv;
   float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
   float noise(vec2 p){vec2 i=floor(p),f=fract(p);float a=hash(i),b=hash(i+vec2(1,0)),c=hash(i+vec2(0,1)),d=hash(i+vec2(1,1));vec2 u=f*f*(3.0-2.0*f);return mix(mix(a,b,u.x),mix(c,d,u.x),u.y);}
   void main(){float fres=pow(1.0-abs(dot(normalize(vN),normalize(-vP))),2.0);
   float ripple=sin(vUv.y*20.0+uTime*10.0)*uLevel*0.3;
   float pulse=0.5+0.5*sin(uTime*3.0)+uLevel*1.5+ripple;
   float caust=noise(vUv*6.0+uTime*0.3)*0.25;
   vec3 col=mix(uColorA,uColorB,fres)+caust;
   gl_FragColor=vec4(col*pulse,fres*0.9+uLevel*0.45+0.08+caust*0.3);}`}));grp.add(core);
// inner glow
const glow=new THREE.Mesh(new THREE.SphereGeometry(.62,32,32),new THREE.MeshBasicMaterial({color:C.amber,transparent:true,opacity:.12,blending:THREE.AdditiveBlending,depthWrite:false}));grp.add(glow);
// god-ray sprite
const rtex=(()=>{const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');const g=x.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,255,255,1)');g.addColorStop(.2,'rgba(255,220,150,.7)');g.addColorStop(.5,'rgba(255,160,60,.25)');g.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=g;x.fillRect(0,0,128,128);return new THREE.CanvasTexture(c);})();
const ray=new THREE.Sprite(new THREE.SpriteMaterial({map:rtex,color:C.hot,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,opacity:.5}));ray.scale.set(6.5,6.5,1);grp.add(ray);
// nebula
const N=1200,pp=new Float32Array(N*3),cc=new Float32Array(N*3),ca=new THREE.Color(C.amber),cb=new THREE.Color(C.ice);
for(let i=0;i<N;i++){const r=.5+Math.random()*3,t=Math.random()*6.28,ph=Math.acos(2*Math.random()-1);
  pp[i*3]=r*Math.sin(ph)*Math.cos(t);pp[i*3+1]=r*Math.cos(ph);pp[i*3+2]=r*Math.sin(ph)*Math.sin(t);
  const col=ca.clone().lerp(cb,Math.random());cc[i*3]=col.r;cc[i*3+1]=col.g;cc[i*3+2]=col.b;}
const ng=new THREE.BufferGeometry();ng.setAttribute('position',new THREE.BufferAttribute(pp,3));ng.setAttribute('color',new THREE.BufferAttribute(cc,3));
const neb=new THREE.Points(ng,new THREE.PointsMaterial({size:.05,vertexColors:true,transparent:true,opacity:.6,blending:THREE.AdditiveBlending,depthWrite:false,map:rtex}));grp.add(neb);
// post-processing bloom + chromatic
const {EffectComposer}=await import("https://esm.sh/three@0.160/examples/jsm/postprocessing/EffectComposer.js");
const {RenderPass}=await import("https://esm.sh/three@0.160/examples/jsm/postprocessing/RenderPass.js");
const {UnrealBloomPass}=await import("https://esm.sh/three@0.160/examples/jsm/postprocessing/UnrealBloomPass.js");
const {ShaderPass}=await import("https://esm.sh/three@0.160/examples/jsm/postprocessing/ShaderPass.js");
const composer=new EffectComposer(ren);composer.addPass(new RenderPass(scene,cam));
const bloom=new UnrealBloomPass(new THREE.Vector2(innerWidth,innerHeight),1.7,0.5,0.2);composer.addPass(bloom);
const chrom=new ShaderPass({uniforms:{tDiffuse:{value:null}},vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
  fragmentShader:`uniform sampler2D tDiffuse;varying vec2 vUv;void main(){vec2 d=vUv-0.5;float o=0.0035*length(d);vec4 cr=texture2D(tDiffuse,vUv+d*o);vec4 cg=texture2D(tDiffuse,vUv);vec4 cb=texture2D(tDiffuse,vUv-d*o*0.5);gl_FragColor=vec4(cr.r,cg.g*1.05,cb.b*0.6,1.0);}`});composer.addPass(chrom);
cam.position.z=3.6;let lvl=0,tgt=0,state='idle',rot=0;
function animate(){requestAnimationFrame(animate);rot+=.004;grp.rotation.y=rot;grp.rotation.x=Math.sin(rot/3)*.1;
  lvl=THREE.MathUtils.lerp(lvl,tgt,0.25);cu.uTime.value=performance.now()/1000;cu.uLevel.value=lvl;
  core.scale.setScalar(1+lvl*0.7+Math.sin(performance.now()/1000*0.8)*0.04);
  glow.scale.setScalar(1+lvl*0.6);glow.material.opacity=0.1+lvl*0.5+(state==='speak'?0.1:0);
  ray.material.opacity=0.35+lvl*0.6+(state==='listen'?0.15:0);
  const sc=colForState(state);cu.uColorA.value.lerp(sc,0.06);neb.material.color.lerp(sc,0.06);
  bloom.strength=1.6+Math.sin(performance.now()/1000*0.8)*0.3+lvl*1.2;
  composer.render(scene,cam);}animate();
// hand tracking
let ws;try{ws=new WebSocket(`ws://${location.hostname}:8081`);}catch(e){}
ws&&ws.addEventListener('message',e=>{const m=JSON.parse(e.data);
  if(m.type==='audio')lvl=m.level;if(m.type==='state'){state=m.state;document.getElementById('st').textContent=m.state.toUpperCase();}
  if(m.type==='gesture')document.getElementById('gst').textContent='GESTURE: '+m.name;
  if(m.type==='transcript'){const t=document.getElementById('tr');
    t.innerHTML+=`<div>${m.who==='user'?'YOU':'ULTRON'}: ${m.text}</div>`;}});
document.getElementById('t').onclick=()=>ws&&ws.send(JSON.stringify({type:'talk'}));
document.getElementById('g').onclick=()=>ws&&ws.send(JSON.stringify({type:'gestures'}));
// typed goal input (pointer-events:auto) -> send {type:'goal',goal:text}
document.getElementById('send').onclick=()=>{const i=document.getElementById('cmd');const v=i.value.trim();if(v){ws&&ws.send(JSON.stringify({type:'goal',goal:v}));i.value='';}};
document.getElementById('cmd').addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('send').click();});
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();ren.setSize(innerWidth,innerHeight);});
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX


@app.post("/talk")
async def talk():
    """Floating widget / button asks the agent to start listening (Vosk STT).
    Relay a `talk` message to the agent WebSocket on :8081."""
    try:
        import websockets
        import asyncio
        async with websockets.connect("ws://127.0.0.1:8081") as ws:
            await ws.send(json.dumps({"type": "talk"}))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await ws.accept(); CLIENTS.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        CLIENTS.discard(ws)

@app.websocket("/gesture")
async def gesture_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            # phone-side would run MediaPipe and forward 21 landmarks; here we echo
            data = json.loads(raw)
            await ws.send_json({"echo": data})
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

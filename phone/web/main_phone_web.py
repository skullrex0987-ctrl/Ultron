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
</style></head>
<body>
<div id="orb"></div>
<div class="hud title">U.L.T.R.O.N. mini</div>
<div class="hud status" id="st">IDLE</div>
<div class="hud gest" id="gst">GESTURE: —</div>
<div class="hud tr" id="tr"></div>
<div class="hud hint">PINCH talk · OPEN-PALM listen · PEACE shot · THUMBS vol · SWIPE nav</div>
<div class="hud btn"><button id="g">GESTURES</button><button id="t">TALK</button></div>
<script type="module">
import * as THREE from "https://esm.sh/three@0.160";
import {HandLandmarker,FilesetResolver} from "https://esm.sh/@mediapipe/tasks-vision@0.10.35";
const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,.1,500);
const ren=new THREE.WebGLRenderer({antialias:true});ren.setSize(innerWidth,innerHeight);
document.getElementById('orb').appendChild(ren.domElement);
const grp=new THREE.Group();scene.add(grp);
const core=new THREE.Mesh(new THREE.IcosahedronGeometry(.35,1),
  new THREE.MeshBasicMaterial({color:0xffcc66,wireframe:true}));grp.add(core);
for(let i=0;i<8;i++){const r=new THREE.Mesh(new THREE.TorusGeometry(.8+i*.12,0.012,8,90),
  new THREE.MeshBasicMaterial({color:0xffaa30,transparent:true,opacity:.4-i*.04}));
  r.rotation.x=Math.random()*3;grp.add(r);}
// particles
const N=600,p=new Float32Array(N*3);
for(let i=0;i<N;i++){const rr=.5+Math.random()*3,t=Math.random()*6.28,ph=Math.acos(2*Math.random()-1);
  p[i*3]=rr*Math.sin(ph)*Math.cos(t);p[i*3+1]=rr*Math.cos(ph);p[i*3+2]=rr*Math.sin(ph)*Math.sin(t);}
const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(p,3));
grp.add(new THREE.Points(pg,new THREE.PointsMaterial({color:0xffaa30,size:0.02,transparent:true,opacity:.6})));
cam.position.z=3.6;let lvl=0,rot=0;
function animate(){requestAnimationFrame(animate);rot+=.004;grp.rotation.y=rot;grp.rotation.x=Math.sin(rot/3)*.1;
  core.scale.setScalar(1+lvl*0.7);ren.render(scene,cam);}animate();
// hand tracking
let ws;try{ws=new WebSocket(`ws://${location.hostname}:8081`);}catch(e){}
ws&&ws.addEventListener('message',e=>{const m=JSON.parse(e.data);
  if(m.type==='audio')lvl=m.level;if(m.type==='state')document.getElementById('st').textContent=m.state.toUpperCase();
  if(m.type==='gesture')document.getElementById('gst').textContent='GESTURE: '+m.name;
  if(m.type==='transcript'){const t=document.getElementById('tr');
    t.innerHTML+=`<div>${m.who==='user'?'YOU':'ULTRON'}: ${m.text}</div>`;}});
document.getElementById('t').onclick=()=>ws&&ws.send(JSON.stringify({type:'talk'}));
document.getElementById('g').onclick=()=>ws&&ws.send(JSON.stringify({type:'gestures'}));
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();ren.setSize(innerWidth,innerHeight);});
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX

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

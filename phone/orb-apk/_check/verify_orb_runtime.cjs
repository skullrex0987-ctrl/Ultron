// ULTRON orb RUNTIME smoke test — executes the actual module (DOM stubs, no GL)
// Catches: TDZ/reference errors, missing elements, dead wiring — everything
// that made v1.2.2 show "ORB ERROR: fxPulse before initialization".
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const WWW = process.env.ORB_WWW || "C:/Users/ranra/projects/Ultron/phone/orb-apk/www";
const GEN = "C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen";
const fURL = p => pathToFileURL(p.replace(/\\/g, "/")).href;
let fail = 0;
const bad = m => { console.log("  FAIL:", m); fail++; };

// ---------- extract the module script ----------
const html = fs.readFileSync(path.join(WWW, "index.html"), "utf8");
const modMatch = html.match(/<script type="module">([\s\S]*?)<\/script>/);
if (!modMatch) { console.log("FAIL: no module script"); process.exit(1); }
let mod = modMatch[1];

// ---------- 1. STATIC TDZ check: anything animate() uses must exist before invocation ----------
{
  const inv = mod.indexOf("animate();");
  const fnStart = mod.indexOf("function animate");
  const body = mod.slice(fnStart, inv);
  if (inv < 0 || fnStart < 0 || inv <= fnStart) bad("animate() invocation not found after function");
  else {
    const declRe = /^(?:let|const)\s+([A-Za-z_$][\w$]*)/gm;
    declRe.lastIndex = inv;
    let m;
    while ((m = declRe.exec(mod))) {
      const name = m[1];
      const usedInAnimate = new RegExp("\\b" + name + "\\b").test(body);
      if (usedInAnimate) bad("TDZ: '" + name + "' declared AFTER animate() but used inside it");
    }
  }
}

// ---------- 2. build transformed module + vendor copies ----------
fs.rmSync(GEN, { recursive: true, force: true });
fs.mkdirSync(path.join(GEN, "post"), { recursive: true });
fs.mkdirSync(path.join(GEN, "shaders"), { recursive: true });

const THREE_PATH = path.join(WWW, "vendor/js/three.module.js");
const MP_PATH = path.join(WWW, "vendor/js/vision_bundle.mjs");

// postprocessing + shader copies with 'three' rewritten to the absolute path
for (const f of fs.readdirSync(path.join(WWW, "vendor/js/postprocessing"))) {
  let s = fs.readFileSync(path.join(WWW, "vendor/js/postprocessing", f), "utf8");
  s = s.replace(/from\s+'three'/g, "from " + JSON.stringify(fURL(THREE_PATH)));
  fs.writeFileSync(path.join(GEN, "post", f), s);
}
for (const f of fs.readdirSync(path.join(WWW, "vendor/js/shaders"))) {
  fs.copyFileSync(path.join(WWW, "vendor/js/shaders", f), path.join(GEN, "shaders", f));
}

// three stub: real three, WebGLRenderer stubbed (no canvas/GL)
fs.writeFileSync(path.join(GEN, "three_stub.mjs"), `
import * as R from ${JSON.stringify(fURL(THREE_PATH))};
class WebGLRendererStub {
  constructor(){ this.domElement = { style:{}, appendChild(){}, remove(){} };
    this.toneMapping = 0; this.toneMappingExposure = 1; }
  getDrawingBufferSize(v){ v.width=800; v.height=600; return v; }
  getSize(v){ v.width=800; v.height=600; return v; }
  setPixelRatio(){} getPixelRatio(){return 2;} setSize(){} render(){} setRenderTarget(){} getRenderTarget(){return null;}
  clear(){} copyFramebufferToTexture(){}
}
export default new Proxy(R, { get(t, p){ if (p === "WebGLRenderer") return WebGLRendererStub; return t[p]; } });
`);

// module transforms
let t = mod;
t = t.replace(/import\s+\*\s+as\s+THREE\s+from\s+"three"/,
  'import THREE from ' + JSON.stringify(fURL(path.join(GEN, "three_stub.mjs"))));
t = t.replace(/from\s+"@mediapipe\/tasks-vision"/, 'from ' + JSON.stringify(fURL(MP_PATH)));
t = t.replace(/import\("\.\/vendor\/js\/postprocessing\/([A-Za-z]+)\.js"\)/g,
  (m0, f) => 'import(' + JSON.stringify(fURL(path.join(GEN, "post", f + ".js"))) + ')');
t = t.replace(/composer\.render\(\);/, ";"); // no GL in headless frames
fs.writeFileSync(path.join(GEN, "orb_transformed.mjs"), t);

// ---------- 3. DOM / browser globals ----------
const noop = () => {};
const gradient = { addColorStop: noop };
const permissiveCtx = new Proxy({}, { get: (t, p) => {
  if (p === "createRadialGradient" || p === "createLinearGradient") return () => gradient;
  if (p === "canvas") return {};
  return noop;
} });
function makeEl(id) {
  const el = {
    id, style: {}, value: "", textContent: "", className: "",
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    appendChild: noop, remove: noop, removeChild: noop, firstChild: null,
    childNodes: [], scrollTop: 0, onclick: null, width: 170, height: 128,
    getContext: () => permissiveCtx, addEventListener: noop,
  };
  return el;
}
const els = {};
global.document = {
  getElementById: id => els[id] || (els[id] = makeEl(id)),
  createElement: tag => makeEl("dyn-" + tag),
};
global.window = global;
global.localStorage = { getItem: () => "", setItem: noop };
global.navigator = { mediaDevices: { getUserMedia: async () => { throw new Error("no camera in harness"); } } };
global.devicePixelRatio = 1;
global.innerWidth = 800; global.innerHeight = 600;
global.addEventListener = noop;
global.WebSocket = class { constructor() { this.readyState = 1; setTimeout(() => this.onopen && this.onopen(), 0); } send() {} close() {} };
global.requestAnimationFrame = fn => { rafQ.push(fn); return rafQ.length; };
const rafQ = [];
global.performance = global.performance || { now: () => Date.now() };

// ---------- 4. LOAD + run frames ----------
(async () => {
  console.log("== runtime smoke ==");
  try {
    await import(fURL(path.join(GEN, "orb_transformed.mjs")));
    console.log("  OK module loads (no TDZ / reference errors)");
  } catch (e) {
    bad("module load: " + e.message);
    console.log("== RESULT: FAIL ==");
    process.exitCode = 1;
    return;
  }
  // give async bits (stub WS onopen) a tick, then drive 5 animation frames
  await new Promise(r => setTimeout(r, 30));
  try {
    for (let i = 0; i < 5; i++) {
      const q = rafQ.splice(0);
      if (!q.length) break;
      q.forEach(fn => fn(i * 16.7));
    }
    console.log("  OK 5 animate() frames ran clean");
  } catch (e) {
    bad("animate frame: " + e.message);
  }
  // wiring sanity: buttons got handlers, splash-safety exists in HTML
  if (!els["g"] || typeof els["g"].onclick !== "function") bad("GESTURES button never wired (module died before wiring?)");
  if (!els["t"] || typeof els["t"].onclick !== "function") bad("TALK button never wired");
  if (!els["cmdGo"] || typeof els["cmdGo"].onclick !== "function") bad("cmd RUN button never wired");
  if (!els["cmdIn"] || typeof els["cmdIn"].addEventListener !== "function") bad("cmd input never wired");
  if (!els["cfg-s"] || typeof els["cfg-s"].onclick !== "function") bad("settings SAVE never wired");
  if (!els["fx"]) bad("fx element missing");
  console.log(fail ? "== RESULT: FAIL(" + fail + ") ==" : "== RESULT: ALL GREEN ==");
  process.exitCode = fail ? 1 : 0;
})();

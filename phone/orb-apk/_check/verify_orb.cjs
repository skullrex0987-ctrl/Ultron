// ULTRON orb index.html — offline import-chain + runtime smoke test (no browser)
// Verifies: (1) every static import in index.html resolves on disk,
//           (2) the full ES module graph loads in Node (real three + mediapipe),
//           (3) the boot splash clears (setTimeout defined + module doesn't die).
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = "C:/Users/ranra/projects/Ultron/phone/orb-apk/www";
let fail = 0;

// ---- 1. static import resolution ----
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const importRe = /(?:import\s+[^;]+?from\s+|import\s*\(\s*|await\s+import\s*\(\s*)["'](\.[^"']+)["']/g;
const refs = new Set();
let m;
while ((m = importRe.exec(html))) refs.add(m[1]);

// importmap: "three" & "@mediapipe/tasks-vision" -> ./vendor/js/...
const imap = JSON.parse(html.match(/<script type="importmap">([\s\S]*?)<\/script>/)[1]);
console.log("== 1. import resolution ==");
for (const r of refs) {
  const target = path.join(ROOT, r);
  const exists = fs.existsSync(target);
  console.log((exists ? "  OK " : "  MISSING ") + r);
  if (!exists) fail++;
}
for (const bare of Object.keys(imap.imports || {})) {
  const p = imap.imports[bare];
  const ok = fs.existsSync(path.join(ROOT, p));
  console.log((ok ? "  OK importmap " : "  MISSING importmap ") + bare + " -> " + p);
  if (!ok) fail++;
}

// ---- 2. module-graph load (real libs, Node ESM via dynamic import) ----
// Node can import the ACTUAL three.module.js + vision_bundle.mjs; wasm files
// are only fetched by MediaPipe at runtime, so graph-load proves the JS chain.
console.log("== 2. module graph load ==");
(async () => {
  try {
    const three = await import("file://" + path.join(ROOT, "vendor/js/three.module.js").replace(/\\/g, "/"));
    const keys = Object.keys(three).length;
    console.log("  three.module.js exports:", keys, keys > 100 ? "OK" : "SUSPECT");
    if (keys < 100) fail++;
    const mp = await import("file://" + path.join(ROOT, "vendor/js/vision_bundle.mjs").replace(/\\/g, "/"));
    const mpk = Object.keys(mp).length;
    console.log("  vision_bundle.mjs exports:", mpk, mpk > 5 ? "OK" : "SUSPECT");
    if (mpk < 5) fail++;
    for (const pp of ["vendor/js/postprocessing/EffectComposer.js",
                      "vendor/js/postprocessing/RenderPass.js",
                      "vendor/js/postprocessing/UnrealBloomPass.js",
                      "vendor/js/postprocessing/ShaderPass.js"]) {
      const mod = await import("file://" + path.join(ROOT, pp).replace(/\\/g, "/"));
      console.log("  OK " + pp, "exports:", Object.keys(mod).length);
    }
  } catch (e) {
    console.log("  MODULE LOAD FAILED:", e.message);
    fail++;
  }

  // ---- 3. splash-clear logic ----
  console.log("== 3. boot splash logic ==");
  if (/id="boot"/.test(html) && /boot\.remove\(\)/.test(html)) {
    console.log("  splash element + remove() present");
  } else {
    console.log("  MISSING splash removal!"); fail++;
  }
  // the remove must NOT depend solely on the module script succeeding:
  const inlineRemove = /setTimeout\(\(\)=>boot\.remove\(\),\s*\d+\)/.test(html);
  const fallbackExists = /<script>(?![^<]*type=["']module)/.test(html);
  console.log("  module-timer remove:", inlineRemove, "| non-module fallback present:", fallbackExists);
  if (!inlineRemove) fail++;

  console.log("== RESULT: " + (fail ? "FAIL(" + fail + ")" : "ALL GREEN") + " ==");
  process.exitCode = fail ? 1 : 0;
})();

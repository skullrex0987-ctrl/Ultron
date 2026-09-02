const { pathToFileURL } = require("url");
const f = p => pathToFileURL(p.replace(/\\/g, "/")).href;
(async () => {
  const m = await import(f("C:/Users/ranra/projects/Ultron/phone/orb-apk/_check/_gen/three_stub.mjs"));
  console.log("THREE keys:", Object.keys(m.THREE).length, "| Scene:", typeof m.THREE.Scene, "| WebGLRenderer:", typeof m.THREE.WebGLRenderer);
})();

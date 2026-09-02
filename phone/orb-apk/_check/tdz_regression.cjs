// Regression check: verify the v1.2.2 TDZ bug class is caught.
// Runs ONLY section 1 (static TDZ scan) of the harness against a given file.
const fs = require("fs");
const file = process.argv[2];
const html = fs.readFileSync(file, "utf8");
const mod = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const inv = mod.indexOf("animate();");
const fnStart = mod.indexOf("function animate");
const body = mod.slice(fnStart, inv);
let bad = 0;
const declRe = /^(?:let|const)\s+([A-Za-z_$][\w$]*)/gm;
declRe.lastIndex = inv;
let m;
while ((m = declRe.exec(mod))) {
  const name = m[1];
  if (new RegExp("\\b" + name + "\\b").test(body)) {
    console.log("CAUGHT TDZ: '" + name + "' declared after animate() but used inside it");
    bad++;
  }
}
console.log(bad ? "REGRESSION CHECK: harness WOULD have caught it (" + bad + " findings)" : "clean");

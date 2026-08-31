/**
 * ULTRON premium orb visuals — cinematic layer.
 * Adds to the existing scene: a shader energy core, a volumetric god-ray sprite,
 * a drifting nebula particle field, a reactive "speaking" pulse, plus upgraded
 * audio-mouthing, an outer inverted-fresnel depth shell, state color grading and
 * subtle caustic surface noise. Designed to look like a living AI brain.
 */
import * as THREE from "three";

type OrbState = "idle" | "listening" | "thinking" | "speaking" | "recovering";

export interface PremiumOrb {
  group: THREE.Group;
  setAudioLevel(level: number): void;
  setState(state: OrbState): void;
  update(t: number): void;
  dispose(): void;
}

/** State → signature color (idle=amber, listening=hot/white, thinking=ice/blue, speaking=green). */
function colForState(s: OrbState): THREE.Color {
  switch (s) {
    case "idle": return new THREE.Color(0xffcc66);      // amber
    case "listening": return new THREE.Color(0xfff2dd); // hot / white
    case "thinking": return new THREE.Color(0x66ccff);  // ice / blue
    case "speaking": return new THREE.Color(0x66ff99);  // green
    case "recovering": return new THREE.Color(0xff5544);  // alert red/amber (self-heal)
  }
}

export function createPremiumOrb(): PremiumOrb {
  const group = new THREE.Group();

  // --- Energy core: custom shader (fresnel + noise pulse + audio mouthing) ---
  const coreUniforms = {
    uTime: { value: 0 },
    uLevel: { value: 0 },
    uColorA: { value: new THREE.Color(0xffcc66) },
    uColorB: { value: new THREE.Color(0x66ccff) },
  };
  const coreMat = new THREE.ShaderMaterial({
    uniforms: coreUniforms,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    vertexShader: `
      varying vec3 vN; varying vec3 vP; varying vec2 vUv;
      void main(){
        vUv = uv;
        vN = normalize(normalMatrix*normal);
        vec4 mv = modelViewMatrix*vec4(position,1.0); vP = mv.xyz;
        gl_Position = projectionMatrix*mv;
      }`,
    fragmentShader: `
      uniform float uTime; uniform float uLevel; uniform vec3 uColorA; uniform vec3 uColorB;
      varying vec3 vN; varying vec3 vP; varying vec2 vUv;

      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float noise(vec2 p){
        vec2 i = floor(p); vec2 f = fract(p);
        float a = hash(i);
        float b = hash(i+vec2(1.0,0.0));
        float c = hash(i+vec2(0.0,1.0));
        float d = hash(i+vec2(1.0,1.0));
        vec2 u = f*f*(3.0-2.0*f);
        return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
      }

      void main(){
        float fres = pow(1.0 - abs(dot(normalize(vN), normalize(-vP))), 2.0);
        // cheap caustic surface noise — keeps the surface alive
        float caustic = noise(vUv*6.0 + uTime*0.3);
        // audio "mouthing": a travelling ripple driven by uLevel
        float ripple = sin(vUv.y*20.0 + uTime*10.0)*uLevel*0.3;
        float pulse = 0.5 + 0.5*sin(uTime*3.0) + uLevel*1.6 + ripple;
        vec3 col = mix(uColorA, uColorB, fres);
        col += caustic*0.08;
        float a = fres*0.9 + uLevel*0.45 + 0.08 + caustic*0.04 + abs(ripple)*0.3;
        gl_FragColor = vec4(col*pulse, a);
      }`,
  });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 4), coreMat);
  group.add(core);

  // --- Outer depth shell: larger inverted-fresnel (bright center, transparent rim) ---
  const shellUniforms = {
    uTime: { value: 0 },
    uColor: { value: colForState("idle").clone() },
  };
  const shellMat = new THREE.ShaderMaterial({
    uniforms: shellUniforms,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.FrontSide,
    vertexShader: `
      varying vec3 vN; varying vec3 vP;
      void main(){
        vN = normalize(normalMatrix*normal);
        vec4 mv = modelViewMatrix*vec4(position,1.0); vP = mv.xyz;
        gl_Position = projectionMatrix*mv;
      }`,
    fragmentShader: `
      uniform float uTime; uniform vec3 uColor;
      varying vec3 vN; varying vec3 vP;
      void main(){
        float fres = pow(1.0 - abs(dot(normalize(vN), normalize(-vP))), 2.0);
        // inverted fresnel: solid/translucent at center, fades to nothing at the rim
        float a = (1.0 - fres) * 0.5;
        float shimmer = 0.85 + 0.15*sin(uTime*1.5 + vP.y*4.0);
        gl_FragColor = vec4(uColor*shimmer, a);
      }`,
  });
  const shell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.7, 3), shellMat);
  group.add(shell);

  // inner glow sphere
  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(0.55, 32, 32),
    new THREE.MeshBasicMaterial({ color: 0xffaa30, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  group.add(glow);

  // --- God-ray sprite (additive radial) ---
  const rayTex = makeRadialTexture();
  const rayMat = new THREE.SpriteMaterial({ map: rayTex, color: 0xffbb55, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.5 });
  const ray = new THREE.Sprite(rayMat);
  ray.scale.set(6, 6, 1);
  group.add(ray);

  // --- Nebula particle field (drifting, depth) ---
  const N = 1400;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const ca = new THREE.Color(0xffaa30), cb = new THREE.Color(0x4488ff);
  for (let i = 0; i < N; i++) {
    const r = 1.2 + Math.random() * 4.5;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    pos[i * 3 + 1] = r * Math.cos(ph) * 0.7;
    pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    const c = ca.clone().lerp(cb, Math.random());
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  const ngeo = new THREE.BufferGeometry();
  ngeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  ngeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const nebulaMat = new THREE.PointsMaterial({
    size: 0.05, vertexColors: true, transparent: true, opacity: 0.55,
    blending: THREE.AdditiveBlending, depthWrite: false, map: rayTex,
    color: colForState("idle").clone(),
  });
  const nebula = new THREE.Points(ngeo, nebulaMat);
  group.add(nebula);

  let audio = 0, target = 0, state: OrbState = "idle";
  // targets we lerp the nebula + shell colors toward each frame
  const nebulaTint = colForState("idle").clone();
  const shellTint = colForState("idle").clone();

  return {
    group,
    setAudioLevel(l: number) { target = Math.max(0, Math.min(1, l)); },
    setState(s) {
      state = s;
      const c = colForState(s);
      nebulaTint.copy(c);
      shellTint.copy(c);
    },
    update(t: number) {
      audio = THREE.MathUtils.lerp(audio, target, 0.25);
      coreUniforms.uTime.value = t;
      shellUniforms.uTime.value = t;
      coreUniforms.uLevel.value = audio + (state === "thinking" ? 0.25 * (0.5 + 0.5 * Math.sin(t * 6)) : 0);

      // audio-driven color grading: nebula + shell lerp toward the state color
      nebulaMat.color.lerp(nebulaTint, 0.05);
      shellUniforms.uColor.value.lerp(shellTint, 0.05);

      const listenThrob = state === "listening" ? (0.5 + 0.5 * Math.sin(t * 9.0)) * 0.35 : 0;
      const recoverThrob = state === "recovering" ? (0.5 + 0.5 * Math.sin(t * 14.0)) * 0.5 : 0;
      const breathe = 1 + Math.sin(t * 0.8) * 0.04 + audio * 0.5 + listenThrob + recoverThrob;
      core.scale.setScalar(breathe);
      glow.scale.setScalar(breathe * (1 + audio * 0.6));
      (glow.material as THREE.MeshBasicMaterial).opacity = 0.1 + audio * 0.5 + (state === "speaking" ? 0.12 : 0) + listenThrob + recoverThrob * 0.6;
      rayMat.opacity = 0.35 + audio * 0.6 + (state === "listening" ? 0.25 + 0.2*Math.sin(t*9.0) : 0) + (state === "thinking" ? 0.1 : 0) + recoverThrob * 0.8;
      ray.scale.setScalar(6 + audio * 3 + Math.sin(t * 0.5) * 0.3 + listenThrob * 2 + recoverThrob * 2);
      ray.material.color.set(state === "thinking" ? 0x66ccff : state === "listening" ? 0xffdd88 : state === "recovering" ? 0xff5544 : 0xffbb55);

      // counter-rotate the depth shell for volumetric feel
      shell.rotation.y -= 0.0009;
      shell.rotation.x += 0.0004;

      nebula.rotation.y += 0.0006;
      nebula.rotation.x = Math.sin(t * 0.1) * 0.2;
    },
    dispose() {
      core.geometry.dispose(); coreMat.dispose();
      shell.geometry.dispose(); shellMat.dispose();
      glow.geometry.dispose();
      (glow.material as THREE.Material).dispose(); rayTex.dispose();
      ngeo.dispose(); (nebula.material as THREE.Material).dispose();
    },
  };
}

function makeRadialTexture(): THREE.Texture {
  const s = 128;
  const c = document.createElement("canvas"); c.width = c.height = s;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.2, "rgba(255,220,150,0.7)");
  g.addColorStop(0.5, "rgba(255,160,60,0.25)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  return tex;
}

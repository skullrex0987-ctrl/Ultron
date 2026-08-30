/**
 * ULTRON premium orb visuals — cinematic layer.
 * Adds to the existing scene: a shader energy core, a volumetric god-ray sprite,
 * a drifting nebula particle field, and a reactive "speaking" pulse. Designed to
 * look like a living AI brain, not a wireframe ball.
 */
import * as THREE from "three";

export interface PremiumOrb {
  group: THREE.Group;
  setAudioLevel(level: number): void;
  setState(state: "idle" | "listening" | "thinking" | "speaking"): void;
  update(t: number): void;
  dispose(): void;
}

export function createPremiumOrb(): PremiumOrb {
  const group = new THREE.Group();

  // --- Energy core: custom shader (fresnel + noise pulse) ---
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
      varying vec3 vN; varying vec3 vP;
      void main(){ vN = normalize(normalMatrix*normal);
        vec4 mv = modelViewMatrix*vec4(position,1.0); vP = mv.xyz;
        gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `
      uniform float uTime; uniform float uLevel; uniform vec3 uColorA; uniform vec3 uColorB;
      varying vec3 vN; varying vec3 vP;
      void main(){
        float fres = pow(1.0 - abs(dot(normalize(vN), normalize(-vP))), 2.0);
        float pulse = 0.5 + 0.5*sin(uTime*3.0) + uLevel*1.5;
        vec3 col = mix(uColorA, uColorB, fres);
        float a = fres*0.9 + uLevel*0.4 + 0.08;
        gl_FragColor = vec4(col*pulse, a);
      }`,
  });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 4), coreMat);
  group.add(core);

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
  const nebula = new THREE.Points(ngeo, new THREE.PointsMaterial({
    size: 0.05, vertexColors: true, transparent: true, opacity: 0.55,
    blending: THREE.AdditiveBlending, depthWrite: false, map: rayTex,
  }));
  group.add(nebula);

  let audio = 0, target = 0, state: any = "idle";

  return {
    group,
    setAudioLevel(l: number) { target = Math.max(0, Math.min(1, l)); },
    setState(s) { state = s; },
    update(t: number) {
      audio = THREE.MathUtils.lerp(audio, target, 0.25);
      coreUniforms.uTime.value = t;
      coreUniforms.uLevel.value = audio + (state === "thinking" ? 0.25 * (0.5 + 0.5 * Math.sin(t * 6)) : 0);
      const breathe = 1 + Math.sin(t * 0.8) * 0.04 + audio * 0.5;
      core.scale.setScalar(breathe);
      glow.scale.setScalar(breathe * (1 + audio * 0.6));
      (glow.material as THREE.MeshBasicMaterial).opacity = 0.1 + audio * 0.35 + (state === "speaking" ? 0.1 : 0);
      rayMat.opacity = 0.35 + audio * 0.5 + (state === "listening" ? 0.15 : 0);
      ray.scale.setScalar(6 + audio * 3 + Math.sin(t * 0.5) * 0.3);
      ray.material.color.set(state === "thinking" ? 0x66ccff : 0xffbb55);
      nebula.rotation.y += 0.0006;
      nebula.rotation.x = Math.sin(t * 0.1) * 0.2;
    },
    dispose() {
      core.geometry.dispose(); coreMat.dispose(); glow.geometry.dispose();
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

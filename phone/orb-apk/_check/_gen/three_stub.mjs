
import * as R from "file:///C:/Users/ranra/projects/Ultron/phone/orb-apk/www/vendor/js/three.module.js";
class WebGLRendererStub {
  constructor(){ this.domElement = { style:{}, appendChild(){}, remove(){} };
    this.toneMapping = 0; this.toneMappingExposure = 1; }
  getDrawingBufferSize(v){ v.width=800; v.height=600; return v; }
  getSize(v){ v.width=800; v.height=600; return v; }
  setPixelRatio(){} getPixelRatio(){return 2;} setSize(){} render(){} setRenderTarget(){} getRenderTarget(){return null;}
  clear(){} copyFramebufferToTexture(){}
}
export default new Proxy(R, { get(t, p){ if (p === "WebGLRenderer") return WebGLRendererStub; return t[p]; } });

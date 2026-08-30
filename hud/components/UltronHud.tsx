"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createOrbScene, type OrbSceneApi } from "@/lib/orbScene";
import { HandTracker, type TrackerStatus } from "@/lib/handTracker";
import { UltronBridge } from "@/lib/ultronBridge";

type CameraState = "off" | "starting" | "on" | "error";
type AgentState = "idle" | "listening" | "thinking" | "speaking";

const MODE_LABEL: Record<TrackerStatus["mode"], string> = {
  idle: "STANDBY",
  spin: "SPIN",
  zoom: "ZOOM",
};

export default function UltronHud() {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<OrbSceneApi | null>(null);
  const trackerRef = useRef<HandTracker | null>(null);
  const bridgeRef = useRef<UltronBridge | null>(null);

  const [camera, setCamera] = useState<CameraState>("off");
  const [status, setStatus] = useState<TrackerStatus>({ hands: 0, mode: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [agent, setAgent] = useState<AgentState>("idle");
  const [transcript, setTranscript] = useState<string[]>([]);
  const [link, setLink] = useState<string>("disconnected");
  const [wake, setWake] = useState(false);
  const recognitionRef = useRef<any>(null);

  // browser TTS (Q8 B) — speak ULTRON replies
  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02; u.pitch = 0.9;
    const voices = window.speechSynthesis.getVoices();
    const en = voices.find((v) => /en[-_]US/i.test(v.lang)) || voices[0];
    if (en) u.voice = en;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }, []);

  // browser STT (Web Speech API) — real microphone capture -> core
  const startListening = useCallback(() => {
    const SR: any = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setError("SPEECH RECOGNITION NOT SUPPORTED IN THIS BROWSER"); return; }
    const rec = new SR();
    rec.lang = "en-US"; rec.interimResults = false; rec.continuous = false;
    rec.onresult = (e: any) => {
      const text = e.results[0][0].transcript.trim();
      if (text) {
        setTranscript((t) => [...t.slice(-8), `YOU: ${text}`]);
        bridgeRef.current?.send({ type: "transcript", text });
      }
    };
    rec.onend = () => setAgent((a) => (a === "listening" ? "idle" : a));
    rec.onerror = () => setAgent((a) => (a === "listening" ? "idle" : a));
    recognitionRef.current = rec;
    rec.start();
    setAgent("listening");
  }, []);

  // audio-reactive binding
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const scene = createOrbScene(container);
    sceneRef.current = scene;

    // bridge to core (audio level + transcript + link state)
    const bridge = new UltronBridge();
    bridgeRef.current = bridge;
    bridge.on((m) => {
      if (m.type === "audio") scene.setAudioLevel(Number(m.level) || 0);
      if (m.type === "state") {
        const s = m.state as AgentState;
        setAgent(s);
        scene.setState(s);
      }
      if (m.type === "transcript") {
        setTranscript((t) => [...t.slice(-8), `${m.who === "user" ? "YOU" : "ULTRON"}: ${m.text}`]);
        if (m.who !== "user") speak(String(m.text));
      }
      if (m.type === "tts") speak(String(m.text));
      if (m.type === "link") setLink(String(m.status));
    });
    bridge.connect();

    // mic -> Vosk happens in core; here we just send a "talk" trigger on hold/wake
    return () => {
      trackerRef.current?.stop();
      trackerRef.current = null;
      scene.dispose();
      sceneRef.current = null;
    };
  }, []);

  const stopGestures = useCallback(() => {
    trackerRef.current?.stop();
    trackerRef.current = null;
    setCamera("off");
    setStatus({ hands: 0, mode: "idle" });
  }, []);

  const startGestures = useCallback(async () => {
    const video = videoRef.current;
    const overlay = overlayRef.current;
    if (!video || !overlay || trackerRef.current) return;
    setCamera("starting");
    setError(null);
    const tracker = new HandTracker(video, overlay, {
      onRotate: (dt, dp) => sceneRef.current?.rotateBy(dt, dp),
      onZoom: (factor) => sceneRef.current?.zoomBy(factor),
      onStatus: setStatus,
    });
    trackerRef.current = tracker;
    try {
      await tracker.start();
      setCamera("on");
    } catch (err) {
      trackerRef.current = null;
      tracker.stop();
      setCamera("error");
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "CAMERA ACCESS DENIED"
          : "TRACKING INIT FAILED",
      );
    }
  }, []);

  const toggleGestures = useCallback(() => {
    if (trackerRef.current) stopGestures();
    else void startGestures();
  }, [startGestures, stopGestures]);

  // gesture -> agent command: pinch (1 hand) = wake/stop talk; two-hand pinch = toggle link
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case "+": case "=": sceneRef.current?.zoomIn(); break;
        case "-": case "_": sceneRef.current?.zoomOut(); break;
        case "r": case "R": sceneRef.current?.resetView(); break;
        case "g": case "G": toggleGestures(); break;
        case "w": case "W": setWake((w) => !w); bridgeRef.current?.send({ type: "wake", on: !wake }); break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleGestures, wake]);

  const triggerTalk = useCallback(() => {
    startListening();
  }, [startListening]);

  const cameraOn = camera === "on";

  return (
    <>
      <div ref={containerRef} className="orb-root" />

      <div className="overlay-vignette" />
      <div className="overlay-grain" />
      <div className="overlay-scanlines" />

      <div className="hud hud-title">U.L.T.R.O.N.</div>

      <div className="hud hud-status">
        <span className={`dot dot-${agent}`} /> {agent.toUpperCase()} · LINK: {link.toUpperCase()}
      </div>

      <div className="hud hud-hint">
        <div>
          <span className="key">DRAG</span> spin&nbsp;&nbsp;
          <span className="key">SCROLL</span> zoom
        </div>
        {cameraOn ? (
          <div>
            <span className="key">PINCH</span> wake/stop&nbsp;&nbsp;
            <span className="key">PINCH BOTH</span> toggle link
          </div>
        ) : (
          <div>
            <span className="key">G</span> gestures&nbsp;&nbsp;
            <span className="key">W</span> wake-word&nbsp;&nbsp;
            <span className="key">T</span> talk
          </div>
        )}
      </div>

      <div className="hud hud-transcript">
        {transcript.map((t, i) => (
          <div key={i} className="tr-line">{t}</div>
        ))}
      </div>

      <div className="hud hud-controls">
        <div className={`camera-panel${cameraOn ? " visible" : ""}`}>
          <video ref={videoRef} muted playsInline className="camera-video" />
          <canvas ref={overlayRef} width={208} height={156} className="camera-overlay" />
          <div className="camera-status">
            {status.hands > 0
              ? `${status.hands} HAND${status.hands > 1 ? "S" : ""} · ${MODE_LABEL[status.mode]}`
              : "SHOW HANDS"}
          </div>
        </div>

        {error && <div className="hud-error">{error}</div>}

        <div className="hud-row">
          <button type="button" className="hud-btn" aria-pressed={cameraOn}
            onClick={toggleGestures} disabled={camera === "starting"}>
            {camera === "starting" ? "INITIALIZING…" : cameraOn ? "GESTURES ON" : "GESTURES OFF"}
          </button>
        </div>
        <div className="hud-row">
          <button type="button" className={`hud-btn${wake ? " active" : ""}`}
            onClick={() => { setWake((w) => !w); bridgeRef.current?.send({ type: "wake", on: !wake }); }}>
            {wake ? "WAKE ON" : "WAKE OFF"}
          </button>
          <button type="button" className="hud-btn" onClick={triggerTalk}>TALK</button>
          <button type="button" className="hud-btn" onClick={() => sceneRef.current?.resetView()}>RESET</button>
        </div>
      </div>
    </>
  );
}

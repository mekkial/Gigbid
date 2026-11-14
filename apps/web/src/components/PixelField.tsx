import { useEffect, useRef } from "react";

/** A small cobalt pixel field (same idea as the landing mosaic): drifts slowly, cells swell and brighten near the pointer. Static if the user prefers reduced motion. */
export function PixelField({ height = 120, cell = 14, className = "" }: { height?: number; cell?: number; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return; const ctx = cv.getContext("2d"); if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ramp = ["#eceeff", "#c9d2ff", "#a3b2ff", "#7b90ff", "#4f6bff", "#2f4dff", "#1b36f2"];
    let w = 0, h = 0, raf = 0, mx = -999, my = -999, visible = true;
    const hash = (x: number, y: number) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };
    const noise = (x: number, y: number) => { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi; const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
      return hash(xi, yi) * (1 - u) * (1 - v) + hash(xi + 1, yi) * u * (1 - v) + hash(xi, yi + 1) * (1 - u) * v + hash(xi + 1, yi + 1) * u * v; };
    const resize = () => { const r = cv.getBoundingClientRect(); const d = Math.min(2, window.devicePixelRatio || 1); w = r.width; h = r.height; cv.width = w * d; cv.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0); };
    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      for (let y = 0; y < h; y += cell) for (let x = 0; x < w; x += cell) {
        const n = noise(x / 90 + t * 0.00006, y / 70 - t * 0.00004) * 0.75 + noise(x / 30, y / 30 + t * 0.00008) * 0.25;
        const dx = x + cell / 2 - mx, dy = y + cell / 2 - my, near = Math.max(0, 1 - Math.hypot(dx, dy) / 110);
        const v = Math.min(0.999, n * (0.55 + (x / w) * 0.6) + near * 0.35);
        ctx.fillStyle = ramp[Math.floor(v * ramp.length)]; const s = cell - 1 + near * 3; ctx.fillRect(x - near * 1.5, y - near * 1.5, s, s);
      }
    };
    const loop = (t: number) => { if (visible) draw(t); raf = requestAnimationFrame(loop); };
    const move = (e: PointerEvent) => { const r = cv.getBoundingClientRect(); mx = e.clientX - r.left; my = e.clientY - r.top; };
    const leave = () => { mx = my = -999; };
    resize(); draw(0);
    const ro = new ResizeObserver(() => { resize(); draw(0); }); ro.observe(cv);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }); io.observe(cv);
    cv.addEventListener("pointermove", move); cv.addEventListener("pointerleave", leave);
    if (!reduce) raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); cv.removeEventListener("pointermove", move); cv.removeEventListener("pointerleave", leave); };
  }, [cell]);
  return <canvas ref={ref} className={`pixel-field ${className}`} style={{ height }} aria-hidden="true" />;
}

/** Counts up to `to` when it scrolls into view. */
export function CountUp({ to, decimals = 0, suffix = "", prefix = "" }: { to: number; decimals?: number; suffix?: string; prefix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const set = (v: number) => { el.textContent = `${prefix}${v.toFixed(decimals)}${suffix}`; };
    if (reduce) { set(to); return; }
    set(0); let raf = 0;
    const io = new IntersectionObserver(([e]) => { if (!e.isIntersecting) return; io.disconnect(); const t0 = performance.now();
      const step = (t: number) => { const p = Math.min(1, (t - t0) / 900); set(to * (1 - Math.pow(1 - p, 3))); if (p < 1) raf = requestAnimationFrame(step); }; raf = requestAnimationFrame(step); });
    io.observe(el); return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, decimals, suffix, prefix]);
  return <span ref={ref}>{`${prefix}${to.toFixed(decimals)}${suffix}`}</span>;
}

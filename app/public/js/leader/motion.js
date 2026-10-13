export const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const outCubic = (t) => 1 - (1 - t) ** 3;
export const inOutCubic = (t) => t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
export const outBack = (t) => 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2;

/** Advance by rendered frames; a suspended tab never catches up in one frame. */
export function animate(duration, update, done = () => {}) {
  let frame, elapsed = 0, last = null, stopped = false;
  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const reset = () => { last = null; };
  const cancel = () => {
    stopped = true; cancelAnimationFrame(frame);
    document.removeEventListener('visibilitychange', reset); mq.removeEventListener('change', finish);
  };
  const finish = () => { if (!stopped) { cancel(); update(1); done(); } };
  const tick = () => {
    const now = performance.now();
    if (stopped) return;
    if (document.hidden) last = null;
    else {
      elapsed += last == null ? 0 : Math.min(34, Math.max(0, now - last)); last = now;
      if (elapsed >= duration) return finish();
      update(elapsed / duration);
    }
    frame = requestAnimationFrame(tick);
  };
  if (mq.matches) { update(1); done(); return () => {}; }
  document.addEventListener('visibilitychange', reset); mq.addEventListener('change', finish);
  update(0); frame = requestAnimationFrame(tick); return cancel;
}

export function appear(el, duration = 250, distance = 6, delay = 0) {
  return animate(duration + delay, (t) => {
    const x = outCubic(Math.max(0, (t * (duration + delay) - delay) / duration));
    el.style.opacity = x; el.style.transform = `translateY(${distance * (1 - x)}px)`;
  }, () => { el.style.removeProperty('opacity'); el.style.removeProperty('transform'); });
}

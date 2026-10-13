import { esc, t } from '../lib.js';
import { signed } from '../fmt.js';
import { animate, inOutCubic, outBack, reduced } from './motion.js';

const point = (value, radius = 128) => {
  const angle = Math.PI * (1 - (value + 100) / 200);
  return [160 + radius * Math.cos(angle), 160 - radius * Math.sin(angle)];
};
const arc = (a, b) => `M${point(a).join(' ')} A128 128 0 0 1 ${point(b).join(' ')}`;
export const zone = (v) => v == null ? 'neu' : v >= 15 ? 'pos' : v <= -15 ? 'neg' : 'neu';
export function gauge() {
  return `<button class="leader-gauge" aria-label="${esc(t('leader.replay'))}">
    <svg viewBox="0 0 320 184" aria-hidden="true">
      <g fill="none" stroke-width="18" stroke-linecap="butt">
        <path class="leader-zone-neg" d="${arc(-100, -16)}"/><path class="leader-zone-neu" d="${arc(-14, 14)}"/>
        <path class="leader-zone-pos" d="${arc(16, 100)}"/><path data-fill/>
      </g><g class="leader-ticks"><text x="32" y="181" text-anchor="middle">−100</text>
        <text x="160" y="13" text-anchor="middle">0</text><text x="288" y="181" text-anchor="middle">+100</text></g>
      <line data-needle x1="160" y1="160" stroke-width="3.5" stroke-linecap="round"/>
      <circle class="leader-hub" cx="160" cy="160" r="9"/><circle class="leader-pin" cx="160" cy="160" r="3.5"/>
    </svg><strong data-mood>—</strong><span data-zone></span></button>`;
}

export function mountGauge(el, target, mode, from = 0) {
  let stop = () => {}, observer;
  const draw = (v) => {
    const value = Math.max(-100, Math.min(100, v)), [x, y] = point(value, 98), cls = zone(target);
    el.dataset.value = value; el.dataset.target = target ?? '';
    el.querySelector('[data-needle]').setAttribute('x2', x); el.querySelector('[data-needle]').setAttribute('y2', y);
    el.querySelector('[data-needle]').style.stroke = `var(--${target == null ? 'neu' : 'ink'})`;
    const fill = el.querySelector('[data-fill]'); fill.setAttribute('d', value > 16 ? arc(16, value) : value < -16 ? arc(value, -16) : '');
    fill.style.stroke = `var(--${value < 0 ? 'neg' : 'pos'})`;
    el.querySelector('[data-mood]').textContent = target == null ? '—' : signed(Math.round(value));
    el.querySelector('[data-mood]').className = cls;
    el.querySelector('[data-zone]').textContent = t(target == null ? 'leader.noNews' : 'ov.' + cls);
    el.querySelector('[data-zone]').className = cls;
  };
  const run = (entry) => {
    stop(); el.dataset.entry = String(entry);
    if (entry) el.dispatchEvent(new Event('entrystart'));
    if (target == null || reduced() || mode === 'static' && !entry) { draw(target || 0); return; }
    const initial = +el.dataset.value || from;
    stop = animate(entry ? 2000 : 950, (t) => {
      if (entry) draw(t <= .45 ? -100 + 200 * inOutCubic(t / .45) : 100 + (target - 100) * outBack((t - .45) / .55));
      else draw(initial + (target - initial) * outBack(t));
    });
  };
  draw(mode === 'entry' && target != null && !reduced() ? -100 : mode === 'update' ? from : target || 0);
  if (mode === 'entry' && !reduced() && target != null) {
    observer = new IntersectionObserver(([e]) => { if (e.intersectionRatio >= .6) { observer.disconnect(); run(true); } }, { threshold: .6 });
    observer.observe(el);
  } else run(false);
  el.onclick = () => { observer?.disconnect(); run(true); };
  return () => { stop(); observer?.disconnect(); };
}

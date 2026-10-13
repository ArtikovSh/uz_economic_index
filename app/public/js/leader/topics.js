import { number, text } from './components.js';
import { aggregate, selectedTopics, TONES } from './model.js';

export function topics(ctx) {
  const cur = aggregate(ctx.data, ctx.period().p, selectedTopics(ctx.prefs)), max = cur.topics[0]?.total || 1;
  return `<section class="leader-card leader-topics"><div class="leader-legend">${TONES.map((tone) => `<span><i class="${tone}"></i>${text('ov.' + tone)}</span>`).join('')}<small>${text('leader.countShare')}</small></div>
    <div class="leader-topic-rows">${cur.topics.map((r) => `<button data-open-topic="${r.key}" class="leader-topic-row ${r.total ? '' : 'muted'}">
      <span class="leader-topic-line"><b>${text('topics.' + r.key)}</b><span class="leader-topic-tones">${r.tones.map((n, i) => number(r.key + TONES[i], n, '', TONES[i])).join(' | ')}</span>
      <strong>${number(r.key + '-total', r.total)}</strong><small>${number(r.key + '-share', cur.total ? Math.round(100 * r.total / cur.total) : 0, 'percent')}</small></span>
      <span class="leader-topic-bar"><span data-bar="topic-${r.key}" style="width:${100 * r.total / max}%">${r.tones.map((n, i) => `<i class="${TONES[i]}" data-bar="${r.key}-${i}" style="flex-grow:${n}"></i>`).join('')}</span></span></button>`).join('')}</div></section>`;
}
export function mountTopics(ctx) {
  ctx.main.querySelectorAll('[data-open-topic]').forEach((b) => { b.onclick = () => ctx.openNews({ topics: [b.dataset.openTopic] }); });
}

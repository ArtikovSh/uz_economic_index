import { icon, t } from '../lib.js';
import { text, number } from './components.js';
import { gauge, mountGauge } from './gauge.js';
import { aggregate, label, previous, selectedChannels, selectedTopics, TONES } from './model.js';

const change = (key, delta, points = false, good = delta, neutral = false) => {
  if (delta == null) return '—';
  if (!delta) return `${points ? icon('arrowRight', 14) : ''}${text('leader.unchanged')}`;
  return `<span class="leader-change ${neutral ? 'muted' : good > 0 ? 'pos' : 'neg'}">${icon(delta > 0 ? 'up' : 'down', 14)}${number(key, points ? delta : Math.abs(delta), points ? 'leader.points' : '')}${points ? '' : ' ' + text('ov.pp')}</span>`;
};
export function home(ctx) {
  const { p } = ctx.period(), topics = selectedTopics(ctx.prefs);
  const cur = aggregate(ctx.data, p, topics), prev = aggregate(ctx.data, p && previous(p), topics);
  const delta = cur.mood == null || prev.mood == null ? null : cur.mood - prev.mood;
  return `<div class="leader-home">
    <section class="leader-card leader-mood"><div class="leader-card-head"><h2>${text('leader.mood')}</h2>
      <span class="leader-info"><button class="icon-btn ghost" aria-label="${text('leader.mood')}" aria-describedby="leader-hint">${icon('info', 18)}</button>
      <span role="tooltip" id="leader-hint">${text('leader.hint')}</span></span></div>
      ${gauge()}<div class="leader-compare"><div><small>${label(p && previous(p), true)}</small><b>${prev.mood == null ? text('leader.noNews') : number('previous', prev.mood, 'signed')}</b></div>
      <div><small>${text('leader.change')}</small><b>${change('moodDelta', delta, true)}</b></div></div></section>
    <section class="leader-card leader-distribution"><div class="leader-card-head"><h2>${text('ov.tone')}</h2><small>${number('economic', cur.total, 'leader.economic')}</small></div>
      <div class="leader-bar">${TONES.map((key, i) => `<span class="${key}" data-bar="tone-${key}" style="flex-grow:${cur.shares[i]}"></span>`).join('')}</div>
      <div class="leader-shares">${TONES.map((key, i) => `<button data-news-tone="${key}"><span class="${key}">${text('ov.' + key)}${icon('chevronRight', 12)}</span>
        <b>${number('share-' + key, cur.shares[i], 'percent')}</b><small>${number('count-' + key, cur.tones[i], 'leader.count')}</small>
        <small>${change('delta-' + key, cur.total && prev.total ? cur.shares[i] - prev.shares[i] : null, false, (cur.shares[i] - prev.shares[i]) * (i === 2 ? -1 : 1), i === 1)}</small></button>`).join('')}</div></section>
    <section class="leader-card leader-coverage"><div><small>${text('ov.coverage')}</small><b>${number('days', cur.days, 'leader.days')}</b></div>
      <div><small>${text('ps.channels')}</small><b>${number('activeChannels', cur.channels)}/${number('selectedChannels', selectedChannels(ctx).length)}</b></div>
      <div><small>${text('leader.total')}</small><b>${number('allPosts', cur.posts, 'leader.count')}</b></div></section></div>`;
}
export function mountHome(ctx, mode, oldGauge) {
  const cur = aggregate(ctx.data, ctx.period().p, selectedTopics(ctx.prefs));
  const el = ctx.main.querySelector('.leader-gauge');
  el.addEventListener('entrystart', () => ctx.animateNumbers('entry'));
  ctx.track(mountGauge(el, cur.mood, mode, oldGauge));
  ctx.main.querySelectorAll('[data-news-tone]').forEach((b) => { b.onclick = () => ctx.openNews({ tone: b.dataset.newsTone }); });
  const info = ctx.main.querySelector('.leader-info button');
  info.onclick = () => info.parentElement.classList.toggle('open');
  info.onblur = () => info.parentElement.classList.remove('open');
}

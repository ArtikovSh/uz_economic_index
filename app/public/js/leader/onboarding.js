import { api, errorText, logo, t, toast } from '../lib.js';
import { num } from '../fmt.js';
import { bindPicker, channelPicker, text, topicTiles } from './components.js';
import { selectedChannels, selectedTopics, TOPICS } from './model.js';

export function onboarding(ctx) {
  let step = 1, channels = [...selectedChannels(ctx)], topics = [...selectedTopics(ctx.prefs)];
  function draw() {
    ctx.shell.innerHTML = `<div class="leader-onboarding"><header class="leader-onboard-header">${logo(34)}<b>${text('leader.title')}</b><small>${step} / 2</small></header>
      <main class="leader-onboard-main"><h1>${text(step === 1 ? 'leader.channelsTitle' : 'leader.topicsTitle')}</h1><p>${text(step === 1 ? 'leader.channelsNote' : 'leader.topicsNote')}</p>
      ${step === 1 ? channelPicker(ctx.data.channels, channels, true) : topicTiles(topics)}</main>
      <footer>${step === 2 ? `<button class="btn secondary" data-back>${text('back')}</button>` : ''}<button class="btn primary" data-next>${text(step === 1 ? 'leader.continueLabel' : 'leader.start', { n: num(channels.length) })}</button></footer></div>`;
    const next = ctx.shell.querySelector('[data-next]');
    if (step === 1) {
      const refresh = (chosen) => { channels = chosen; next.disabled = !channels.length; next.textContent = t(channels.length ? 'leader.continueLabel' : 'leader.needChannel', { n: num(channels.length) }); };
      bindPicker(ctx.shell, ctx.data.channels, channels, true, refresh); refresh(channels);
    } else {
      ctx.shell.querySelector('[data-back]').onclick = () => { step = 1; draw(); };
      ctx.shell.querySelectorAll('[data-topic]').forEach((b) => { b.onclick = () => {
        const key = b.dataset.topic;
        if (topics.includes(key) && topics.length === 1) return;
        topics = topics.includes(key) ? topics.filter((v) => v !== key) : [...topics, key];
        b.setAttribute('aria-pressed', topics.includes(key));
      }; });
    }
    next.onclick = async () => {
      if (step === 1) { step = 2; draw(); return; }
      next.disabled = true;
      try {
        const r = await api('prefs_set', { channels, topics: topics.length === TOPICS.length ? [] : topics, onboarded: true });
        if (!r.ok) throw r;
        ctx.prefs = r.prefs;
        const data = await api('leader_stats', { channels }); if (!data.ok) throw data;
        ctx.data = data; ctx.launch();
      } catch (r) { toast(errorText(r)); next.disabled = false; }
    };
  }
  draw();
}

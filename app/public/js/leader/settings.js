import { api, errorText, esc, fmtDate, icon, lang, LANGS, setLang, t, toast } from '../lib.js';
import { num } from '../fmt.js';
import { bindPicker, channelPicker, sheet, text, topicTiles } from './components.js';
import { selectedChannels, selectedTopics, TOPICS } from './model.js';

export function settings(ctx) {
  const chosen = selectedChannels(ctx), topics = selectedTopics(ctx.prefs), me = ctx.me;
  const names = ctx.data.channels.filter((c) => chosen.includes(c.id)).map((c) => c.name).join(', ');
  const until = me.expires_at ? t('admin.until', { d: fmtDate(me.expires_at) }) : t('admin.noExpiry');
  return `<div class="leader-settings"><section class="leader-card leader-settings-topics"><div class="leader-card-head"><h2>${text('tabs.topics')}</h2>
    <small>${text(topics.length === TOPICS.length ? 'leader.allSelected' : 'leader.selectedTopics', { n: num(topics.length) })}</small></div>${topicTiles(topics)}</section>
    <section class="leader-card"><h2>${text('ps.channels')}</h2><button class="pick-row" data-pick-channels>
      <span class="t"><b>${text(chosen.length === ctx.data.channels.length ? 'ps.allChannels' : 'ps.nChannels', { n: num(chosen.length) })}</b><small>${esc(names)}</small></span>
      <span class="cnt">${text('ps.ofN', { n: num(ctx.data.channels.length) })}</span>${icon('chevronRight', 18)}</button></section>
    <section class="leader-card"><h2>${text('langTitle')}</h2><div class="leader-seg">${LANGS.map(([key, title]) => `<button data-language="${key}" aria-pressed="${key === lang()}">${esc(title)}</button>`).join('')}</div></section>
    <section class="leader-card"><button class="leader-digest" role="switch" aria-checked="${ctx.prefs.digest}" data-digest><span class="leader-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg></span>
      <span><b>${text('leader.digest')}</b><small>${text(ctx.prefs.digest ? 'leader.digestNote' : 'leader.off')}</small></span><i class="leader-switch"><i></i></i></button></section>
    <section class="leader-card"><div class="leader-account"><span class="leader-avatar">${icon('user')}</span><div><b>${esc(me.login)}</b><small>${text('roles.leader')} · ${esc(until)}</small></div></div>
      <button class="leader-logout" data-logout>${icon('logout')}${text('dash.logout')}</button></section></div>`;
}
export function mountSettings(ctx) {
  ctx.main.querySelectorAll('[data-topic]').forEach((b) => { b.onclick = () => {
    const picked = selectedTopics(ctx.prefs), key = b.dataset.topic;
    if (picked.includes(key) && picked.length === 1) return;
    const next = picked.includes(key) ? picked.filter((k) => k !== key) : [...picked, key];
    ctx.updatePrefs({ topics: next.length === TOPICS.length ? [] : next });
    ctx.draw('static', true);
  }; });
  ctx.main.querySelector('[data-pick-channels]').onclick = () => {
    const chosen = selectedChannels(ctx);
    sheet(ctx, t('ps.channels'), channelPicker(ctx.data.channels, chosen, false), (panel) => {
      bindPicker(panel, ctx.data.channels, chosen, false, (channels) => { ctx.updatePrefs({ channels }); ctx.draw('static', true); });
    }, 'channels');
  };
  ctx.main.querySelectorAll('[data-language]').forEach((b) => { b.onclick = () => { setLang(b.dataset.language); ctx.draw('static', true); }; });
  ctx.main.querySelector('[data-digest]').onclick = async (e) => {
    const button = e.currentTarget, on = !ctx.prefs.digest; button.disabled = true;
    try {
      const r = await api('digest', { on });
      if (!r.ok) throw r;
      ctx.prefs.digest = r.digest;
      if (ctx.ui.tab === 'settings') ctx.draw('static', true);
    } catch (r) { toast(errorText(r)); button.disabled = false; }
  };
  ctx.main.querySelector('[data-logout]').onclick = async (e) => {
    e.currentTarget.disabled = true;
    await ctx.flushPrefs();
    try { const r = await api('logout'); if (!r.ok) throw r; ctx.dispose(); ctx.nav.reload(); }
    catch (r) { toast(errorText(r)); e.target.disabled = false; }
  };
}

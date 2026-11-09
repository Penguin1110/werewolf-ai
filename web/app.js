// ============================================================================
//  月下狼人殺 — 觀戰 / 回放前端
//  事件流 (events) -> 狀態 (S) -> 畫面；可以播放、暫停、單步、跳轉、切換上帝視角
// ============================================================================
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const ROLE = { werewolf: '狼人', villager: '村民', seer: '預言家', witch: '女巫', hunter: '獵人', guard: '守衛' };
const TEAM = r => (r === 'werewolf' ? 'wolf' : 'village');
const SPEECH_KINDS = ['speech', 'wolf_chat', 'last_words', 'pk_speech', 'postgame'];
const KIND_NAME = { speech: '發言', wolf_chat: '狼人夜聊', wolf_kill: '狼人刀人', seer_check: '預言家查驗', witch: '女巫用藥', guard: '守衛守護', vote: '投票', pk_vote: 'PK 投票', pk_speech: 'PK 發言', last_words: '遺言', hunter_shoot: '獵人開槍', postgame: '賽後復盤' };

const P = { events: [], cursor: 0, playing: false, speed: 1, god: true, live: null, done: true, timer: null, lastStart: null };
let S = freshState();
let SETUP = null;
let seatSkillImportTarget = null;

function freshState() {
  return { players: {}, n: 0, day: 0, phase: 'setup', sub: '', roles: {}, revealed: {}, deathCause: {}, votes: {}, order: [], winner: null, board: '', boardName: '', seed: null, acting: null, pendingThought: {}, over: null };
}

// ---------------------------------------------------------------- 版面縮放
function fit() {
  const s = Math.min(innerWidth / 1600, innerHeight / 900);
  $('#stage').style.transform = `translate(-50%, -50%) scale(${s})`;
}
addEventListener('resize', fit);

// ---------------------------------------------------------------- 座位
function seatPos(seat) {
  const n = S.n || 9, i = seat - 1;
  const a = (-90 + (360 * i) / n) * Math.PI / 180;
  const rx = n >= 11 ? 640 : 610, ry = n >= 11 ? 262 : 248;
  return { x: 800 + rx * Math.cos(a), y: (n >= 11 ? 384 : 388) + ry * Math.sin(a) };
}
function anchor(seat) { const p = seatPos(seat); return { x: p.x, y: p.y - 28 }; }

function buildSeats() {
  const box = $('#seats');
  box.innerHTML = '';
  box.classList.toggle('seats-compact', S.n >= 11);
  Object.values(S.players).forEach(p => {
    const pos = seatPos(p.seat);
    const el = document.createElement('div');
    el.className = 'seat';
    el.id = 'seat-' + p.seat;
    el.style.left = pos.x + 'px';
    el.style.top = pos.y + 'px';
    el.innerHTML = `
      <div class="thinking">思考中 <i></i><i></i><i></i></div>
      <div class="portrait"><div class="face">${Art.avatar(p.name)}</div><div class="num">${p.seat}</div><div class="rolebadge"></div>
        <div class="tomb">${Art.ICON.tomb}</div><div class="votes"></div><div class="order"></div></div>
      <div class="nameplate">${esc(p.name)}</div>
      <div class="tags"><b>${esc(p.skill)}</b><br>${esc(modelLabel(p.model))}</div>
      <div class="deathnote"></div>`;
    box.appendChild(el);
  });
}
function modelLabel(m) {
  const found = SETUP && SETUP.models.find(x => x.id === m);
  return found ? found.label : m;
}

function renderSeats() {
  const tallies = {};
  Object.values(S.votes).forEach(t => { if (t) tallies[t] = (tallies[t] || 0) + 1; });
  const night = S.phase === 'night';
  Object.values(S.players).forEach(p => {
    const el = $('#seat-' + p.seat);
    if (!el) return;
    const role = S.roles[p.seat];
    const showRole = role && (P.god || S.revealed[p.seat] || S.postgame || S.over);
    el.classList.toggle('dead', !p.alive);
    el.classList.toggle('show-role', !!showRole);
    const badge = $('.rolebadge', el);
    const want = showRole ? (S.revealed[p.seat] && !P.god && !S.over ? S.revealed[p.seat] : role) : '';
    if (badge.dataset.role !== want) { badge.dataset.role = want; badge.innerHTML = want ? Art.emblem(want, 40) : ''; }
    const cause = S.deathCause[p.seat];
    const causeTxt = { wolf: '夜裡被刀', poison: '被毒殺', exile: '被放逐', shot: '被槍殺' }[cause];
    const pub = { night: '夜裡出局', exile: '被放逐', shot: '被帶走' }[p.publicCause];
    $('.deathnote', el).textContent = !p.alive ? `☠ 第${p.diedDay}天 · ${P.god && causeTxt ? causeTxt : pub || ''}` : '';
    const oi = S.order.indexOf(p.seat);
    el.classList.toggle('has-order', oi >= 0 && S.sub === '發言');
    $('.order', el).textContent = oi >= 0 ? `第${oi + 1}` : '';
    el.classList.toggle('voted', !!tallies[p.seat]);
    $('.votes', el).textContent = tallies[p.seat] ? tallies[p.seat] + '票' : '';
    const wolfTime = night && P.god && role === 'werewolf' && p.alive && ['狼人行動'].includes(S.sub);
    el.classList.toggle('wolfnight', !!wolfTime);
    el.classList.toggle('awake', !!(night && P.god && (S.awake === p.seat || wolfTime)));
    el.classList.toggle('acting', S.acting === p.seat && (P.god || S.phase === 'day'));
  });
  renderPhase();
}

function renderPhase() {
  const st = $('#stage');
  st.classList.toggle('day', S.phase === 'day' || S.phase === 'end');
  st.classList.toggle('night', S.phase === 'night' || S.phase === 'setup');
  st.classList.toggle('wolfhour', S.phase === 'night' && S.sub === '狼人行動' && P.god);
  let txt = '準備中';
  if (S.phase === 'night') txt = `第 ${S.day} 夜` + (S.sub ? ` · ${S.sub}` : '');
  else if (S.phase === 'day') txt = `第 ${S.day} 天` + (S.sub ? ` · ${S.sub}` : '');
  else if (S.phase === 'end') txt = S.postgame && !S.over ? '賽後復盤' : '對局結束';
  $('#phase-text').textContent = txt;
  $('#phase-icon').innerHTML = S.phase === 'day' || S.phase === 'end' ? Art.ICON.sun : Art.ICON.moon;
}

// ---------------------------------------------------------------- 狀態更新（不含動畫）
function apply(ev) {
  const d = ev.data;
  switch (ev.type) {
    case 'game_start': {
      const keep = { pendingThought: {} };
      S = Object.assign(freshState(), keep);
      S.n = d.players.length; S.board = d.board; S.boardName = d.board_name; S.seed = d.seed;
      d.players.forEach(p => { S.players[p.seat] = { ...p, alive: true }; });
      buildSeats();
      break;
    }
    case 'role_assign': S.roles = norm(d.roles); break;
    case 'phase': S.phase = d.phase; S.day = d.day; S.sub = ''; S.votes = {}; S.order = []; S.acting = null; break;
    case 'acting': S.acting = d.seat; break;
    case 'death': { const p = S.players[d.seat]; p.alive = false; p.publicCause = d.public_cause; p.diedDay = ev.day; break; }
    case 'death_detail': S.deathCause[d.seat] = d.cause; break;
    case 'hunter_shoot': S.revealed[d.seat] = 'hunter'; break;
    case 'speech_order': S.order = d.order; break;
    case 'pk_start': S.votes = {}; break;
    case 'vote': S.votes[d.seat] = d.target; break;
    case 'postgame_start': S.winner = d.winner; S.roles = norm(d.roles); S.phase = 'end'; S.postgame = true; break;
    case 'game_over': S.winner = d.winner; S.roles = norm(d.roles); S.over = d; S.phase = 'end'; break;
  }
  if (ev.type === 'acting') S.awake = d.seat;
  else if (!['thought', 'fallback', 'your_role', 'witch_info'].includes(ev.type)) S.acting = null;
  if (ev.type === 'phase') S.awake = null;
  const sub = subPhase(ev);
  if (sub) S.sub = sub;
}
function subPhase(ev) {
  const t = ev.type, k = ev.data && ev.data.kind;
  if (t === 'acting' && P.god) {
    if (k === 'wolf_chat' || k === 'wolf_kill') return '狼人行動';
    if (k === 'seer_check') return '預言家查驗'; if (k === 'witch') return '女巫用藥'; if (k === 'guard') return '守衛守護';
    if (k === 'hunter_shoot') return '獵人開槍';
  }
  if (t === 'speech_order' || t === 'speech') return ev.data.pk ? 'PK 發言' : '發言';
  if (t === 'vote') return '投票'; if (t === 'last_words') return '遺言'; if (t === 'pk_start') return 'PK';
  if (t === 'night_result') return '公布死訊';
  if (t === 'postgame_start' || t === 'postgame') return '賽後復盤';
  return null;
}
const norm = o => { const r = {}; Object.entries(o || {}).forEach(([k, v]) => (r[+k] = v)); return r; };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const visible = ev => P.god || ev.vis === 'all';
const pname = s => (S.players[s] ? `${s}號 ${S.players[s].name}` : `${s}號`);

// ---------------------------------------------------------------- 特效工具
function line(from, to, cls, marker) {
  const a = anchor(from), b = anchor(to);
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  const cx = mx + (410 - my) * 0.25 * 0, cy = my - Math.hypot(b.x - a.x, b.y - a.y) * 0.18;
  const sh = 0.86; // 箭頭停在頭像邊緣
  const ex = cx + (b.x - cx) * sh, ey = cy + (b.y - cy) * sh;
  const sx = cx + (a.x - cx) * 0.9, sy = cy + (a.y - cy) * 0.9;
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', `M${sx} ${sy} Q${cx} ${cy} ${ex} ${ey}`);
  p.setAttribute('class', cls);
  if (marker) p.setAttribute('marker-end', `url(#${marker})`);
  $('#fx-lines').appendChild(p);
  return p;
}
function clearLines(cls) { $$(cls ? '#fx-lines .' + cls : '#fx-lines path').forEach(p => p.remove()); }
function fxAt(seat, html, cls, ms, size = 90, dy = 0) {
  const a = anchor(seat);
  const el = document.createElement('div');
  el.className = 'fx-icon ' + (cls || '');
  el.style.left = a.x + 'px'; el.style.top = a.y + dy + 'px'; el.style.width = size + 'px'; el.style.height = size + 'px';
  el.innerHTML = html;
  $('#fxlayer').appendChild(el);
  later(() => { el.classList.add('fx-out'); later(() => el.remove(), 500); }, ms);
  return el;
}
function stamp(seat, text, cls, ms) {
  const a = anchor(seat);
  const el = document.createElement('div');
  el.className = 'fx-stamp ' + cls;
  el.style.left = a.x + 'px'; el.style.top = a.y + 'px';
  el.textContent = text;
  $('#fxlayer').appendChild(el);
  later(() => { el.classList.add('fx-out'); later(() => el.remove(), 500); }, ms);
}
function thoughtCloud(seat, text, ms) {
  const a = anchor(seat);
  const el = document.createElement('div');
  el.className = 'thought-cloud';
  el.style.left = Math.min(1460, Math.max(140, a.x)) + 'px'; el.style.top = a.y - 60 + 'px';
  el.innerHTML = `<b>💭 ${esc(pname(seat))}</b><br>${esc(text)}`;
  $('#fxlayer').appendChild(el);
  if (P.playing) later(() => el.remove(), ms);
  else el.classList.add('await-click');
}
function shake(seat) { const el = $('#seat-' + seat); if (el) { el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake'); } }
function banner(icon, title, sub, ms, red) {
  const b = $('#banner');
  b.className = '';
  b.innerHTML = `<div class="b-icon">${icon || ''}</div><div class="b-title">${esc(title)}</div>${sub ? `<div class="b-sub">${esc(sub)}</div>` : ''}`;
  b.style.setProperty('--bd', ms / P.speed + 'ms');
  void b.offsetWidth;
  b.className = 'show' + (red ? ' red' : '');
}
const timers = new Set();
function later(fn, ms) { const t = setTimeout(() => { timers.delete(t); fn(); }, ms / P.speed); timers.add(t); return t; }
function clearFx() { timers.forEach(clearTimeout); timers.clear(); $('#fxlayer').innerHTML = ''; clearLines(); $('#banner').className = ''; $('#tally').innerHTML = ''; stopType(); }

// ---------------------------------------------------------------- 對話框 + 打字機
let typeTimer = null, typeFull = '';
function stopType() { if (typeTimer) { clearInterval(typeTimer); typeTimer = null; } }
function dialog({ seat, channel, text, thought, cls }) {
  const dlg = $('#dialog');
  dlg.className = cls || '';
  const p = seat ? S.players[seat] : null;
  $('.dlg-portrait', dlg).innerHTML = p ? Art.avatar(p.name) : '';
  $('.dlg-channel', dlg).textContent = channel || '';
  $('.dlg-name', dlg).textContent = p ? pname(seat) : '主持人';
  const role = seat && S.roles[seat];
  $('.dlg-role', dlg).innerHTML = role && (P.god || S.over) ? `${Art.emblem(role, 22)} ${ROLE[role]}` : '';
  $('.dlg-tag', dlg).textContent = p ? `策略：${p.skill} · ${modelLabel(p.model)}` : '';
  const showT = P.god && thought;
  dlg.classList.toggle('with-thought', !!showT);
  $('.th-text', dlg).textContent = showT ? thought : '';
  if (!seat) dlg.classList.add('system');
  $$('.seat.speaking').forEach(x => x.classList.remove('speaking'));
  if (seat && $('#seat-' + seat)) $('#seat-' + seat).classList.add('speaking');
  stopType();
  const box = $('.dlg-text', dlg);
  typeFull = text;
  let i = 0;
  const cps = 26 * P.speed;
  box.innerHTML = '<span class="caret"></span>';
  typeTimer = setInterval(() => {
    i += Math.max(1, Math.round(cps / 30));
    if (i >= typeFull.length) { box.textContent = typeFull; stopType(); return; }
    box.innerHTML = esc(typeFull.slice(0, i)) + '<span class="caret"></span>';
    box.scrollTop = box.scrollHeight;
  }, 1000 / 30);
  return Math.max(2000, (text.length / 26) * 1000 + 1300);
}
function hideDialog() { $('#dialog').classList.add('hidden'); stopType(); $$('.seat.speaking').forEach(x => x.classList.remove('speaking')); }
$('#dialog').addEventListener('click', () => { if (typeTimer) { stopType(); $('.dlg-text').textContent = typeFull; } else { step(); } });

// ---------------------------------------------------------------- 每個事件的動畫，回傳持續時間 (ms, 1× 速度)
function animate(ev) {
  const d = ev.data;
  if (!visible(ev)) return 0;
  switch (ev.type) {
    case 'game_start':
      hideDialog();
      banner(Art.ICON.moon, '月下狼人殺', `${d.board_name} · 種子 ${d.seed}`, 2400);
      return 2400;
    case 'role_assign': {
      const counts = {};
      Object.values(d.roles).forEach(r => (counts[r] = (counts[r] || 0) + 1));
      const s = Object.entries(counts).map(([r, n]) => `${ROLE[r]}×${n}`).join('　');
      dialog({ text: `身分已經秘密發放：${s}。（上帝視角可以看到每個人的身分徽章）`, channel: '主持人' });
      return 2400;
    }
    case 'phase':
      clearLines(); $('#tally').innerHTML = ''; hideDialog();
      if (d.phase === 'night') { banner(Art.ICON.moon, `第 ${d.day} 夜`, '天黑請閉眼', 2400); return 2600; }
      banner(Art.ICON.sun, `第 ${d.day} 天`, '天亮了，請睜眼', 2200); return 2400;
    case 'acting':
      return 0;
    case 'thought': {
      if (SPEECH_KINDS.includes(d.kind)) { S.pendingThought[d.seat] = d.text; return 0; }
      const ms = Math.min(3600, Math.max(1500, d.text.length * 45));
      thoughtCloud(d.seat, d.text, ms);
      return ms;
    }
    case 'fallback': return 0;
    case 'your_role': return 0;
    case 'guard':
      if (!d.target) { stamp(d.seat, '空守', 'good', 1100); return 1200; }
      line(d.seat, d.target, 'guard-line'); fxAt(d.target, Art.ICON.shield, '', 1600, 110);
      later(() => clearLines('guard-line'), 1600);
      return 1700;
    case 'wolf_chat':
      return dialog({ seat: d.seat, channel: '🐺 狼人頻道', text: d.text, thought: take(d.seat), cls: 'wolf' });
    case 'wolf_vote':
      line(d.seat, d.target, 'wolf-line', 'arrowRed');
      return 500;
    case 'wolf_kill':
      hideDialog();
      if (!d.target) return 600;
      $('#stage').classList.add('blood');
      later(() => $('#stage').classList.remove('blood'), 2200);
      fxAt(d.target, Art.ICON.claw, 'claw', 1700, 120); shake(d.target);
      later(() => clearLines('wolf-line'), 1200);
      return 2000;
    case 'seer_check':
      line(d.seat, d.target, 'beam', 'arrowPurple');
      fxAt(d.seat, Art.ICON.eye, '', 1500, 54, -70);
      later(() => stamp(d.target, d.result === 'wolf' ? '狼人' : '好人', d.result === 'wolf' ? 'wolf' : 'good', 1500), 600);
      later(() => clearLines('beam'), 2000);
      return 2300;
    case 'witch_info': return 0;
    case 'witch':
      if (d.save) { fxAt(d.save, Art.ICON.potionG, '', 1600, 80); later(() => stamp(d.save, '解藥', 'good', 1200), 400); return 1900; }
      if (d.poison) { line(d.seat, d.poison, 'kill-line'); fxAt(d.poison, Art.ICON.potionP, '', 1600, 80); later(() => stamp(d.poison, '毒藥', 'wolf', 1200), 400); later(() => clearLines('kill-line'), 1600); return 1900; }
      fxAt(d.seat, Art.ICON.potionG, '', 900, 44, -70); return 1000;
    case 'night_result':
      if (!d.deaths.length) { banner(Art.ICON.sun, '平安夜', '昨晚沒有人死亡', 2400); return 2500; }
      banner(Art.ICON.tomb, `昨晚 ${d.deaths.map(s => s + '號').join('、')} 死亡`, d.deaths.map(s => S.players[s].name).join('、') + ' 倒在了月光下', 2600, true);
      return 2700;
    case 'death':
      shake(d.seat);
      return 900;
    case 'death_detail':
      if (P.god) stamp(d.seat, ROLE[d.role], d.role === 'werewolf' ? 'wolf' : 'good', 1100);
      return 1100;
    case 'last_words':
      return dialog({ seat: d.seat, channel: '🕯 遺言', text: d.text, thought: take(d.seat), cls: 'lastwords' });
    case 'hunter_shoot':
      if (!d.target) { stamp(d.seat, '不開槍', 'exile', 1400); return 1500; }
      line(d.seat, d.target, 'shot');
      later(() => { stamp(d.target, '砰！', 'bang', 1300); shake(d.target); }, 250);
      later(() => clearLines('shot'), 1500);
      return 1900;
    case 'speech_order':
      dialog({ text: `請依序發言：${d.order.join(' → ')}`, channel: '主持人' });
      return 1500;
    case 'speech':
      return dialog({ seat: d.seat, channel: d.pk ? '⚔ PK 發言' : '☀ 白天發言', text: d.text, thought: take(d.seat), cls: '' });
    case 'vote':
      if ($('#dialog').classList.contains('hidden') === false && !$('#dialog').classList.contains('system')) hideDialog();
      if (d.target) line(d.seat, d.target, 'vote-line', 'arrowGold');
      else stamp(d.seat, '棄票', 'exile', 700);
      return 420;
    case 'vote_result': {
      const entries = Object.entries(d.tally).sort((a, b) => b[1] - a[1]);
      const max = entries.length ? entries[0][1] : 0;
      $('#tally').innerHTML = entries.map(([s, c]) => `<div class="bar ${c === max ? 'max' : ''}">${s}號 ${esc(S.players[s].name)}<b>${c}</b></div>`).join('');
      if (d.exiled) { later(() => { stamp(d.exiled, '放逐', 'exile', 1700); shake(d.exiled); }, 500); }
      dialog({ text: ev.text, channel: '⚖ 投票結果' });
      return 3000;
    }
    case 'pk_start':
      clearLines(); $('#tally').innerHTML = '';
      banner(Art.ICON.gavel, 'P K', d.candidates.map(s => s + '號').join(' vs ') + ' 平票，上台辯論', 2200, true);
      return 2300;
    case 'no_exile':
      dialog({ text: d.reason, channel: '⚖ 投票結果' });
      return 1800;
    case 'postgame_start':
      hideDialog(); clearLines();
      banner(Art.ICON.moon, '身分公開', '賽後復盤 · 說說這局的關鍵', 2600);
      return 2700;
    case 'postgame':
      return dialog({ seat: d.seat, channel: `◇ 賽後復盤 · ${ROLE[d.role]}`, text: d.text, thought: take(d.seat), cls: 'postgame' });
    case 'game_over':
      hideDialog(); clearLines(); $('#tally').innerHTML = '';
      showGameOver(d);
      return 0;
  }
  return 0;
}
function take(seat) { const t = S.pendingThought[seat]; delete S.pendingThought[seat]; return t; }

// ---------------------------------------------------------------- 編年史
function chrAdd(ev) {
  if (ev.type === 'acting' || ev.type === 'your_role' || ev.type === 'witch_info') return;
  if (!visible(ev)) return;
  const el = document.createElement('div');
  let cls = 'e';
  if (ev.vis !== 'all') cls += ' god';
  if (['wolf_chat', 'wolf_vote', 'wolf_kill'].includes(ev.type)) cls += ' wolf';
  if (ev.type === 'thought') cls += ' thought';
  if (ev.type === 'phase') cls += ' phase';
  if (ev.type === 'fallback') cls += ' warn';
  if (ev.type === 'game_over') cls += ' end';
  el.className = cls;
  el.dataset.i = ev.i;
  el.textContent = (ev.vis !== 'all' && ev.type !== 'thought' ? '👁 ' : '') + ev.text;
  el.onclick = () => seek(ev.i);
  const list = $('#chr-list');
  const stick = list.scrollTop + list.clientHeight >= list.scrollHeight - 30;
  list.appendChild(el);
  $$('.e.cur', list).forEach(x => x.classList.remove('cur'));
  el.classList.add('cur');
  if (stick) list.scrollTop = list.scrollHeight;
}

// ---------------------------------------------------------------- 播放控制
function tick() {
  clearTimeout(P.timer);
  if (!P.playing) return;
  if (P.cursor >= P.events.length) { waiting(); P.timer = setTimeout(tick, 300); return; }
  const dur = processNext();
  P.timer = setTimeout(tick, dur / P.speed);
}
function processNext() {
  const ev = P.events[P.cursor++];
  apply(ev);
  chrAdd(ev);
  const dur = animate(ev);
  renderSeats();
  status('');
  if (ev.type === 'game_over') { P.playing = false; updatePlayBtn(); }
  return dur;
}
function step() {
  P.playing = false; updatePlayBtn(); clearTimeout(P.timer);
  $$('.thought-cloud.await-click').forEach(x => x.remove());
  while (P.cursor < P.events.length) {
    const ev = P.events[P.cursor];
    const d = processNext();
    if (d > 0 || ev.type === 'game_over') break;
  }
}
function waiting() {
  if (P.done) { status(S.over ? '' : '回放結束'); return; }
  const last = P.events[P.events.length - 1];
  if (last && last.type === 'acting' && (P.god || S.phase === 'day')) {
    status(`⏳ ${pname(last.data.seat)} 正在思考（${KIND_NAME[last.data.kind] || last.data.kind}）…`);
    S.acting = last.data.seat; renderSeats();
  } else status('⏳ 等待 AI 回應…');
}
function status(t) { $('#status').textContent = t; }
function seek(i) {
  clearTimeout(P.timer); clearFx(); hideDialog();
  $('#gameover').classList.add('hidden');
  S = freshState();
  $('#chr-list').innerHTML = '';
  for (let k = 0; k < i && k < P.events.length; k++) { apply(P.events[k]); chrAdd(P.events[k]); }
  P.cursor = Math.min(i, P.events.length);
  renderSeats();
  if (P.playing) tick();
}
function setPlaying(v) {
  P.playing = v;
  updatePlayBtn();
  if (v) { $$('.thought-cloud.await-click').forEach(x => x.remove()); tick(); }
  else clearTimeout(P.timer);
}
function updatePlayBtn() {
  $('#btn-play').textContent = P.playing ? '⏸' : '▶';
  $('#stage').classList.toggle('manual', !P.playing);
}

$('#btn-play').onclick = () => setPlaying(!P.playing);
$('#btn-step').onclick = step;
$('#btn-restart').onclick = () => { P.playing = false; updatePlayBtn(); seek(0); status('點擊畫面前進下一步'); };
$$('.speed button').forEach(b => b.onclick = () => { P.speed = +b.dataset.speed; $$('.speed button').forEach(x => x.classList.toggle('on', x === b)); });
$('#god').onchange = e => { P.god = e.target.checked; seek(P.cursor); };
$('#btn-log').onclick = () => $('#chronicle').classList.toggle('hidden');
$('#chr-close').onclick = () => $('#chronicle').classList.add('hidden');
$('#btn-lobby').onclick = () => { setPlaying(false); openLobby(); };
$('#stage').addEventListener('click', e => {
  if (!$('#lobby').classList.contains('hidden') || !$('#gameover').classList.contains('hidden')) return;
  if (e.target.closest('button,input,select,label,a,#dialog,#chronicle')) return;
  step();
});
addEventListener('keydown', e => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  if (e.code === 'Space') { e.preventDefault(); setPlaying(!P.playing); }
  if (e.code === 'ArrowRight') step();
  if (e.key === 'l') $('#chronicle').classList.toggle('hidden');
  if (e.key === 'g') { $('#god').checked = !$('#god').checked; $('#god').onchange({ target: $('#god') }); }
});

// ---------------------------------------------------------------- 結算畫面
function showGameOver(d) {
  const go = $('#gameover');
  const title = { wolf: '狼人陣營勝利', village: '好人陣營勝利' }[d.winner] || '遊戲結束';
  go.className = d.winner === 'wolf' ? 'wolf' : '';
  const roles = norm(d.roles);
  go.innerHTML = `<h2>${title}</h2><div class="reason">${esc(d.reason)} · 共 ${S.day} 天</div>
    <div class="go-grid">${Object.values(S.players).map(p => {
      const r = roles[p.seat];
      const win = d.winner && TEAM(r) === d.winner;
      return `<div class="go-card ${win ? 'win' : ''} ${p.alive ? '' : 'dead'}"><div class="mini">${Art.avatar(p.name)}</div><div class="em">${Art.emblem(r, 34)}</div>
        <b>${p.seat}號 ${esc(p.name)}</b><div class="rn" style="color:${Art.ROLE_COLORS[r]}">${ROLE[r]}${win ? ' 🏆' : ''}</div>
        <small>${esc(p.skill)}</small><small>${esc(modelLabel(p.model))}</small><small>${p.alive ? '存活' : '☠ 出局'}</small></div>`;
    }).join('')}</div>
    <div class="go-actions">
      ${P.lastStart ? '<button class="gold" id="go-again">⚔ 再來一局</button>' : ''}
      <button id="go-replay">⏮ 重看這局</button><button id="go-close">👀 看看戰場</button><button id="go-lobby">🏠 回大廳</button></div>`;
  if ($('#go-again')) $('#go-again').onclick = () => startGame(P.lastStart);
  $('#go-replay').onclick = () => { go.classList.add('hidden'); P.playing = false; updatePlayBtn(); seek(0); status('點擊畫面前進下一步'); };
  $('#go-close').onclick = () => go.classList.add('hidden');
  $('#go-lobby').onclick = () => { go.classList.add('hidden'); openLobby(); };
}

// ---------------------------------------------------------------- 大廳
async function api(url, opt) {
  const r = await fetch(url, opt);
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || r.statusText);
  return j;
}
function openLobby() { $('#lobby').classList.remove('hidden'); refreshReplays(); }

async function loadSetup() {
  const previousBoard = SETUP && $('#board') ? $('#board').value : null;
  try {
    SETUP = await api('/api/setup');
  } catch (e) {
    $('#lobby-err').textContent = '⚠ 連不到本機伺服器。請在專案資料夾執行：python run.py\n（現在仍可以用右邊「載入回放檔」觀看回放）';
    return;
  }
  $('#key-status').innerHTML = SETUP.openai_key
    ? '<span class="ok">✅ 已讀到 OpenAI API 金鑰，可以使用 GPT 模型</span>'
    : `<span class="bad">⚠ 沒有讀到 OpenAI API 金鑰。請設定環境變數 <code>${esc(SETUP.key_env)}</code> 或在專案資料夾放 <code>.env</code>，然後重新啟動 run.py。在那之前只能選「規則 AI」。</span>`;
  const bs = $('#board');
  bs.innerHTML = Object.entries(SETUP.boards).map(([k, b]) => `<option value="${k}">${b.name}</option>`).join('');
  bs.value = previousBoard && SETUP.boards[previousBoard] ? previousBoard : SETUP.board;
  bs.onchange = renderSeatTable;
  const am = $('#all-model');
  am.innerHTML = '<option value="">（選擇模型）</option>' + SETUP.models.map(m => `<option value="${m.id}">${esc(m.label)}</option>`).join('');
  am.onchange = () => { if (am.value) $$('.seat-row .m').forEach(s => (s.value = am.value)); am.value = ''; };
  $('#skill-list').innerHTML = SETUP.skills.map(s => `<div class="skill"><b>${esc(s.name)}</b><span class="id">skills/${esc(s.id)}</span>
      ${s.has_code ? '<span class="chip code">strategy.py</span>' : ''}${s.roles.map(r => `<span class="chip">${r === 'village' ? '好人' : ROLE[r] || r}</span>`).join('')}
      <p>${esc(s.description)}${s.author ? ` — ${esc(s.author)}` : ''}</p></div>`).join('') || '<p>skills/ 資料夾裡還沒有 skill</p>';
  renderSeatTable();
  refreshReplays();
}
function renderSeatTable() {
  const n = SETUP.boards[$('#board').value].roles.length;
  const old = $$('.seat-row').map(r => ({ name: $('.nm', r).value, skill: $('.sk', r).value, model: $('.m', r).value }));
  const src = old.length ? old : SETUP.players;
  const rows = [];
  for (let i = 0; i < n; i++) {
    const p = src[i] || SETUP.players[i] || { name: `玩家${i + 1}`, skill: 'baseline', model: 'rule' };
    rows.push(`<div class="seat-row"><div class="n">${i + 1}</div><div class="mini">${Art.avatar(p.name)}</div>
      <input class="nm" value="${esc(p.name)}" maxlength="10">
      <select class="sk">${SETUP.skills.map(s => `<option value="${s.id}" ${s.id === p.skill ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select>
      <select class="m">${SETUP.models.map(m => `<option value="${m.id}" ${m.id === p.model ? 'selected' : ''}>${esc(m.label)}</option>`).join('')}</select>
      <button type="button" class="seat-skill-import" title="匯入 Skill 並套用到 ${i + 1} 號玩家">＋ Skill</button></div>`);
  }
  $('#seat-table').innerHTML = rows.join('');
  $$('.seat-row .nm').forEach(inp => inp.oninput = () => { inp.parentElement.querySelector('.mini').innerHTML = Art.avatar(inp.value); });
  $$('.seat-row .seat-skill-import').forEach((button, i) => button.onclick = () => {
    seatSkillImportTarget = i;
    $('#seat-skill-file').click();
  });
}
$('#btn-shuffle').onclick = () => {
  const rows = $$('.seat-row').map(r => ({ name: $('.nm', r).value, skill: $('.sk', r).value, model: $('.m', r).value }));
  for (let i = rows.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [rows[i], rows[j]] = [rows[j], rows[i]]; }
  $$('.seat-row').forEach((r, i) => { $('.nm', r).value = rows[i].name; $('.sk', r).value = rows[i].skill; $('.m', r).value = rows[i].model; $('.mini', r).innerHTML = Art.avatar(rows[i].name); });
};
$('#btn-start').onclick = () => {
  const body = {
    board: $('#board').value, seed: $('#seed').value.trim() || null,
    players: $$('.seat-row').map(r => ({ name: $('.nm', r).value.trim() || '無名', skill: $('.sk', r).value, model: $('.m', r).value })),
  };
  startGame(body);
};
async function startGame(body) {
  $('#lobby-err').textContent = '';
  if (P.live && !P.done) fetch('/api/stop/' + P.live, { method: 'POST' }).catch(() => {});
  try {
    const j = await api('/api/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    P.lastStart = body;
    resetPlayer([], false);
    P.live = j.game_id;
    $('#lobby').classList.add('hidden');
    $('#gameover').classList.add('hidden');
    poll(j.game_id);
  } catch (e) { $('#lobby-err').textContent = '⚠ ' + e.message; }
}
async function poll(id) {
  if (P.live !== id) return;
  try {
    const j = await api(`/api/events/${id}?since=${P.events.length}`);
    P.events.push(...j.events);
    P.done = j.done;
    if (j.error) status('⚠ 遊戲發生錯誤：' + j.error);
    if (!j.done) setTimeout(() => poll(id), 600);
  } catch (e) { status('⚠ ' + e.message); setTimeout(() => poll(id), 1500); }
}
function resetPlayer(events, done) {
  clearTimeout(P.timer); clearFx(); hideDialog();
  P.events = events; P.cursor = 0; P.done = done; P.live = null; P.playing = false; updatePlayBtn();
  S = freshState(); $('#chr-list').innerHTML = ''; $('#seats').innerHTML = '';
  renderSeats(); status('點擊畫面前進下一步');
}
async function refreshReplays() {
  try {
    const items = await api('/api/replays');
    $('#replay-list').innerHTML = items.map(it => `<div data-f="${esc(it.file)}">🎞 ${esc(it.file)}</div>`).join('') || '<small>還沒有回放。每場對局結束都會自動存到 replays/</small>';
    $$('#replay-list div[data-f]').forEach(d => d.onclick = async () => { const j = await api('/api/replays/' + encodeURIComponent(d.dataset.f)); loadReplay(j); });
  } catch (e) { /* 離線 */ }
}
$('#replay-file').onchange = e => {
  const f = e.target.files[0];
  if (!f) return;
  f.text().then(t => loadReplay(JSON.parse(t)));
};
async function importSkill(input, targetIndex = null) {
  const f = input.files[0];
  if (!f) return;
  const out = $('#skill-import-status');
  if (!confirm('外部 Skill 可能包含會在本機執行的 strategy.py。確定信任這個檔案並匯入嗎？')) {
    input.value = '';
    return;
  }
  out.textContent = '⏳ 正在驗證並匯入…';
  try {
    const j = await api('/api/skills/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip', 'X-Skill-Filename': encodeURIComponent(f.name) },
      body: f,
    });
    out.textContent = `✅ 已匯入 skills/${j.skill_id}`;
    await loadSetup();
    if (targetIndex !== null) {
      const row = $$('.seat-row')[targetIndex];
      if (row) $('.sk', row).value = j.skill_id;
      out.textContent = `✅ 已匯入 skills/${j.skill_id}，並套用到 ${targetIndex + 1} 號玩家`;
    } else {
      out.textContent = `✅ 已匯入 skills/${j.skill_id}，現在可套用到玩家`;
    }
  } catch (err) {
    out.textContent = '⚠ ' + err.message;
  } finally {
    input.value = '';
  }
}
$('#skill-file').onchange = e => importSkill(e.target);
$('#seat-skill-file').onchange = e => {
  const target = seatSkillImportTarget;
  seatSkillImportTarget = null;
  importSkill(e.target, target);
};
function loadReplay(j) {
  $('#lobby').classList.add('hidden'); $('#gameover').classList.add('hidden');
  P.lastStart = j.meta && j.meta.players ? { board: j.board, players: j.meta.players, seed: null } : null;
  resetPlayer(j.events, true);
}

// ---------------------------------------------------------------- 啟動
$('#scenery-wrap').innerHTML = Art.scenery();
$('#stars').innerHTML = Art.stars();
fit();
renderPhase();
updatePlayBtn();
loadSetup();
// 網址帶 ?replay=檔名 可直接播放
const qp = new URLSearchParams(location.search);
if (qp.get('replay')) api('/api/replays/' + encodeURIComponent(qp.get('replay'))).then(loadReplay).catch(() => {});
if (qp.get('speed')) P.speed = +qp.get('speed');

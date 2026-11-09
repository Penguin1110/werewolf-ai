// ============================================================================
//  美術資源：全部用程式產生的 SVG，不需要任何外部圖片
// ============================================================================
const Art = (() => {
  function rng(seed) {
    let h = 2166136261 >>> 0;
    const s = String(seed);
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return () => { h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  const pick = (r, arr) => arr[Math.floor(r() * arr.length)];

  const SKIN = ['#f6d7b8', '#efc39e', '#e0a982', '#c98c62', '#a8714c', '#f3cfae'];
  const HAIR = ['#2b1d16', '#4a2f1f', '#7a4b2a', '#b5783b', '#e0b35a', '#d9d4cc', '#5b2a4a', '#2d3b55', '#8e2f22'];
  const CLOAK = ['#6b2d2d', '#2f4f6b', '#3d5a3a', '#5a3f6e', '#7a5a2a', '#2f5d5a', '#6e3b54', '#44506b', '#7a3e1f'];
  const BG = ['#3a2a4f', '#24384f', '#3b2f2a', '#2b4237', '#4a2d36', '#2f3550'];

  // 每位玩家的原創角色立繪
  function legacyAvatar(seed) {
    const r = rng(seed);
    const skin = pick(r, SKIN), hair = pick(r, HAIR), cloak = pick(r, CLOAK), bg = pick(r, BG);
    const style = Math.floor(r() * 7);
    const glasses = r() < 0.15, beard = r() < 0.18, blush = r() < 0.6, scar = r() < 0.1;
    const eyeY = 50 + r() * 2, eyeGap = 7.5 + r() * 1.5;
    const brow = r() < 0.5 ? 0 : (r() < 0.5 ? -1.5 : 1.5);
    const id = 'a' + Math.floor(r() * 1e9);
    let back = '', front = '', hat = '';
    if (style === 0) { // 短髮
      front = `<path d="M29 46 Q28 24 50 23 Q72 24 71 46 Q66 34 50 33 Q38 33 29 46Z" fill="${hair}"/>`;
    } else if (style === 1) { // 長髮
      back = `<path d="M27 46 Q26 22 50 21 Q74 22 73 46 L76 82 Q50 90 24 82Z" fill="${hair}"/>`;
      front = `<path d="M29 46 Q30 25 50 24 Q70 25 71 46 Q62 33 52 36 Q44 30 29 46Z" fill="${hair}"/>`;
    } else if (style === 2) { // 包頭
      back = `<circle cx="50" cy="19" r="9" fill="${hair}"/>`;
      front = `<path d="M29 47 Q28 25 50 24 Q72 25 71 47 Q64 31 50 31 Q36 31 29 47Z" fill="${hair}"/>`;
    } else if (style === 3) { // 兜帽
      back = `<path d="M22 60 Q20 18 50 15 Q80 18 78 60 L80 80 L20 80Z" fill="${cloak}" filter="brightness(.8)"/>`;
      front = `<path d="M30 44 Q34 30 50 30 Q66 30 70 44 Q60 36 50 37 Q40 36 30 44Z" fill="${hair}"/>
               <path d="M24 58 Q24 22 50 20 Q76 22 76 58 Q72 30 50 28 Q28 30 24 58Z" fill="${cloak}"/>`;
    } else if (style === 4) { // 寬帽
      front = `<path d="M30 46 Q29 28 50 27 Q71 28 70 46 Q63 36 50 36 Q37 36 30 46Z" fill="${hair}"/>`;
      hat = `<ellipse cx="50" cy="30" rx="31" ry="6" fill="#2a2320"/><path d="M36 30 Q36 12 50 12 Q64 12 64 30Z" fill="#2a2320"/>
             <rect x="36" y="25" width="28" height="4" fill="${cloak}"/>`;
    } else if (style === 5) { // 刺蝟頭
      front = `<path d="M28 46 L30 30 L35 34 L37 22 L43 30 L48 18 L53 29 L59 20 L62 31 L68 26 L70 34 L72 46 Q64 35 50 35 Q36 35 28 46Z" fill="${hair}"/>`;
    } else { // 側分 + 髮帶
      back = `<path d="M28 50 Q26 24 50 22 Q74 24 72 50 L72 64 L28 64Z" fill="${hair}"/>`;
      front = `<path d="M29 47 Q30 24 52 23 Q72 25 71 44 Q56 40 46 28 Q40 40 29 47Z" fill="${hair}"/>
               <path d="M29 38 Q50 30 71 38" stroke="${pick(r, ['#c8a24a', '#b33', '#3a7', '#46c'])}" stroke-width="3" fill="none"/>`;
    }
    const mouth = pick(r, [
      `<path d="M45 64 Q50 67 55 64" stroke="#6b3b2b" stroke-width="1.6" fill="none" stroke-linecap="round"/>`,
      `<path d="M46 65 L54 65" stroke="#6b3b2b" stroke-width="1.6" stroke-linecap="round"/>`,
      `<path d="M45 63 Q50 69 55 63 Z" fill="#7a3328"/>`,
      `<path d="M46 66 Q50 63 54 66" stroke="#6b3b2b" stroke-width="1.6" fill="none" stroke-linecap="round"/>`,
    ]);
    return `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" class="avatar">
      <defs><radialGradient id="${id}bg" cx="50%" cy="40%" r="70%"><stop offset="0" stop-color="${bg}" stop-opacity="1"/><stop offset="1" stop-color="#0d0b14"/></radialGradient></defs>
      <rect width="100" height="100" fill="url(#${id}bg)"/>
      ${back}
      <path d="M8 104 Q12 74 50 70 Q88 74 92 104Z" fill="${cloak}"/>
      <path d="M38 72 L50 86 L62 72" fill="none" stroke="#d9b26a" stroke-width="2"/>
      <rect x="44" y="62" width="12" height="12" fill="${skin}" filter="brightness(.9)"/>
      <ellipse cx="50" cy="50" rx="20" ry="22" fill="${skin}"/>
      <ellipse cx="30" cy="52" rx="3" ry="5" fill="${skin}"/><ellipse cx="70" cy="52" rx="3" ry="5" fill="${skin}"/>
      ${front}
      <g class="eyes">
        <path d="M${50 - eyeGap - 4} ${eyeY - 6 + brow} L${50 - eyeGap + 4} ${eyeY - 6 - brow}" stroke="${hair}" stroke-width="2" stroke-linecap="round"/>
        <path d="M${50 + eyeGap - 4} ${eyeY - 6 - brow} L${50 + eyeGap + 4} ${eyeY - 6 + brow}" stroke="${hair}" stroke-width="2" stroke-linecap="round"/>
        <ellipse cx="${50 - eyeGap}" cy="${eyeY}" rx="2.6" ry="3.2" fill="#1d1414"/>
        <ellipse cx="${50 + eyeGap}" cy="${eyeY}" rx="2.6" ry="3.2" fill="#1d1414"/>
        <circle cx="${50 - eyeGap + 1}" cy="${eyeY - 1.2}" r=".9" fill="#fff"/><circle cx="${50 + eyeGap + 1}" cy="${eyeY - 1.2}" r=".9" fill="#fff"/>
      </g>
      <g class="wolf-eyes">
        <ellipse cx="${50 - eyeGap}" cy="${eyeY}" rx="3.4" ry="2.2" fill="#ff3b2f"/>
        <ellipse cx="${50 + eyeGap}" cy="${eyeY}" rx="3.4" ry="2.2" fill="#ff3b2f"/>
        <ellipse cx="${50 - eyeGap}" cy="${eyeY}" rx=".9" ry="2" fill="#2a0000"/><ellipse cx="${50 + eyeGap}" cy="${eyeY}" rx=".9" ry="2" fill="#2a0000"/>
      </g>
      ${blush ? `<ellipse cx="${50 - 12}" cy="58" rx="3.5" ry="2" fill="#e88a7a" opacity=".45"/><ellipse cx="${50 + 12}" cy="58" rx="3.5" ry="2" fill="#e88a7a" opacity=".45"/>` : ''}
      <path d="M50 52 Q48 58 51 59" stroke="#00000033" stroke-width="1.4" fill="none"/>
      ${mouth}
      ${beard ? `<path d="M34 58 Q36 76 50 78 Q64 76 66 58 Q60 68 50 68 Q40 68 34 58Z" fill="${hair}"/>` : ''}
      ${glasses ? `<g fill="none" stroke="#c9b27a" stroke-width="1.4"><circle cx="${50 - eyeGap}" cy="${eyeY}" r="5.5"/><circle cx="${50 + eyeGap}" cy="${eyeY}" r="5.5"/><path d="M${50 - eyeGap + 5.5} ${eyeY} L${50 + eyeGap - 5.5} ${eyeY}"/></g>` : ''}
      ${scar ? `<path d="M60 40 L66 54" stroke="#9b4a3a" stroke-width="1.5"/>` : ''}
      ${hat}
    </svg>`;
  }

  // 玩家肖像：低飽和版畫風，避免 Q 版頭像破壞暗黑桌遊氣氛
  function avatar(seed) {
    const r = rng(seed);
    const id = 'p' + Math.floor(r() * 1e9);
    const skin = pick(r, ['#c8a88d', '#b99173', '#977156', '#d0b39a', '#80604b']);
    const light = pick(r, ['#b8a47b', '#89939a', '#8b766c', '#78877d', '#96829b']);
    const cloth = pick(r, ['#273039', '#34302d', '#29352f', '#382c33', '#2d2a3a']);
    const hair = pick(r, ['#171616', '#2a211d', '#46372d', '#5a493c', '#8a8175']);
    const bg = pick(r, ['#20262c', '#292421', '#202925', '#29222a', '#22232c']);
    const style = Math.floor(r() * 6);
    const scar = r() < .18;
    const beard = r() < .28;
    const eyeGap = 8 + r() * 1.5;
    let back = '', front = '', accessory = '';

    if (style === 0) {
      front = `<path d="M32 42 Q31 20 50 18 Q69 20 68 42 Q60 31 51 30 Q42 36 32 42Z" fill="${hair}"/>`;
    } else if (style === 1) {
      back = `<path d="M28 39 Q27 16 50 15 Q73 17 72 41 L75 78 L62 72 L59 35 L40 35 L37 73 L25 80Z" fill="${hair}"/>`;
      front = `<path d="M31 41 Q30 20 50 18 Q70 20 69 41 Q59 28 49 29 Q40 32 31 41Z" fill="${hair}"/>`;
    } else if (style === 2) {
      back = `<path d="M22 62 Q20 14 50 11 Q80 14 78 62 L82 90 L18 90Z" fill="${cloth}"/>`;
      front = `<path d="M25 55 Q25 18 50 15 Q75 18 75 55 Q68 29 50 27 Q32 29 25 55Z" fill="${cloth}"/><path d="M34 40 Q37 26 51 25 Q65 28 67 41 Q57 31 48 32 Q41 36 34 40Z" fill="${hair}"/>`;
    } else if (style === 3) {
      front = `<path d="M31 42 Q30 21 50 19 Q70 21 69 42 Q61 29 50 29 Q39 30 31 42Z" fill="${hair}"/><path d="M31 30 Q50 24 69 31" fill="none" stroke="${light}" stroke-width="2"/>`;
      accessory = `<path d="M66 36 Q78 43 72 61" fill="none" stroke="${light}" stroke-width="2"/><circle cx="72" cy="62" r="2" fill="${light}"/>`;
    } else if (style === 4) {
      front = `<path d="M31 42 Q31 23 49 21 Q67 22 69 42 Q58 33 48 28 Q43 37 31 42Z" fill="${hair}"/>`;
      accessory = `<path d="M20 29 Q50 20 80 29" stroke="#151515" stroke-width="7"/><path d="M35 26 Q36 8 50 8 Q64 8 66 26Z" fill="#171718"/><path d="M36 23 L65 23" stroke="${light}" stroke-width="2"/>`;
    } else {
      back = `<path d="M27 38 Q29 15 50 14 Q71 16 73 39 L69 70 L62 67 L60 32 L39 32 L37 68 L29 72Z" fill="${hair}"/>`;
      front = `<path d="M31 40 Q32 20 52 18 Q69 21 69 39 Q55 36 46 25 Q41 35 31 40Z" fill="${hair}"/>`;
    }

    return `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" class="avatar portrait-art">
      <defs>
        <radialGradient id="${id}bg" cx="42%" cy="32%" r="78%"><stop offset="0" stop-color="${bg}"/><stop offset="1" stop-color="#08090b"/></radialGradient>
        <linearGradient id="${id}coat" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${light}" stop-opacity=".52"/><stop offset=".42" stop-color="${cloth}"/><stop offset="1" stop-color="#111317"/></linearGradient>
        <linearGradient id="${id}face" x1="0" y1="0" x2="1" y2=".4"><stop stop-color="${skin}"/><stop offset=".58" stop-color="${skin}"/><stop offset="1" stop-color="#3a2b25"/></linearGradient>
        <pattern id="${id}hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(18)"><line x1="0" y1="0" x2="0" y2="5" stroke="#fff" stroke-opacity=".035" stroke-width="1"/></pattern>
      </defs>
      <rect width="100" height="100" fill="url(#${id}bg)"/>
      <circle cx="50" cy="48" r="42" fill="none" stroke="${light}" stroke-opacity=".13"/>
      ${back}
      <path d="M8 103 Q12 76 37 71 L50 85 L63 71 Q88 76 92 103Z" fill="url(#${id}coat)"/>
      <path d="M42 66 L40 75 L50 86 L60 75 L58 65Z" fill="${skin}" opacity=".82"/>
      <path d="M34 39 Q34 20 50 19 Q66 21 66 40 L63 57 Q60 69 50 74 Q40 69 37 57Z" fill="url(#${id}face)"/>
      <path d="M35 40 Q30 40 33 52 L37 54 M65 40 Q70 40 67 52 L63 54" fill="${skin}" stroke="#49362d" stroke-width=".7"/>
      ${front}
      <g class="eyes" stroke="#171719" stroke-linecap="round">
        <path d="M${50 - eyeGap - 5} 43 Q${50 - eyeGap} 40 ${50 - eyeGap + 5} 43" stroke-width="2"/>
        <path d="M${50 + eyeGap - 5} 43 Q${50 + eyeGap} 40 ${50 + eyeGap + 5} 43" stroke-width="2"/>
        <path d="M${50 - eyeGap - 4} 48 Q${50 - eyeGap} 50 ${50 - eyeGap + 4} 48" stroke-width="1.4"/>
        <path d="M${50 + eyeGap - 4} 48 Q${50 + eyeGap} 50 ${50 + eyeGap + 4} 48" stroke-width="1.4"/>
        <circle cx="${50 - eyeGap}" cy="48" r="1.5" fill="#232126" stroke="none"/><circle cx="${50 + eyeGap}" cy="48" r="1.5" fill="#232126" stroke="none"/>
      </g>
      <g class="wolf-eyes"><path d="M${50 - eyeGap - 4} 48 L${50 - eyeGap + 4} 47" stroke="#d23b39" stroke-width="2.6"/><path d="M${50 + eyeGap - 4} 47 L${50 + eyeGap + 4} 48" stroke="#d23b39" stroke-width="2.6"/></g>
      <path d="M50 47 L47 57 L51 59" fill="none" stroke="#5f4437" stroke-width="1.2"/>
      <path d="M44 64 Q50 ${62 + r() * 4} 56 64" fill="none" stroke="#50342f" stroke-width="1.5"/>
      ${beard ? `<path d="M37 57 Q39 73 50 77 Q61 73 63 57 Q58 69 50 70 Q42 69 37 57Z" fill="${hair}" opacity=".78"/>` : ''}
      ${scar ? `<path d="M60 38 L55 56" stroke="#70423b" stroke-width="1.4"/><path d="M57 44 L61 46 M55 50 L59 52" stroke="#70423b" stroke-width=".8"/>` : ''}
      ${accessory}
      <rect width="100" height="100" fill="url(#${id}hatch)"/>
      <path d="M0 0 H100 V100 H0Z" fill="none" stroke="#000" stroke-opacity=".55" stroke-width="7"/>
    </svg>`;
  }

  // 身分徽章
  const ROLE_COLORS = { werewolf: '#b3261e', villager: '#8a6a3a', seer: '#6a3fb5', witch: '#2f8a57', hunter: '#c26a1a', guard: '#2f6fb5' };
  const ROLE_ICON = {
    werewolf: `<path d="M18 46 L14 18 L26 28 Q32 24 38 28 L50 18 L46 46 Q42 54 32 56 Q22 54 18 46Z" fill="#1b0f0f"/>
               <path d="M24 38 L29 36 M40 38 L35 36" stroke="#ff4d3a" stroke-width="3" stroke-linecap="round"/>
               <path d="M28 48 L32 52 L36 48" fill="#fff" />`,
    villager: `<path d="M16 34 L32 20 L48 34 L48 50 L16 50Z" fill="#f2e2bd"/><rect x="28" y="38" width="8" height="12" fill="#6b4a2a"/><path d="M12 36 L32 17 L52 36" stroke="#5b3a1a" stroke-width="4" fill="none" stroke-linejoin="round"/>`,
    seer: `<circle cx="32" cy="29" r="14" fill="#cdb6ff"/><circle cx="32" cy="29" r="14" fill="url(#orb)"/><path d="M20 50 L44 50 L40 43 L24 43Z" fill="#e6c77a"/>
           <path d="M24 29 Q32 21 40 29 Q32 37 24 29Z" fill="#fff"/><circle cx="32" cy="29" r="3" fill="#3a1f6b"/>`,
    witch: `<path d="M26 14 L38 14 L38 24 Q48 30 48 40 Q48 52 32 52 Q16 52 16 40 Q16 30 26 24Z" fill="#e8f5ec"/><path d="M18 38 Q32 34 46 38 Q46 50 32 50 Q18 50 18 38Z" fill="#59e08f"/>
            <rect x="24" y="11" width="16" height="5" rx="2" fill="#a77b3a"/><circle cx="28" cy="43" r="2" fill="#fff"/><circle cx="35" cy="40" r="1.4" fill="#fff"/>`,
    hunter: `<circle cx="32" cy="32" r="16" fill="none" stroke="#ffe2b8" stroke-width="3"/><circle cx="32" cy="32" r="6" fill="none" stroke="#ffe2b8" stroke-width="3"/>
             <path d="M32 10 L32 22 M32 42 L32 54 M10 32 L22 32 M42 32 L54 32" stroke="#ffe2b8" stroke-width="3" stroke-linecap="round"/>`,
    guard: `<path d="M32 12 L50 18 Q50 42 32 54 Q14 42 14 18Z" fill="#dbe8ff"/><path d="M32 18 L44 22 Q44 40 32 48Z" fill="#8fb4f0"/><path d="M26 32 L31 37 L40 27" stroke="#1d3d73" stroke-width="3" fill="none" stroke-linecap="round"/>`,
  };
  function emblem(role, size = 40) {
    const c = ROLE_COLORS[role] || '#555';
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}" class="emblem">
      <defs><radialGradient id="orb" cx="40%" cy="35%" r="60%"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#7b4fd6" stop-opacity=".2"/></radialGradient>
      <radialGradient id="eg${role}" cx="35%" cy="30%" r="80%"><stop offset="0" stop-color="${c}" stop-opacity="1"/><stop offset="1" stop-color="#120c0c"/></radialGradient></defs>
      <circle cx="32" cy="32" r="30" fill="url(#eg${role})" stroke="#e8c77a" stroke-width="3"/>
      ${ROLE_ICON[role] || ''}
    </svg>`;
  }

  // 背景：遠山、森林、村莊
  function scenery() {
    const r = rng('village');
    let trees = '';
    for (let x = -20; x < 1640; x += 18 + r() * 22) {
      const h = 50 + r() * 70, y = 330 + r() * 25;
      trees += `<path d="M${x} ${y} L${x + h * 0.28} ${y - h} L${x + h * 0.56} ${y}Z"/>`;
    }
    let houses = '', windows = '';
    const hx = [140, 230, 330, 1180, 1270, 1380, 1470];
    hx.forEach((x, i) => {
      const w = 60 + r() * 30, h = 45 + r() * 25, y = 360;
      houses += `<rect x="${x}" y="${y - h}" width="${w}" height="${h}"/><path d="M${x - 8} ${y - h} L${x + w / 2} ${y - h - 32} L${x + w + 8} ${y - h}Z"/>`;
      windows += `<rect class="win" x="${x + 12}" y="${y - h + 12}" width="10" height="12"/><rect class="win" x="${x + w - 24}" y="${y - h + 14}" width="10" height="12"/>`;
    });
    // 教堂
    houses += `<rect x="1050" y="250" width="40" height="110"/><path d="M1042 250 L1070 190 L1098 250Z"/><rect x="1068" y="168" width="4" height="26"/><rect x="1061" y="176" width="18" height="4"/>`;
    windows += `<circle class="win" cx="1070" cy="275" r="8"/>`;
    return `<svg id="scenery" viewBox="0 0 1600 900" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="mtnA" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--mtn1)"/><stop offset="1" stop-color="var(--mtn2)"/></linearGradient>
        <radialGradient id="clearing" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="var(--ground1)"/><stop offset=".7" stop-color="var(--ground2)"/><stop offset="1" stop-color="var(--ground3)" stop-opacity="0"/></radialGradient>
      </defs>
      <path d="M0 300 L120 200 L230 260 L380 150 L520 250 L640 190 L760 260 L900 160 L1040 240 L1180 170 L1320 250 L1460 180 L1600 240 L1600 420 L0 420Z" fill="url(#mtnA)" opacity=".75"/>
      <path d="M0 330 Q200 280 400 320 T800 310 T1200 320 T1600 300 L1600 440 L0 440Z" fill="var(--hill)"/>
      <g fill="var(--tree)">${trees}</g>
      <g fill="var(--house)">${houses}</g>
      <g class="windows">${windows}</g>
      <rect x="0" y="360" width="1600" height="540" fill="var(--field)"/>
      <ellipse cx="800" cy="440" rx="760" ry="380" fill="url(#clearing)"/>
    </svg>`;
  }

  function stars(n = 140) {
    const r = rng('stars');
    let s = '';
    for (let i = 0; i < n; i++) {
      const x = r() * 100, y = r() * 38, sz = r() < 0.1 ? 3 : (r() < 0.4 ? 2 : 1);
      s += `<i style="left:${x}%;top:${y}%;width:${sz}px;height:${sz}px;animation-delay:${(r() * 4).toFixed(2)}s"></i>`;
    }
    return s;
  }

  const ICON = {
    claw: `<svg viewBox="0 0 100 100"><g stroke="#ff2a1f" stroke-width="7" stroke-linecap="round" fill="none" filter="drop-shadow(0 0 6px #ff0000)">
      <path class="slash" d="M20 10 Q45 50 30 92"/><path class="slash" d="M45 6 Q70 50 55 96"/><path class="slash" d="M70 10 Q95 50 80 92"/></g></svg>`,
    shield: `<svg viewBox="0 0 64 64"><path d="M32 6 L54 14 Q54 42 32 58 Q10 42 10 14Z" fill="#7fb2ff" fill-opacity=".55" stroke="#dff0ff" stroke-width="3"/></svg>`,
    potionG: `<svg viewBox="0 0 64 64"><path d="M26 8 L38 8 L38 20 Q50 28 50 40 Q50 56 32 56 Q14 56 14 40 Q14 28 26 20Z" fill="#c9ffe0" stroke="#fff" stroke-width="2"/><path d="M16 38 Q32 32 48 38 Q48 54 32 54 Q16 54 16 38Z" fill="#35d07a"/></svg>`,
    potionP: `<svg viewBox="0 0 64 64"><path d="M26 8 L38 8 L38 20 Q50 28 50 40 Q50 56 32 56 Q14 56 14 40 Q14 28 26 20Z" fill="#ead6ff" stroke="#fff" stroke-width="2"/><path d="M16 38 Q32 32 48 38 Q48 54 32 54 Q16 54 16 38Z" fill="#8e3be0"/><circle cx="27" cy="44" r="3" fill="#1b0b2b"/><circle cx="37" cy="44" r="3" fill="#1b0b2b"/></svg>`,
    eye: `<svg viewBox="0 0 64 64"><path d="M4 32 Q32 6 60 32 Q32 58 4 32Z" fill="#e9dcff" stroke="#b18cff" stroke-width="3"/><circle cx="32" cy="32" r="10" fill="#6a3fb5"/><circle cx="32" cy="32" r="4" fill="#120a24"/></svg>`,
    tomb: `<svg viewBox="0 0 64 64"><path d="M14 58 L14 26 Q14 8 32 8 Q50 8 50 26 L50 58Z" fill="#6f6a72" stroke="#2b2830" stroke-width="3"/><path d="M32 18 L32 40 M24 26 L40 26" stroke="#2b2830" stroke-width="4" stroke-linecap="round"/><rect x="8" y="56" width="48" height="6" rx="2" fill="#3c4a2c"/></svg>`,
    moon: `<svg viewBox="0 0 64 64"><path d="M40 6 A26 26 0 1 0 58 44 A20 20 0 1 1 40 6Z" fill="#ffe9a8"/></svg>`,
    sun: `<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="13" fill="#ffd36a"/><g stroke="#ffd36a" stroke-width="4" stroke-linecap="round"><path d="M32 4v8M32 52v8M4 32h8M52 32h8M12 12l6 6M46 46l6 6M12 52l6-6M46 18l6-6"/></g></svg>`,
    gavel: `<svg viewBox="0 0 64 64"><rect x="10" y="14" width="26" height="14" rx="3" transform="rotate(-35 23 21)" fill="#c58b4a" stroke="#4a2c12" stroke-width="2"/><path d="M28 30 L52 54" stroke="#7a4b22" stroke-width="6" stroke-linecap="round"/><rect x="6" y="54" width="30" height="6" rx="2" fill="#4a2c12"/></svg>`,
  };

  return { avatar, emblem, scenery, stars, ICON, ROLE_COLORS };
})();

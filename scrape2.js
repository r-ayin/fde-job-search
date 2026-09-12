(() => {
  const anchors = [...document.querySelectorAll('a[href*="job_detail"]')];
  const seen = new Set();
  const cards = [];
  for (const a of anchors) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/job_detail\/([^.?]+)/);
    if (!m) continue;
    const eid = m[1];
    if (seen.has(eid)) continue;
    seen.add(eid);
    // 向上找卡片容器
    let card = a;
    for (let i = 0; i < 6 && card.parentElement; i++) {
      card = card.parentElement;
      const t = card.innerText || '';
      if (t.length > 40 && t.indexOf('K') >= 0) break;
    }
    const txt = (card.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    cards.push({
      eid,
      href,
      lines: txt.slice(0, 14),
      raw: txt.slice(0, 14).join(' | ')
    });
  }
  return JSON.stringify({ count: cards.length, cards }).slice(0, 20000);
})()

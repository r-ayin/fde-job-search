(async () => {
  const scroller = document.querySelector('.user-list-content');
  if (!scroller) return JSON.stringify({ err: 'NO_SCROLLER' });
  const seen = {};
  const step = Math.max(150, scroller.clientHeight - 80);
  for (let pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
    scroller.scrollTop = pos;
    await new Promise(r => setTimeout(r, 350));
    for (const w of document.querySelectorAll('.friend-content-warp')) {
      const t = (w.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
      if (!t.length) continue;
      const key = t.slice(0, 2).join('|');
      if (!seen[key]) seen[key] = { header: t.slice(0, 3).join(' / '), tail: t[t.length - 1].slice(-80) };
    }
  }
  scroller.scrollTop = 0;
  await new Promise(r => setTimeout(r, 300));
  return JSON.stringify(Object.entries(seen).map(([k, v]) => ({ key: k, header: v.header, tail: v.tail })));
})()

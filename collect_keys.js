(async () => {
  const scroller = document.querySelector('.user-list-content');
  if (!scroller) return JSON.stringify(['NO_SCROLLER']);
  const seen = {};
  const step = Math.max(150, scroller.clientHeight - 80);
  const total = scroller.scrollHeight;
  for (let pos = 0; pos <= total + step; pos += step) {
    scroller.scrollTop = pos;
    await new Promise(r => setTimeout(r, 320));
    for (const w of document.querySelectorAll('.friend-content-warp')) {
      const t = (w.innerText || '').split('\n').filter(Boolean);
      if (t.length) seen[t.slice(0, 2).join('|')] = 1;
    }
  }
  scroller.scrollTop = 0;
  await new Promise(r => setTimeout(r, 300));
  return JSON.stringify(Object.keys(seen));
})()

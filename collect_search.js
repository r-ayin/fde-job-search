(async () => {
  // 滚动到底加载全部卡片
  for (let i = 0; i < 8; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 1200));
  }
  const boxes = [...document.querySelectorAll('li.job-card-box')];
  const cards = [];
  for (const li of boxes) {
    const a = li.querySelector('a.job-name');
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    const m = href.match(/job_detail\/([^.?]+)/);
    if (!m) continue;
    const q = s => { const e = li.querySelector(s); return e ? e.innerText.trim() : ''; };
    cards.push({
      eid: m[1],
      name: q('a.job-name'),
      salary: q('.job-salary'),
      tags: [...li.querySelectorAll('.tag-list li')].map(e => e.innerText.trim()).filter(Boolean),
      company: q('.boss-name'),
      area: q('.company-location')
    });
  }
  const seen = new Set();
  const uniq = cards.filter(c => { if (seen.has(c.eid)) return false; seen.add(c.eid); return true; });
  return JSON.stringify({ total: cards.length, uniq: uniq.length, cards: uniq }).slice(0, 30000);
})()

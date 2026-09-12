(async () => {
  // 等渲染
  for (let i = 0; i < 6; i++) {
    if (document.querySelectorAll('li.job-card-box').length > 3) break;
    await new Promise(r => setTimeout(r, 800));
  }
  const boxes = [...document.querySelectorAll('li.job-card-box')];
  const rows = [];
  for (const li of boxes) {
    const a = li.querySelector('a.job-name');
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    const m = href.match(/job_detail\/([^.?]+)/);
    if (!m) continue;
    const q = s => { const e = li.querySelector(s); return e ? e.innerText.trim() : ''; };
    rows.push([m[1], q('a.job-name'), q('.boss-name'), q('.job-salary'),
               [...li.querySelectorAll('.tag-list li')].map(e=>e.innerText.trim()).join('/'),
               q('.company-location')].join('~'));
  }
  return JSON.stringify({ url: location.href, n: rows.length, rows: rows });
})()

(() => {
  const boxes = [...document.querySelectorAll('li.job-card-box')];
  const cards = boxes.map(li => {
    const a = li.querySelector('a.job-name');
    const href = a ? a.getAttribute('href') : '';
    const m = href.match(/job_detail\/([^.?]+)/);
    const q = s => { const e = li.querySelector(s); return e ? e.innerText.trim() : ''; };
    return {
      eid: m ? m[1] : null,
      name: q('a.job-name'),
      salary: q('.salary'),
      area: q('.job-area'),
      company: q('.company-name'),
      tags: [...li.querySelectorAll('.tag-list li')].map(e => e.innerText.trim()).filter(Boolean),
      welfare: [...li.querySelectorAll('.job-card-footer .tag-list li')].map(e => e.innerText.trim()).filter(Boolean),
      bossName: q('.info-public .name'),
      bossTitle: q('.info-public em'),
      full: (li.innerText || '').split('\n').map(s => s.trim()).filter(Boolean).slice(0, 12).join(' | ')
    };
  }).filter(c => c.eid);
  return JSON.stringify({ count: cards.length, cards }).slice(0, 22000);
})()

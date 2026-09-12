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
      salary: q('.job-salary'),
      tags: [...li.querySelectorAll('.tag-list li')].map(e => e.innerText.trim()).filter(Boolean),
      company: q('.boss-name'),
      area: q('.company-location')
    };
  }).filter(c => c.eid);
  return JSON.stringify({ count: cards.length, cards }).slice(0, 20000);
})()

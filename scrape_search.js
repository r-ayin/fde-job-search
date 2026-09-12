(() => {
  const out = { url: location.href, cards: [] };
  // 找岗位卡片
  const lis = [...document.querySelectorAll('li')].filter(li => {
    const t = li.innerText || '';
    return t.indexOf('K') >= 0 && (li.querySelector('a[href*="job_detail"]') || li.querySelector('.job-name'));
  });
  for (const li of lis) {
    const a = li.querySelector('a[href*="job_detail"]');
    const nameEl = li.querySelector('.job-name, .job-card-left .job-title, [class*=job-name]');
    const salEl = li.querySelector('.salary, [class*=salary]');
    const tagEls = [...li.querySelectorAll('.tag-list li, .job-card-footer .tag-list li, [class*=tag]')];
    const areaEl = li.querySelector('.job-area, [class*=job-area]');
    const compEl = li.querySelector('.company-name, [class*=company-name]');
    out.cards.push({
      href: a ? a.getAttribute('href') : null,
      eid: a ? (a.getAttribute('href') || '').split('/job_detail/')[1]?.split('.')[0] : null,
      name: nameEl ? nameEl.innerText.trim() : '',
      salary: salEl ? salEl.innerText.trim() : '',
      area: areaEl ? areaEl.innerText.trim() : '',
      company: compEl ? compEl.innerText.trim() : '',
      tags: tagEls.map(e => e.innerText.trim()).filter(Boolean).slice(0, 8),
      text: (li.innerText || '').split('\n').filter(Boolean).slice(0, 12).join(' | ')
    });
  }
  return JSON.stringify(out).slice(0, 12000);
})()

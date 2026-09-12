(async () => {
  const ids = window.__jdQueue || [];
  const out = [];
  for (const item of ids) {
    try {
      const r = await fetch('/job_detail/' + item.encryptJobId + '.html', { credentials: 'include' });
      const html = await r.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const q = s => doc.querySelector(s);
      const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '';
      out.push({
        encryptJobId: item.encryptJobId,
        name: item.name,
        brandName: item.brandName,
        positionName: item.positionName,
        jobName: item.jobName,
        location: item.locationName,
        ok: r.status === 200,
        title: txt(q('.name h1') || q('h1')),
        salary: txt(q('.salary')),
        expEdu: txt(q('.job-primary .text, .info-primary p')),
        desc: txt(q('.job-sec-text') || q('.job-detail-section .text')),
        tags: [...doc.querySelectorAll('.job-keyword-list li, .tag-all .tag-item, .job-tags span')].map(e => txt(e)).filter(Boolean),
        companyIntro: txt(q('.company-info-box .text, .job-sec.company-info .text'))
      });
    } catch (e) {
      out.push({ encryptJobId: item.encryptJobId, name: item.name, brandName: item.brandName, error: String(e).slice(0, 120) });
    }
  }
  return out;
})()

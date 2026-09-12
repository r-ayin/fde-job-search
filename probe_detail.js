(() => {
  const g = s => document.querySelector(s);
  const txt = el => el ? (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim() : '';
  const out = {
    title: txt(g('.name h1') || g('h1')),
    salary: txt(g('.salary')),
    company: txt(g('.company-info .name') || g('.sider-company .name') || g('.company-name')),
    companyBox: txt(g('.company-info') || g('.sider-company')),
    jobSec: txt(g('.job-sec-text')).slice(0, 200)
  };
  // 找公司信息区所有候选
  out.candidates = [...document.querySelectorAll('[class*=company]')].slice(0, 8).map(e => ({
    cls: (e.className || '').toString().slice(0, 50), txt: (e.innerText || '').trim().slice(0, 60)
  }));
  return JSON.stringify(out);
})()

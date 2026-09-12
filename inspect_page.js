(() => {
  const out = {};
  out.url = location.href;
  out.jobCardBox = document.querySelectorAll('li.job-card-box').length;
  out.allLi = document.querySelectorAll('li').length;
  out.jobDetailLinks = document.querySelectorAll('a[href*="job_detail"]').length;
  // 主要容器
  out.containers = [...document.querySelectorAll('div')]
    .filter(d => { const c = (d.className||'').toString(); return /job-list|search-result|job-card-wrap|rec-job|result/i.test(c); })
    .slice(0, 8).map(d => ({ cls: (d.className||'').toString().slice(0, 55), childLi: d.querySelectorAll('li').length, sh: d.scrollHeight, ch: d.clientHeight }));
  // 页面底部文本
  out.bottomText = document.body.innerText.slice(-300);
  return JSON.stringify(out).slice(0, 2500);
})()

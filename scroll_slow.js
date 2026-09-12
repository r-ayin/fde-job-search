(async () => {
  const before = document.querySelectorAll('li.job-card-box').length;
  for (let i = 0; i < 10; i++) {
    window.scrollTo(0, document.documentElement.scrollHeight);
    await new Promise(r => setTimeout(r, 1500));
  }
  const after = document.querySelectorAll('li.job-card-box').length;
  // 找分页控件
  const pagText = [...document.querySelectorAll('div,a,span')]
    .filter(e => /下一页|^\d+$/.test((e.innerText||'').trim()) && (e.innerText||'').trim().length < 8)
    .slice(0, 15).map(e => e.tagName + ':' + (e.className||'').slice(0,30) + ':' + (e.innerText||'').trim());
  return JSON.stringify({ before: before, after: after, pag: pagText, bodyH: document.body.scrollHeight });
})()

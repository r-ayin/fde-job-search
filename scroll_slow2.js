(async () => {
  const before = document.querySelectorAll('li.job-card-box').length;
  for (let i = 0; i < 5; i++) {
    window.scrollTo(0, document.documentElement.scrollHeight);
    await new Promise(r => setTimeout(r, 900));
  }
  const after = document.querySelectorAll('li.job-card-box').length;
  const pagText = [...document.querySelectorAll('div,a,span')]
    .filter(e => /下一页|上一页/.test((e.innerText||'').trim()))
    .slice(0, 6).map(e => e.tagName + ':' + (e.className||'').slice(0,25) + ':' + (e.innerText||'').trim());
  return JSON.stringify({ before: before, after: after, pag: pagText, bodyH: document.body.scrollHeight });
})()

(() => {
  const out = { url: location.href, title: document.title };
  // 搜索框
  const sb = [...document.querySelectorAll('input')].find(e => (e.getAttribute('placeholder')||'').indexOf('搜索') >= 0);
  out.searchBox = sb ? { cls: (sb.className||'').slice(0,50), ph: sb.getAttribute('placeholder'), val: sb.value } : null;
  // 分页
  const pag = document.querySelector('.options-pages, .pagination, [class*=page]');
  out.pagination = pag ? (pag.className || '') + ' :: ' + (pag.innerText||'').replace(/\s+/g,' ').slice(0,120) : null;
  out.jobCards = document.querySelectorAll('li.job-card-box').length;
  // 页码链接
  out.pageLinks = [...document.querySelectorAll('a[href*=page], .options-pages a')].slice(0,12).map(a => (a.innerText||'').trim() + ' -> ' + (a.getAttribute('href')||''));
  return JSON.stringify(out).slice(0, 2000);
})()

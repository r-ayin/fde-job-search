(() => {
  const out = {};
  const sec = document.querySelector('.job-sec-text');
  out.secLen = sec ? sec.innerText.length : 0;
  out.secHTML = sec ? sec.outerHTML.slice(0, 400) : null;
  // 找展开按钮
  const btns = [...document.querySelectorAll('div,a,span')].filter(e => /展开|查看完整|查看更多/.test((e.innerText||'').trim()) && (e.innerText||'').trim().length < 12);
  out.expandBtns = btns.slice(0,6).map(e => e.tagName + ':' + (e.className||'').slice(0,40) + ':' + (e.innerText||'').trim());
  // 其他可能的选择器
  out.candidates = ['.job-detail-section', '.job-sec', '.detail-content', '.job-detail'].map(s => {
    const el = document.querySelector(s);
    return s + ' -> ' + (el ? el.innerText.length + ' | ' + (el.className||'') : 'null');
  });
  return JSON.stringify(out).slice(0, 2000);
})()

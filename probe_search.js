(() => {
  const out = {};
  const inputs = [...document.querySelectorAll('input')].map(e => ({
    cls: (e.className || '').slice(0, 50),
    ph: e.getAttribute('placeholder') || '',
    id: e.id
  }));
  out.inputs = inputs;
  const sb = [...document.querySelectorAll('input')].find(e => (e.getAttribute('placeholder') || '').indexOf('搜索') >= 0);
  out.searchBox = sb ? { cls: sb.className, ph: sb.getAttribute('placeholder'), parentCls: (sb.parentElement.className||'').slice(0,50) } : null;
  return JSON.stringify(out);
})()

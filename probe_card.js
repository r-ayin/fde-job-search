(() => {
  const a = document.querySelector('a[href*="job_detail"]');
  if (!a) return 'NO_ANCHOR';
  const chain = [];
  let el = a;
  for (let i = 0; i < 7 && el; i++) {
    chain.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 80), childCount: el.children.length });
    el = el.parentElement;
  }
  return JSON.stringify({ aHref: a.getAttribute('href'), aText: (a.innerText||'').slice(0,120), chain });
})()

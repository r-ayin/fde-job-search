(() => {
  const tabs = [...document.querySelectorAll('div,span,li,a')].filter(e => {
    const t = (e.innerText || '').trim();
    return t === '全部' || t === '未读' || t === '新招呼';
  });
  if (tabs.length) {
    const t = tabs.find(x => (x.innerText||'').trim() === '全部') || tabs[0];
    t.click();
    return 'clicked: ' + t.innerText.trim() + ' (candidates=' + tabs.length + ')';
  }
  return 'NO_TABS';
})()

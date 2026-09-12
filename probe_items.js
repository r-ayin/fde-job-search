(() => {
  const out = {};
  const wrap = document.querySelectorAll('.friend-content-warp');
  out.wrapCount = wrap.length;
  out.samples = [...wrap].slice(0, 3).map(w => {
    const li = w.closest('li');
    return {
      liClass: li ? (li.className || '') : null,
      text: (w.innerText || '').split('\n').filter(Boolean).slice(0, 4).join(' / '),
      name: (w.querySelector('.name-text') || {}).innerText,
      brand: (() => { const nb = w.querySelector('.name-box'); return nb ? nb.innerText.split('\n')[0] : ''; })()
    };
  });
  // 找带 active/selected 的会话项
  const act = [...document.querySelectorAll('.friend-content-warp')].filter(w => {
    const li = w.closest('li');
    return li && /active|selected|cur/i.test(li.className || '');
  });
  out.activeText = act.map(x => (x.innerText || '').split('\n').filter(Boolean).slice(0, 4).join(' / '));
  return JSON.stringify(out);
})()

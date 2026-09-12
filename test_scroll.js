(() => {
  const w = document.querySelector('.friend-content-warp');
  if (!w) return 'NO_WRAP';
  // 向上找可滚动容器
  let el = w.parentElement, found = null;
  for (let i = 0; i < 10 && el; i++) {
    const st = getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 20 && /auto|scroll/.test(st.overflowY)) { found = el; break; }
    el = el.parentElement;
  }
  if (!found) return JSON.stringify({ scroller: null, chain: [] });
  // 滚到底加载更多
  found.scrollTop = found.scrollHeight;
  return JSON.stringify({
    scroller: (found.className || '').slice(0, 60),
    scrollHeight: found.scrollHeight,
    clientHeight: found.clientHeight,
    before: document.querySelectorAll('.friend-content-warp').length
  });
})()

(() => {
  const items = [...document.querySelectorAll('.friend-content-warp')];
  for (const w of items) {
    if ((w.innerText || '').indexOf('宇泛智能') >= 0) {
      const inner = w.querySelector('.friend-content') || w.firstElementChild || w;
      inner.click();
      return 'clicked';
    }
  }
  return 'nf';
})()

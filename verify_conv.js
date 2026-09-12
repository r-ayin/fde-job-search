(() => {
  const brand = %s;
  const items = [...document.querySelectorAll('.friend-content-warp')];
  const scroller = document.querySelector('.user-list-content');
  if (scroller) {
    const step = Math.max(200, scroller.clientHeight - 60);
    for (let pos = 0; pos <= scroller.scrollHeight; pos += step) {
      scroller.scrollTop = pos;
      for (const w of items) {
        if ((w.innerText || '').indexOf(brand) >= 0) {
          (w.querySelector('.friend-content') || w.firstElementChild || w).click();
          return 'clicked';
        }
      }
    }
  }
  return 'not_found';
})()

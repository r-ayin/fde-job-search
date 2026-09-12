(() => {
  const brand = %s;
  const scroller = document.querySelector('.user-list-content');
  if (!scroller) return 'NO_SCROLLER';
  const step = Math.max(200, scroller.clientHeight - 60);
  for (let pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
    scroller.scrollTop = pos;
    const items = [...document.querySelectorAll('.friend-content-warp')];
    for (const w of items) {
      if ((w.innerText || '').indexOf(brand) >= 0) {
        (w.querySelector('.friend-content') || w.firstElementChild || w).click();
        return 'clicked@' + pos;
      }
    }
  }
  return 'not_found';
})()

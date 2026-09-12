(() => {
  const brand = '宇泛智能';
  const items = [...document.querySelectorAll('.friend-content-warp')];
  for (const w of items) {
    if ((w.innerText || '').indexOf(brand) >= 0) {
      const li = w.closest('li');
      const inner = w.querySelector('.friend-content') || w.firstElementChild;
      inner.click();
      return 'clicked_inner:' + (inner.className || inner.tagName);
    }
  }
  return 'not_found';
})()

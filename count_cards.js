(async () => {
  for (let i = 0; i < 6; i++) {
    window.scrollTo(0, document.documentElement.scrollHeight);
    await new Promise(r => setTimeout(r, 1800));
  }
  return JSON.stringify({
    cards: document.querySelectorAll('li.job-card-box').length,
    bodyH: document.body.scrollHeight,
    hasNoMore: document.body.innerText.indexOf('没有更多') >= 0,
    q: (document.querySelector('input.input') || {}).value || ''
  });
})()

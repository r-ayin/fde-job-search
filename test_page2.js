(() => {
  return JSON.stringify({
    url: location.href,
    cards: document.querySelectorAll('li.job-card-box').length,
    first: (document.querySelector('li.job-card-box a.job-name')||{}).innerText || null,
    last: (() => { const a = document.querySelectorAll('li.job-card-box a.job-name'); return a.length ? a[a.length-1].innerText : null; })(),
    hasMore: document.body.innerText.indexOf('没有更多') >= 0
  });
})()

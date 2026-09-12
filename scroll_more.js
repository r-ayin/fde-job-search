(async () => {
  const before = document.querySelectorAll('li').length;
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 2500));
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 2500));
  const after = document.querySelectorAll('li').length;
  const cards = [...document.querySelectorAll('a[href*="job_detail"]')].map(a => a.getAttribute('href'));
  return JSON.stringify({ before, after, linkCount: cards.length, hasMore: document.body.innerText.indexOf('没有更多') >= 0 });
})()

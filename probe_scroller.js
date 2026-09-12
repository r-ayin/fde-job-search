(() => {
  const out = {};
  const li = document.querySelector('li.job-card-box');
  if (!li) return 'NO_CARD';
  let el = li.parentElement, found = [];
  for (let i = 0; i < 12 && el; i++) {
    const st = getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 20) {
      found.push({ i: i, cls: (el.className||'').slice(0,50), sh: el.scrollHeight, ch: el.clientHeight, ov: st.overflowY });
    }
    el = el.parentElement;
  }
  out.scrollers = found;
  out.bodyScroll = { sh: document.body.scrollHeight, ch: document.body.clientHeight };
  out.docScroll = { sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight };
  return JSON.stringify(out);
})()

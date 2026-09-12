(() => {
  const sec = document.querySelector('.job-sec-text');
  if (!sec) return JSON.stringify({ err: 'NO_SEC' });
  const html = sec.innerHTML || '';
  const text = (sec.textContent || '').replace(/\s+/g, ' ').trim();
  return JSON.stringify({
    innerTextLen: (sec.innerText || '').length,
    textContentLen: text.length,
    htmlLen: html.length,
    textHead: text.slice(0, 200),
    textTail: text.slice(-200)
  });
})()

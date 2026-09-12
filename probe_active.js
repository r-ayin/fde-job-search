(() => {
  const out = {};
  out.url = location.href;
  out.liCount = document.querySelectorAll('li').length;
  const act = [...document.querySelectorAll('li')].filter(li => /active|selected|current/i.test(li.className || ''));
  out.activeLis = act.slice(0, 3).map(x => x.className + ' || ' + (x.innerText || '').split('\n').filter(Boolean).slice(0, 4).join(' / '));
  const pc = document.querySelector('.chat-position-content');
  out.positionJob = pc ? pc.innerText.split('\n').filter(Boolean).join(' | ') : null;
  const cv = document.querySelector('.chat-conversation');
  out.convHead = cv ? cv.innerText.split('\n').filter(Boolean).slice(0, 5).join(' | ') : null;
  // 所有 li 的类名样本
  out.liClasses = [...document.querySelectorAll('li')].slice(0, 12).map(x => (x.className || '').slice(0, 40));
  return JSON.stringify(out);
})()

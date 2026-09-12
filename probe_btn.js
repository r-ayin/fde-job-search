(() => {
  const btns = [...document.querySelectorAll('a,button,div,span')].filter(e => {
    const t = (e.innerText || '').trim();
    return /立即沟通|继续沟通|打招呼|发起沟通/.test(t) && t.length < 20;
  }).map(e => ({
    tag: e.tagName,
    text: (e.innerText || '').trim(),
    cls: (e.className || '').toString().slice(0, 60),
    href: e.getAttribute && e.getAttribute('href')
  }));
  return JSON.stringify({ url: location.href, title: document.title, btns: btns.slice(0, 10) });
})()

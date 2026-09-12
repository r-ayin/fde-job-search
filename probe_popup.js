(() => {
  const out = { url: location.href, title: document.title };
  out.editables = [...document.querySelectorAll('[contenteditable="true"], textarea')].map(e => ({
    tag: e.tagName, id: e.id, cls: (e.className||'').toString().slice(0,60),
    vis: e.offsetParent !== null, ph: e.getAttribute('placeholder') || ''
  }));
  out.sendBtns = [...document.querySelectorAll('div,button,a')].filter(e => /^\s*发送\s*$/.test((e.innerText||'').trim())).map(e => ({
    tag: e.tagName, cls: (e.className||'').toString().slice(0,60)
  }));
  // 聊天弹窗容器
  out.chatBoxes = [...document.querySelectorAll('[class*=chat],[class*=dialog],[class*=popup]')].slice(0,10).map(e => ({
    cls: (e.className||'').toString().slice(0,70), txt: (e.innerText||'').replace(/\s+/g,' ').slice(0,80)
  }));
  return JSON.stringify(out).slice(0, 3000);
})()

(() => {
  const t = document.querySelector('textarea.input-area');
  const box = document.querySelector('.dialog-open');
  return JSON.stringify({
    url: location.href,
    inputVal: t ? t.value : null,
    chatText: box ? box.innerText.replace(/\s+/g,' ').slice(0, 600) : null
  });
})()

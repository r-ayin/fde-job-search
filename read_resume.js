(() => {
  const out = {};
  // 简历主体文本
  const main = document.querySelector('.resume-main, .resume-content, #wrap');
  out.text = main ? main.innerText.slice(0, 12000) : document.body.innerText.slice(0, 12000);
  // 结构化：各 section
  const secs = [...document.querySelectorAll('[class*=section], [class*=item], .resume-item')].slice(0, 60).map(e => ({
    cls: (e.className || '').toString().slice(0, 60),
    txt: (e.innerText || '').slice(0, 300)
  })).filter(x => x.txt.trim());
  out.sections = secs;
  return JSON.stringify(out).slice(0, 18000);
})()

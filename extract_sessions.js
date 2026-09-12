(() => {
  const out = [];
  const lis = [...document.querySelectorAll('li')].filter(li => {
    const t = li.innerText || '';
    return t.indexOf('送达') >= 0 || t.indexOf('已读') >= 0;
  });
  for (const li of lis) {
    const nodes = [li, ...li.querySelectorAll('*')];
    let obj = null;
    for (const n of nodes) {
      let p = n.__vue__;
      let d = 0;
      while (p && d < 6) {
        const data = p._data || {};
        for (const k of Object.keys(data)) {
          const v = data[k];
          if (v && typeof v === 'object' && !Array.isArray(v) && v.encryptJobId !== undefined && v.friendId !== undefined) {
            obj = v; break;
          }
        }
        if (obj) break;
        p = p.$parent; d++;
      }
      if (obj) break;
    }
    const txt = (li.innerText || '').split('\n').join(' | ');
    if (obj) {
      out.push({
        name: obj.name,
        brand: obj.brand || null,
        encryptJobId: obj.encryptJobId,
        jobId: obj.jobId,
        friendId: obj.friendId,
        lastText: obj.lastText || null,
        unread: obj.unreadCount,
        dom: txt.slice(0, 200)
      });
    } else {
      out.push({ dom: txt.slice(0, 200) });
    }
  }
  return out;
})()

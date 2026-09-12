(() => {
  const els = [...document.querySelectorAll('*')].filter(e => e.__vue__);
  const comps = new Set();
  for (const el of els) { let p = el.__vue__; let d=0; while (p && d<15) { comps.add(p); p=p.$parent; d++; } }
  for (const c of comps) {
    const nm = (c.$options && (c.$options.name || c.$options._componentTag)) || '';
    if (nm === 'virtual-list') {
      const src = (c.$props && c.$props.dataSources) || (c._data && c._data.dataSources);
      if (src && src.length) return JSON.stringify(src.map(x => ({
        name: x.name, brand: x.brandName, jobName: x.jobName,
        encryptJobId: x.encryptJobId, friendId: x.friendId,
        encryptBossId: x.encryptBossId, securityId: x.securityId,
        lastText: (x.lastText || '').slice(0, 50), unread: x.unreadCount
      })));
    }
  }
  return 'NF';
})()

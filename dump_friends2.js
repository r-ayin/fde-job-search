(() => {
  const els = [...document.querySelectorAll('*')].filter(e => e.__vue__);
  const comps = new Set();
  for (const el of els) {
    let p = el.__vue__;
    let d = 0;
    while (p && d < 15) { comps.add(p); p = p.$parent; d++; }
  }
  for (const c of comps) {
    const nm = (c.$options && (c.$options.name || c.$options._componentTag)) || '';
    if (nm === 'virtual-list') {
      const src = (c.$props && c.$props.dataSources) || (c._data && c._data.dataSources);
      if (src && src.length) {
        return src.map(x => ({
          name: x.name, brandName: x.brandName, positionName: x.positionName,
          jobName: x.jobName, title: x.title, jobTypeDesc: x.jobTypeDesc,
          locationName: x.locationName, encryptJobId: x.encryptJobId, jobId: x.jobId,
          friendId: x.friendId, lastText: x.lastText, unreadCount: x.unreadCount,
          lastTS: x.lastTS, lastMsgStatus: x.lastMsgStatus, relationType: x.relationType
        }));
      }
    }
  }
  return 'NOT_FOUND';
})()

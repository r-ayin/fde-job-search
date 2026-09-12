
(() => {
  const w = document.querySelector('.friend-content-warp');
  if (!w) return 'NO_WARP';
  let p = w.__vue__;
  let d = 0;
  while (p && d < 20) {
    const nm = (p.$options && (p.$options.name || p.$options._componentTag)) || '';
    const src = (p.$props && p.$props.dataSources) || (p._data && p._data.dataSources);
    if (nm === 'virtual-list' && src && src.length) {
      return JSON.stringify(src.map(x => ({
        hr: x.name, brand: x.brandName, convJob: x.jobName || x.positionName || '',
        eid: x.encryptJobId, last: x.lastText || ''
      })));
    }
    p = p.$parent; d++;
  }
  return 'NOT_FOUND';
})()

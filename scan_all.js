(() => {
  const out = { stores: [], hits: [] };
  const els = [...document.querySelectorAll('*')].filter(e => e.__vue__);
  const comps = new Set();
  for (const el of els) {
    let p = el.__vue__;
    let d = 0;
    while (p && d < 15) { comps.add(p); p = p.$parent; d++; }
  }
  out.compCount = comps.size;
  for (const c of comps) {
    try {
      if (c.$store) {
        out.stores.push({ name: c.$options && c.$options.name, hasStore: true, stateKeys: Object.keys(c.$store.state || {}).slice(0, 30) });
        break;
      }
    } catch (e) {}
  }
  // 搜索所有组件的 data/props 中带 encryptJobId 的
  for (const c of comps) {
    const nm = (c.$options && (c.$options.name || c.$options._componentTag)) || '?';
    const pools = [];
    if (c._data) pools.push(['data', c._data]);
    if (c.$props) pools.push(['props', c.$props]);
    for (const [kind, pool] of pools) {
      for (const k of Object.keys(pool)) {
        const v = pool[k];
        if (Array.isArray(v) && v.length) {
          const obj0 = v.find(x => x && typeof x === 'object' && (x.encryptJobId !== undefined || x.friendId !== undefined));
          if (obj0) out.hits.push({ comp: nm, kind, key: k, len: v.length, sampleKeys: Object.keys(obj0).slice(0, 30) });
        } else if (v && typeof v === 'object' && !Array.isArray(v) && (v.encryptJobId !== undefined || v.friendId !== undefined)) {
          out.hits.push({ comp: nm, kind, key: k, single: true, sampleKeys: Object.keys(v).slice(0, 30) });
        }
      }
    }
    if (out.hits.length > 10) break;
  }
  return JSON.stringify(out).slice(0, 3500);
})()

(() => {
  // 尝试从 Vue store 读简历数据
  const els = [...document.querySelectorAll('*')].filter(e => e.__vue__);
  const comps = new Set();
  for (const el of els) {
    let p = el.__vue__;
    let d = 0;
    while (p && d < 15) { comps.add(p); p = p.$parent; d++; }
  }
  for (const c of comps) {
    try {
      if (c.$store && c.$store.state) {
        const st = c.$store.state;
        if (st.resume && Object.keys(st.resume).length) {
          return JSON.stringify(st.resume).slice(0, 20000);
        }
      }
    } catch (e) {}
  }
  return 'NO_RESUME_IN_STORE';
})()

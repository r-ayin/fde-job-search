(() => {
  const entries = performance.getEntriesByType('resource')
    .filter(e => e.initiatorType === 'xmlhttprequest' || e.initiatorType === 'fetch')
    .map(e => e.name)
    .filter(n => n.indexOf('/wapi/') >= 0 || n.indexOf('chat') >= 0 || n.indexOf('job') >= 0);
  const uniq = [...new Set(entries)];
  return uniq.slice(-60);
})()

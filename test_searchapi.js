(async () => {
  var out = [];
  var tests = [
    '/wapi/zpgeek/search/joblist.json?scene=1&query=fde&city=101210100&page=1&pageSize=30',
    '/wapi/zpgeek/search/joblist.json?scene=1&query=fde&city=101210100&page=2&pageSize=30'
  ];
  for (var t = 0; t < tests.length; t++) {
    try {
      var r = await fetch(tests[t], {credentials:'include'});
      var j = await r.json();
      var zd = j.zpData || {};
      var list = zd.jobList || [];
      out.push({ url: tests[t].slice(-60), code: j.code, msg: j.message, keys: Object.keys(zd), count: list.length, total: zd.totalCount || zd.total || null });
    } catch(e) { out.push({ url: tests[t].slice(-60), err: String(e).slice(0,80) }); }
  }
  return JSON.stringify(out);
})()

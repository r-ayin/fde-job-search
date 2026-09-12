(async () => {
  var r = await fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=fde&city=101210100&page=1&pageSize=30', {credentials:'include'});
  var j = await r.json();
  var list = (j.zpData && j.zpData.jobList) || [];
  return JSON.stringify({
    total: j.zpData.totalCount,
    sampleKeys: list.length ? Object.keys(list[0]) : [],
    first: list.length ? list[0] : null
  }).slice(0, 2200);
})()

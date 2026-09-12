(async function(){
  var r = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', {
    method:'POST', credentials:'include',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'page=1&pageSize=100'
  });
  var j = await r.json();
  var arr = (j.zpData && j.zpData.result) || [];
  var out = { count: arr.length, sampleKeys: arr.length ? Object.keys(arr[0]) : [] };
  if (arr.length) {
    var a = arr[0];
    out.sample = {
      name: a.name, brandName: a.brandName, jobName: a.jobName,
      lastMsg: a.lastMsg, hasInfo: !!a.lastMessageInfo
    };
    if (a.lastMessageInfo) out.msgKeys = Object.keys(a.lastMessageInfo);
  }
  return JSON.stringify(out).slice(0, 1800);
})()

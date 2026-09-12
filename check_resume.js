(async function(){
  var r = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', {
    method:'POST', credentials:'include',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'page=1&pageSize=100'
  });
  var j = await r.json();
  var arr = (j.zpData && j.zpData.result) || [];
  var withRes = 0, without = [];
  for (var i = 0; i < arr.length; i++) {
    var a = arr[i];
    var txt = String((a.lastMessageInfo && a.lastMessageInfo.showText) || a.lastMsg || '');
    if (txt.indexOf('example.com') >= 0) { withRes++; }
    else if (txt.indexOf('您好，看到') >= 0) {
      without.push([a.brandName||'', a.name||'', txt.slice(0,50)].join('~'));
    }
  }
  return JSON.stringify({ withResume: withRes, missingCount: without.length, missing: without });
})()

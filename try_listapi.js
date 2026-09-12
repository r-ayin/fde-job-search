(async function(){
  var out = {};
  try {
    var r1 = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', {credentials:'include'});
    var t1 = await r1.text();
    out.get = t1.slice(0, 200);
  } catch(e) { out.getErr = String(e).slice(0,100); }
  try {
    var r2 = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', {
      method:'POST', credentials:'include',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'page=1&pageSize=100'
    });
    var t2 = await r2.text();
    out.post = t2.slice(0, 200);
    out.postLen = t2.length;
  } catch(e) { out.postErr = String(e).slice(0,100); }
  return JSON.stringify(out);
})()

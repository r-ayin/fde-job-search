(async () => {
  const r = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', { credentials: 'include' });
  const j = await r.json();
  const d = j.zpData || {};
  const keys = Object.keys(d);
  let arr = null, arrKey = null;
  for (const k of keys) { if (Array.isArray(d[k]) && d[k].length) { arr = d[k]; arrKey = k; break; } }
  return JSON.stringify({
    code: j.code, msg: j.message, keys,
    arrKey, len: arr ? arr.length : 0,
    sample: arr && arr[0] ? Object.keys(arr[0]) : null,
    first: arr && arr[0] ? JSON.stringify(arr[0]).slice(0, 1200) : null
  }).slice(0, 3000);
})()

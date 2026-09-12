(async () => {
  const r = await fetch('/wapi/zprelation/friend/getGeekFriendList.json', { credentials: 'include' });
  const t = await r.text();
  return t.slice(0, 1500);
})()

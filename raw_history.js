(async () => {
  const bossId = '338bf7a1e0eb7fbd0XN93Nu7EFtR';
  const securityId = 'BBSb1n0tHmRRR-K1Yw5DISmuu1MVWSk7K1eyIbtv-KIjukuwH-Y-f6_E44DMe7xa1GZ3zk8Ir5sjXsHTliRus874enTCz0o8z5_uTxm6MzS_ivk2L7njjhtDAhLCa5VbqDTdrv8l09iAQaddCHuvIpo5KNxsa7d4T80ts4EqCfqfhd-uLgd274NGO-ny0uGyZT7JR2LyCWI1FmnjDNN3_nI~';
  const url = '/wapi/zpchat/geek/historyMsg?bossId=' + bossId + '&maxMsgId=0&c=50&page=1&src=0&securityId=' + encodeURIComponent(securityId);
  const r = await fetch(url, { credentials: 'include' });
  const t = await r.text();
  return t.slice(0, 8000);
})()

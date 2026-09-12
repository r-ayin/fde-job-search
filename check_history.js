(async () => {
  const bossId = '338bf7a1e0eb7fbd0XN93Nu7EFtR';
  const securityId = 'BBSb1n0tHmRRR-K1Yw5DISmuu1MVWSk7K1eyIbtv-KIjukuwH-Y-f6_E44DMe7xa1GZ3zk8Ir5sjXsHTliRus874enTCz0o8z5_uTxm6MzS_ivk2L7njjhtDAhLCa5VbqDTdrv8l09iAQaddCHuvIpo5KNxsa7d4T80ts4EqCfqfhd-uLgd274NGO-ny0uGyZT7JR2LyCWI1FmnjDNN3_nI~';
  const url = '/wapi/zpchat/geek/historyMsg?bossId=' + bossId + '&maxMsgId=0&c=20&page=1&src=0&securityId=' + encodeURIComponent(securityId);
  const r = await fetch(url, { credentials: 'include' });
  const j = await r.json();
  const list = (j.zpData && j.zpData.messages) || (j.zpData && j.zpData.list) || [];
  const out = list.map(m => ({
    id: m.messageId || m.msgId,
    type: m.type,
    from: m.from,
    text: (m.body && (m.body.text || m.body.content)) || m.text || '',
    ts: m.time || m.createTime
  }));
  return JSON.stringify({ code: j.code, msg: j.message, count: out.length, msgs: out }).slice(0, 3000);
})()

(async () => {
  const r = await fetch('/job_detail/' + 'bde5db43745c17ad0nB50t-5ElpW' + '.html', { credentials: 'include' });
  const t = await r.text();
  return JSON.stringify({
    status: r.status,
    len: t.length,
    head: t.slice(0, 600),
    hasSecText: t.indexOf('job-sec-text') >= 0,
    hasVerify: t.indexOf('verify') >= 0 || t.indexOf('安全验证') >= 0
  });
})()

(() => {
  const li = document.querySelector('li.job-card-box');
  if (!li) return 'NO';
  return JSON.stringify({ html: li.outerHTML.slice(0, 2000) });
})()

(() => {
  const sb = document.querySelector('.boss-search-input');
  if (!sb) return 'NO_SEARCH';
  sb.focus();
  return 'focused';
})()

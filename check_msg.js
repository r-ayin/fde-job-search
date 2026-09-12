(() => {
  const conv = document.querySelector('.chat-conversation');
  return conv ? conv.innerText.slice(0, 1500) : 'NO_CONV';
})()

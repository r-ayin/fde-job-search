(async () => {
  var scroller = document.querySelector('.user-list-content');
  var step = Math.max(150, scroller.clientHeight - 80);
  var brand = '皆大欢喜';
  var clicked = false;
  for (var pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
    scroller.scrollTop = pos;
    await new Promise(function(r){setTimeout(r,250);});
    var items = document.querySelectorAll('.friend-content-warp');
    for (var i = 0; i < items.length; i++) {
      if ((items[i].innerText||'').indexOf(brand) >= 0) {
        (items[i].querySelector('.friend-content')||items[i].firstElementChild||items[i]).click();
        clicked = true; break;
      }
    }
    if (clicked) break;
  }
  if (!clicked) return 'NOT_FOUND';
  await new Promise(function(r){setTimeout(r,5000);});
  var pc = document.querySelector('.chat-position-content');
  var cv = document.querySelector('.chat-conversation');
  var t = cv ? cv.innerText : '';
  var i = t.indexOf(String.fromCharCode(12300)), j = t.indexOf(String.fromCharCode(12301));
  return 'panel=' + (pc?pc.innerText.split(String.fromCharCode(10))[0]:'?') + ' | msg=' + ((i>=0&&j>i)?t.substring(i+1,j):'?');
})()

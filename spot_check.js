(async () => {
  var LB = String.fromCharCode(12300), RB = String.fromCharCode(12301);
  var scroller = document.querySelector('.user-list-content');
  if (!scroller) return 'NO_SCROLLER';
  var step = Math.max(150, scroller.clientHeight - 80);
  var targets = ['皆大欢喜', '润和软件', '数秦科技'];
  var out = [];
  for (var t = 0; t < targets.length; t++) {
    var brand = targets[t];
    var clicked = false;
    for (var pos = 0; pos <= scroller.scrollHeight + step; pos += step) {
      scroller.scrollTop = pos;
      await new Promise(function(r){setTimeout(r, 250);});
      var items = document.querySelectorAll('.friend-content-warp');
      for (var i = 0; i < items.length; i++) {
        if ((items[i].innerText || '').indexOf(brand) >= 0) {
          (items[i].querySelector('.friend-content') || items[i].firstElementChild || items[i]).click();
          clicked = true; break;
        }
      }
      if (clicked) break;
    }
    if (!clicked) { out.push(brand + ' :: NOT_FOUND'); continue; }
    // 等面板稳定：header 含品牌 且 岗位卡有内容，再等额外 2 秒
    var stable = 0;
    for (var k = 0; k < 20; k++) {
      await new Promise(function(r){setTimeout(r, 500);});
      var cv = document.querySelector('.chat-conversation');
      var pc = document.querySelector('.chat-position-content');
      var txt = cv ? cv.innerText : '';
      var ptxt = pc ? pc.innerText : '';
      if (cv && txt.indexOf(brand) >= 0 && ptxt.length > 3) { stable++; if (stable >= 3) break; }
    }
    var cv2 = document.querySelector('.chat-conversation');
    var pc2 = document.querySelector('.chat-position-content');
    var t2 = cv2 ? cv2.innerText : '';
    var i2 = t2.indexOf(LB), j2 = t2.indexOf(RB);
    out.push(brand + ' :: panelJob=' + (pc2 ? pc2.innerText.split(String.fromCharCode(10))[0] : '?') + ' :: msgJob=' + (i2 >= 0 && j2 > i2 ? t2.substring(i2+1, j2) : '?'));
  }
  return out.join('
');
})()
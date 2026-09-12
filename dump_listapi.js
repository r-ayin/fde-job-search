(function(){
  var c = window.__cap || [];
  for (var i = 0; i < c.length; i++) {
    if (String(c[i].u).indexOf('getGeekFriendList') >= 0) {
      return String(c[i].t);
    }
  }
  return 'NOT_CAPTURED';
})()

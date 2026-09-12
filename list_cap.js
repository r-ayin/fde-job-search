(function(){
  var c = window.__cap || [];
  var out = [];
  for (var i = 0; i < c.length; i++) {
    out.push(String(c[i].t.length) + ' | ' + String(c[i].u).slice(0, 110));
  }
  return out.join(String.fromCharCode(10));
})()

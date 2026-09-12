(function(){
  window.__cap = [];
  try {
    var of = window.fetch;
    window.fetch = function(){
      var a = arguments[0];
      var u = (typeof a === 'string') ? a : ((a && a.url) || '');
      return of.apply(this, arguments).then(function(res){
        try {
          if (String(u).indexOf('/wapi/') >= 0) {
            var c = res.clone();
            c.text().then(function(t){ window.__cap.push({u:String(u), t:t.slice(0,6000)}); }).catch(function(){});
          }
        } catch(e){}
        return res;
      });
    };
  } catch(e){}
  try {
    var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m,u){ this.__u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(){
      var self = this;
      this.addEventListener('load', function(){
        try { if (String(self.__u||'').indexOf('/wapi/') >= 0) window.__cap.push({u:String(self.__u), t:String(self.responseText||'').slice(0,6000)}); } catch(e){}
      });
      return os.apply(this, arguments);
    };
  } catch(e){}
})();

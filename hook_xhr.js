(() => {
  if (window.__zcodeHooked) return 'already hooked';
  window.__zcodeHooked = true;
  window.__zcodeReqs = [];
  const OrigOpen = XMLHttpRequest.prototype.open;
  const OrigSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__zcUrl = url;
    return OrigOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    const self = this;
    this.addEventListener('load', function () {
      try {
        const u = String(self.__zcUrl || '');
        if (u.indexOf('FriendList') >= 0 || u.indexOf('friend') >= 0 || u.indexOf('chat') >= 0) {
          window.__zcodeReqs.push({
            url: u.slice(0, 300),
            reqBody: body ? String(body).slice(0, 400) : null,
            resp: String(self.responseText || '').slice(0, 6000)
          });
          if (window.__zcodeReqs.length > 12) window.__zcodeReqs.shift();
        }
      } catch (e) {}
    });
    return OrigSend.apply(this, arguments);
  };
  return 'hooked';
})()

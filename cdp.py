import json, sys, urllib.request

PORT = 18793

def cmd(method, params=None, session="cb-tab-1"):
    body = json.dumps({"method": method, "params": params or {}, "sessionId": session}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/cmd", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.load(r)
    if "error" in resp:
        raise RuntimeError(resp["error"])
    return resp.get("result", {})

def js(expr):
    """Evaluate JS in the page and return the value."""
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    inner = r.get("result", {})
    if inner.get("subtype") == "error" or r.get("exceptionDetails"):
        raise RuntimeError(json.dumps(r, ensure_ascii=False)[:500])
    return inner.get("value")

if __name__ == "__main__":
    expr = sys.argv[1] if len(sys.argv) > 1 else "document.title"
    print(js(expr))

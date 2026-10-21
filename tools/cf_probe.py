#!/usr/bin/env python3
"""بررسی توکن‌های کلودفلر (CF_ACCOUNTS): حساب، دسترسی KV و Workers. هیچ توکنی چاپ نمی‌شود."""
import json, os, urllib.request, urllib.error

API = "https://api.cloudflare.com/client/v4"

def call(token, path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"errors": [{"message": str(e)}]}

def err(body):
    return "; ".join(f"{e.get('code')}:{e.get('message')}" for e in body.get("errors", []))[:120]

for acc in json.loads(os.environ["CF_ACCOUNTS"]):
    name, tok = acc["name"], acc["token"]
    s, b = call(tok, "/user/tokens/verify")
    status = b.get("result", {}).get("status") if s == 200 else f"HTTP {s} {err(b)}"
    s, b = call(tok, "/accounts")
    accounts = [(a["id"], a["name"]) for a in b.get("result", [])] if s == 200 else []
    line = [f"token={status}", f"accounts={[(i[:6], n) for i, n in accounts] or err(b)}"]
    for aid, an in accounts:
        s, b = call(tok, f"/accounts/{aid}/storage/kv/namespaces?per_page=50")
        kv = f"ok({len(b.get('result', []))} ns: {[n['title'] for n in b.get('result', [])]})" if s == 200 else f"NO {err(b)}"
        s, b = call(tok, f"/accounts/{aid}/workers/scripts")
        wk = f"ok({len(b.get('result', []))})" if s == 200 else f"NO {err(b)}"
        s, b = call(tok, f"/accounts/{aid}/workers/subdomain")
        sub = b.get("result", {}).get("subdomain") if s == 200 else f"NO {err(b)}"
        line.append(f"[{aid[:6]}] kv={kv} workers={wk} subdomain={sub}")
    print(f"::notice title=probe {name}::" + " | ".join(line))

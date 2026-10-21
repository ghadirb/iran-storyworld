#!/usr/bin/env python3
"""ذخیرهٔ چندحسابی روی Cloudflare KV (جایگزین R2 که بدون کارت بانکی فعال نمی‌شود).

ایده: هر حساب رایگان ۱ گیگابایت KV دارد (هر مقدار ≤ ۲۵MiB، ۱۰۰۰ نوشتن در روز). این ابزار فایل‌ها را
از حساب اول پر می‌کند و وقتی سهمیهٔ بودجه‌شده یا محدودیت نوشتن تمام شد، به حساب بعدی می‌ریزد.
جدول «کدام فایل در کدام حساب است» (registry) در حساب اول ذخیره می‌شود و Worker از روی آن می‌خواند.

محیط:
  CF_ACCOUNTS          آرایهٔ JSON از {"name": "...", "token": "cfut_..."} (به‌صورت GitHub Secret)
  PRIMARY_ACCOUNT_ID   شناسهٔ حسابی که Worker در آن مستقر است (اختیاری؛ آن حساب اول می‌شود)
  KV_ACCOUNT_BUDGET_MB سقف استفاده از هر حساب (پیش‌فرض ۹۰۰ از ۱۰۲۴)
  KV_PRIMARY_STORES_MEDIA=1  فقط اگر بخواهی حساب اصلی هم رسانه نگه دارد (پیش‌فرض: خیر؛ فقط registry)

دستورها:
  prepare --out FILE   کشف حساب‌ها، ساخت namespace، نوشتن JSON نرمال‌شده برای Worker
  sync MANIFEST        هر خط: <key> <file> <content-type>  (کاتالوگ را آخر بگذار)
  status               مصرف هر حساب بر اساس registry
هیچ‌جا توکن چاپ نمی‌شود.
"""
import hashlib, json, os, sys, time, uuid, urllib.error, urllib.parse, urllib.request

API = "https://api.cloudflare.com/client/v4"
NS_TITLE = "riwayat-media"
REGISTRY_KEY = "__registry__"
BUDGET = int(os.environ.get("KV_ACCOUNT_BUDGET_MB", "900")) * 1024 * 1024
MAX_VALUE = 25 * 1024 * 1024 - 4096  # کمی حاشیه زیر ۲۵MiB


class CFError(Exception):
    def __init__(self, status, msg):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


def http(token, method, path, body=None, headers=None, raw=False, retries=3):
    h = {"Authorization": f"Bearer {token}"}
    h.update(headers or {})
    for attempt in range(retries):
        req = urllib.request.Request(API + path, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            if e.code in (500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            try:
                msg = "; ".join(f"{x.get('code')}:{x.get('message')}" for x in json.loads(data).get("errors", []))
            except Exception:
                msg = data[:120].decode("utf8", "replace")
            raise CFError(e.code, msg or "error")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise CFError(0, str(e))


def discover():
    """حساب‌های قابل‌استفاده را (یکتا بر اساس شناسهٔ حساب) برمی‌گرداند: [{name,id,token,ns}]"""
    items = json.loads(os.environ["CF_ACCOUNTS"])
    primary = os.environ.get("PRIMARY_ACCOUNT_ID", "")
    found, seen = [], set()
    for it in items:
        name, tok = it.get("name", "?"), it["token"]
        try:
            accs = http(tok, "GET", "/accounts")["result"]
        except CFError as e:
            print(f"::warning title=skip {name}::توکن/حساب قابل‌استفاده نیست ({e})")
            continue
        for a in accs:
            if a["id"] in seen:
                continue
            try:
                ns = ensure_namespace(tok, a["id"])
            except CFError as e:
                print(f"::warning title=skip {name}::دسترسی KV ندارد ({e})")
                continue
            seen.add(a["id"])
            found.append({"name": name, "id": a["id"], "token": tok, "ns": ns})
    found.sort(key=lambda x: 0 if x["id"] == primary else 1)  # پایدار: حساب اصلی اول
    if not found:
        raise SystemExit("هیچ حساب قابل‌استفاده‌ای پیدا نشد")
    if primary and found[0]["id"] != primary:
        print(f"::warning title=primary::حساب اصلی Worker در بین توکن‌های KV نیست؛ حساب {found[0]['name']} اصلی شد")
    return found


def ensure_namespace(token, acct):
    page = 1
    while True:
        r = http(token, "GET", f"/accounts/{acct}/storage/kv/namespaces?per_page=100&page={page}")
        for n in r["result"]:
            if n["title"] == NS_TITLE:
                return n["id"]
        if page >= r.get("result_info", {}).get("total_pages", 1):
            break
        page += 1
    r = http(token, "POST", f"/accounts/{acct}/storage/kv/namespaces", json.dumps({"title": NS_TITLE}).encode(),
             {"Content-Type": "application/json"})
    return r["result"]["id"]


def kv_path(acc, key):
    return f"/accounts/{acc['id']}/storage/kv/namespaces/{acc['ns']}/values/{urllib.parse.quote(key, safe='')}"


def kv_put(acc, key, data, meta=None):
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="value"\r\n\r\n'.encode(), data, b"\r\n",
             f'--{b}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{json.dumps(meta or {})}\r\n--{b}--\r\n'.encode()]
    http(acc["token"], "PUT", kv_path(acc, key), b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={b}"})


def kv_get(acc, key):
    try:
        return http(acc["token"], "GET", kv_path(acc, key), raw=True)
    except CFError as e:
        if e.status == 404:
            return None
        raise


def kv_delete(acc, key):
    try:
        http(acc["token"], "DELETE", kv_path(acc, key))
    except CFError as e:
        print(f"::warning title=delete::{key}: {e}")


def load_registry(primary):
    raw = kv_get(primary, REGISTRY_KEY)
    return json.loads(raw) if raw else {"version": 1, "objects": {}}


def usage(reg, acct_id):
    return sum(o["size"] for o in reg["objects"].values() if o["acct"] == acct_id)


def candidates(reg, accounts, key, size):
    """ترتیب حساب‌های مناسب: اول حساب فعلی همان کلید (جایگزینی)، بعد به ترتیب پرشدن."""
    cur = reg["objects"].get(key)
    order = []
    if cur:
        a = next((x for x in accounts if x["id"] == cur["acct"]), None)
        if a and usage(reg, a["id"]) - cur["size"] + size <= BUDGET:
            order.append(a)
    for a in accounts:
        if a in order:
            continue
        if usage(reg, a["id"]) + size <= BUDGET:
            order.append(a)
    return order


def put_object(accounts, reg, key, data, ct, exhausted, storage=None):
    """accounts = همهٔ حساب‌ها (برای حذف از حساب قبلی)؛ storage = حساب‌هایی که اجازهٔ نگه‌داری فایل دارند."""
    storage = storage if storage is not None else accounts
    size = len(data)
    if size > MAX_VALUE:
        raise SystemExit(f"{key}: حجم {size/1048576:.1f}MiB بیش از سقف KV است؛ crf را بیشتر کن یا ویدیو را کوتاه‌تر کن")
    sha = hashlib.sha256(data).hexdigest()
    cur = reg["objects"].get(key)
    if cur and cur["sha"] == sha and any(a["id"] == cur["acct"] for a in storage):
        print(f"= {key} بدون تغییر ({cur['acct'][:6]})")
        return
    last = None
    for acc in candidates(reg, storage, key, size):
        if acc["id"] in exhausted:
            continue
        try:
            kv_put(acc, key, data, {"ct": ct, "size": size})
        except CFError as e:
            last = e
            # ۴۲۹/۴۰۳ و خطاهای سقف روزانه/حجم: این حساب را برای بقیهٔ اجرا کنار بگذار و به حساب بعد برو
            print(f"::warning title=spill::{acc['name']} ({acc['id'][:6]}) فایل {key} را نپذیرفت ({e}) → حساب بعدی")
            exhausted.add(acc["id"])
            continue
        if cur and cur["acct"] != acc["id"]:
            old = next((x for x in accounts if x["id"] == cur["acct"]), None)
            if old:
                kv_delete(old, key)
        reg["objects"][key] = {"acct": acc["id"], "size": size, "ct": ct, "sha": sha, "ts": int(time.time())}
        print(f"+ {key} → {acc['name']} ({acc['id'][:6]}) {size/1048576:.2f}MiB")
        return
    raise SystemExit(f"{key}: هیچ حسابی ظرفیت یا سهمیهٔ نوشتن ندارد (آخرین خطا: {last}). یک توکن حساب جدید به CF_ACCOUNTS اضافه کن.")


def storage_accounts(accounts):
    """حساب اصلی (Worker و برنامه‌های اشتراک) فایل رسانه نگه نمی‌دارد، مگر KV_PRIMARY_STORES_MEDIA=1 یا حساب دیگری نباشد."""
    if os.environ.get("KV_PRIMARY_STORES_MEDIA") == "1" or len(accounts) < 2:
        return accounts
    return accounts[1:]


def cmd_prepare(out):
    accounts = discover()
    with open(out, "w") as f:
        json.dump([{"id": a["id"], "token": a["token"], "ns": a["ns"]} for a in accounts], f)
    os.chmod(out, 0o600)
    print(f"::notice title=accounts::{len(accounts)} حساب KV آماده: " + ", ".join(f"{a['name']}({a['id'][:6]})" for a in accounts))


def cmd_sync(manifest):
    accounts = discover()
    storage = storage_accounts(accounts)
    reg = load_registry(accounts[0])
    exhausted = set()
    try:
        for line in open(manifest, encoding="utf8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, path, ct = line.split(" ", 2)
            with open(path, "rb") as f:
                put_object(accounts, reg, key, f.read(), ct, exhausted, storage)
    finally:
        kv_put(accounts[0], REGISTRY_KEY, json.dumps(reg).encode(), {"ct": "application/json"})
    cmd_status(accounts, reg)


def cmd_status(accounts=None, reg=None):
    accounts = accounts or discover()
    reg = reg or load_registry(accounts[0])
    st = {a["id"] for a in storage_accounts(accounts)}
    rows = [f"{a['name']}({a['id'][:6]}){'' if a['id'] in st else '[اصلی-بدون رسانه]'}: {usage(reg, a['id'])/1048576:.1f}/{BUDGET/1048576:.0f}MiB" for a in accounts]
    print("::notice title=kv-usage::" + " | ".join(rows) + f" | فایل‌ها: {len(reg['objects'])}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["prepare"] and len(a) == 3 and a[1] == "--out":
        cmd_prepare(a[2])
    elif a[:1] == ["sync"] and len(a) == 2:
        cmd_sync(a[1])
    elif a[:1] == ["status"]:
        cmd_status()
    else:
        print(__doc__)
        sys.exit(2)

// Worker «روایت ایران»: کاتالوگ، پوستر و ویدیوی امضاشدهٔ کوتاه‌عمر (پشتیبانی Range).
// فایل‌ها در Cloudflare KV چند حساب پخش شده‌اند (R2 نیاز به کارت دارد). جدول «کلید → حساب» در
// کلید __registry__ حساب اول است. secret با نام ACCOUNTS: [{id, token, ns}, ...] (حساب اول = اصلی).

const API = "https://api.cloudflare.com/client/v4";
const TTL_SECONDS = 600;
const ID_RE = /^[a-z0-9_-]{1,40}$/i;
const REGISTRY_KEY = "__registry__";
const enc = new TextEncoder();

async function hmacHex(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra } });

// کش درون‌حافظه‌ای (Cache API روی workers.dev کار نمی‌کند). فقط برای کم‌کردن فراخوانی‌های API؛ اجباری نیست.
const MEM_MAX = 48 * 1024 * 1024;
const mem = new Map(); // key -> {t, ttl, buf}
let memBytes = 0;
function memGet(k) {
  const e = mem.get(k);
  if (!e) return null;
  if (Date.now() - e.t > e.ttl) { mem.delete(k); memBytes -= e.buf.byteLength; return null; }
  return e.buf;
}
function memSet(k, buf, ttl) {
  if (buf.byteLength > MEM_MAX / 2) return;
  const old = mem.get(k);
  if (old) memBytes -= old.buf.byteLength;
  mem.set(k, { t: Date.now(), ttl, buf });
  memBytes += buf.byteLength;
  for (const [kk, v] of mem) { if (memBytes <= MEM_MAX) break; mem.delete(kk); memBytes -= v.buf.byteLength; }
}

let accountsParsed = null;
const accounts = (env) => (accountsParsed ??= JSON.parse(env.ACCOUNTS));

async function kvRead(acc, key) {
  const r = await fetch(`${API}/accounts/${acc.id}/storage/kv/namespaces/${acc.ns}/values/${encodeURIComponent(key)}`, {
    headers: { authorization: `Bearer ${acc.token}` },
  });
  if (!r.ok) { await r.body?.cancel(); return null; }
  return r.arrayBuffer();
}

async function registry(env) {
  const hit = memGet("reg");
  if (hit) return JSON.parse(new TextDecoder().decode(hit));
  const buf = await kvRead(accounts(env)[0], REGISTRY_KEY);
  if (!buf) return { objects: {} };
  memSet("reg", buf, 30_000);
  return JSON.parse(new TextDecoder().decode(buf));
}

async function entryFor(env, key) {
  const reg = await registry(env);
  const e = reg.objects[key];
  if (!e) return null;
  const acc = accounts(env).find((a) => a.id === e.acct);
  return acc ? { e, acc } : null;
}

async function loadBody(env, key, ent, ttlMs) {
  const ck = `${key}@${ent.e.sha}`;
  let buf = memGet(ck);
  if (!buf) {
    buf = await kvRead(ent.acc, key);
    if (buf) memSet(ck, buf, ttlMs);
  }
  return buf;
}

function parseRange(h, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(h || "");
  if (!m || (m[1] === "" && m[2] === "")) return null;
  let start, end;
  if (m[1] === "") { start = Math.max(0, size - parseInt(m[2], 10)); end = size - 1; }
  else { start = parseInt(m[1], 10); end = m[2] === "" ? size - 1 : Math.min(parseInt(m[2], 10), size - 1); }
  return start > end || start >= size ? "bad" : { start, end };
}

async function serveKey(req, env, key, cacheControl, ttlMs) {
  const ent = await entryFor(env, key);
  if (!ent) return new Response("Not found", { status: 404 });
  const etag = `"${ent.e.sha.slice(0, 32)}"`;
  const headers = new Headers({
    "content-type": ent.e.ct || "application/octet-stream",
    etag, "accept-ranges": "bytes", "cache-control": cacheControl, "x-content-type-options": "nosniff",
  });
  if (req.headers.get("if-none-match") === etag) return new Response(null, { status: 304, headers });
  const buf = await loadBody(env, key, ent, ttlMs);
  if (!buf) return new Response("Storage unavailable", { status: 503 });
  const size = buf.byteLength;
  const rg = req.headers.get("range") ? parseRange(req.headers.get("range"), size) : null;
  if (rg === "bad") { headers.set("content-range", `bytes */${size}`); return new Response(null, { status: 416, headers }); }
  if (rg) {
    headers.set("content-range", `bytes ${rg.start}-${rg.end}/${size}`);
    headers.set("content-length", String(rg.end - rg.start + 1));
    return new Response(req.method === "HEAD" ? null : buf.slice(rg.start, rg.end + 1), { status: 206, headers });
  }
  headers.set("content-length", String(size));
  return new Response(req.method === "HEAD" ? null : buf, { status: 200, headers });
}

export default {
  async fetch(req, env) {
    if (req.method !== "GET" && req.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
    const url = new URL(req.url);
    const p = url.pathname;

    if (p === "/catalog.json") return serveKey(req, env, "catalog.json", "no-cache", 20_000);

    let m = p.match(/^\/poster\/([a-z0-9_-]{1,40})\.jpg$/i);
    if (m) return serveKey(req, env, `posters/${m[1]}.jpg`, "public, max-age=86400", 600_000);

    m = p.match(/^\/play\/([a-z0-9_-]{1,40})$/i);
    if (m) {
      const given = req.headers.get("x-app-key") || "";
      if (!env.APP_KEY || !safeEqual(given, env.APP_KEY)) return json({ error: "forbidden" }, 403);
      const id = m[1];
      if (!ID_RE.test(id) || !(await entryFor(env, `videos/${id}.mp4`))) return json({ error: "not_found" }, 404);
      const exp = Math.floor(Date.now() / 1000) + TTL_SECONDS;
      const sig = await hmacHex(env.SIGN_SECRET, `${id}.${exp}`);
      return json({ url: `${url.origin}/media/${id}.mp4?exp=${exp}&sig=${sig}`, expires: exp });
    }

    m = p.match(/^\/media\/([a-z0-9_-]{1,40})\.mp4$/i);
    if (m) {
      const exp = parseInt(url.searchParams.get("exp") || "0", 10);
      const sig = url.searchParams.get("sig") || "";
      if (!exp || exp < Math.floor(Date.now() / 1000)) return new Response("Expired", { status: 403 });
      const want = await hmacHex(env.SIGN_SECRET, `${m[1]}.${exp}`);
      if (!safeEqual(sig, want)) return new Response("Forbidden", { status: 403 });
      return serveKey(req, env, `videos/${m[1]}.mp4`, "private, no-store", TTL_SECONDS * 1000);
    }

    return new Response("Not found", { status: 404 });
  },
};

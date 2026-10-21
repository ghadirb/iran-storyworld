// Worker «روایت ایران»: کاتالوگ، پوستر، و ویدیوی امضاشده با عمر کوتاه (پشتیبانی Range).
// فایل‌ها در R2 (binding: BUCKET). ویدیو فقط با لینک امضاشدهٔ ۱۰ دقیقه‌ای قابل دریافت است.

const TTL_SECONDS = 600;
const ID_RE = /^[a-z0-9_-]{1,40}$/i;
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

async function serveObject(req, env, key, cacheControl) {
  const obj = await env.BUCKET.get(key, { range: req.headers, onlyIf: req.headers });
  if (!obj) return new Response("Not found", { status: 404 });
  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag", obj.httpEtag);
  headers.set("accept-ranges", "bytes");
  headers.set("cache-control", cacheControl);
  headers.set("x-content-type-options", "nosniff");
  if (!obj.body) return new Response(null, { status: 304, headers });
  let status = 200;
  if (obj.range && req.headers.get("range")) {
    status = 206;
    const r = obj.range;
    let start, end;
    if (r.suffix !== undefined) { start = obj.size - r.suffix; end = obj.size - 1; }
    else { start = r.offset ?? 0; end = r.length !== undefined ? start + r.length - 1 : obj.size - 1; }
    headers.set("content-range", `bytes ${start}-${end}/${obj.size}`);
    headers.set("content-length", String(end - start + 1));
  } else {
    headers.set("content-length", String(obj.size));
  }
  return new Response(req.method === "HEAD" ? null : obj.body, { status, headers });
}

export default {
  async fetch(req, env) {
    if (req.method !== "GET" && req.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
    const url = new URL(req.url);
    const p = url.pathname;

    // کاتالوگ (همیشه تازه)
    if (p === "/catalog.json") return serveObject(req, env, "catalog.json", "no-cache");

    // پوستر (غیرحساس، قابل کش)
    let m = p.match(/^\/poster\/([a-z0-9_-]{1,40})\.jpg$/i);
    if (m) return serveObject(req, env, `posters/${m[1]}.jpg`, "public, max-age=86400");

    // درخواست لینک پخش: فقط با کلید برنامه
    m = p.match(/^\/play\/([a-z0-9_-]{1,40})$/i);
    if (m) {
      const given = req.headers.get("x-app-key") || "";
      if (!env.APP_KEY || !safeEqual(given, env.APP_KEY)) return json({ error: "forbidden" }, 403);
      const id = m[1];
      if (!ID_RE.test(id) || !(await env.BUCKET.head(`videos/${id}.mp4`))) return json({ error: "not_found" }, 404);
      const exp = Math.floor(Date.now() / 1000) + TTL_SECONDS;
      const sig = await hmacHex(env.SIGN_SECRET, `${id}.${exp}`);
      return json({ url: `${url.origin}/media/${id}.mp4?exp=${exp}&sig=${sig}`, expires: exp });
    }

    // خود ویدیو: فقط با امضای معتبر و منقضی‌نشده
    m = p.match(/^\/media\/([a-z0-9_-]{1,40})\.mp4$/i);
    if (m) {
      const exp = parseInt(url.searchParams.get("exp") || "0", 10);
      const sig = url.searchParams.get("sig") || "";
      if (!exp || exp < Math.floor(Date.now() / 1000)) return new Response("Expired", { status: 403 });
      const want = await hmacHex(env.SIGN_SECRET, `${m[1]}.${exp}`);
      if (!safeEqual(sig, want)) return new Response("Forbidden", { status: 403 });
      return serveObject(req, env, `videos/${m[1]}.mp4`, "private, no-store");
    }

    return new Response("Not found", { status: 404 });
  },
};

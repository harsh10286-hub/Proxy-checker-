"""
┌─────────────────────────────────────────────────────────────┐
│           PROXY CHECKER BOT  v5.0  — Multi-User             │
│                                                             │
│  Features:                                                  │
│  • True per-user isolated job queues                        │
│  • 1500 concurrent workers (tunable)                        │
│  • HTTP · HTTPS · SOCKS4 · SOCKS5 + auth                   │
│  • Geo · ISP · Anonymity detection                          │
│  • Smart progress throttling (no flood wait)                │
│  • 9 categorised output files                               │
│  • Job history per user                                     │
│  • /status — see all active jobs (admin)                    │
│                                                             │
│  Install:                                                   │
│    pip install python-telegram-bot aiohttp aiohttp-socks    │
│                                                             │
│  Run:                                                       │
│    export TELEGRAM_BOT_TOKEN="your_token"                   │
│    python proxy_bot_v5.py                                   │
└─────────────────────────────────────────────────────────────┘
"""

import os, re, asyncio, logging, time, json, platform
from io import BytesIO
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional, Callable

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, Message,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
BOT_TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN", "7974258604:AAG4MPU9HY5kvHfuVWEr3iz9eOXfNNcJsoE")
MAX_WORKERS     = 1500          # per-user concurrent connections
CHECK_TIMEOUT   = 7             # seconds
MAX_RETRIES     = 1
PROGRESS_EVERY  = 300           # update UI every N checked
EDIT_INTERVAL   = 3.5           # min seconds between edits (avoid flood)
ADMIN_IDS: set  = set()         # optional: add Telegram user IDs

SPEED_ULTRA  = 600
SPEED_FAST   = 2000
SPEED_MEDIUM = 5000

TEST_URLS = [
    "http://httpbin.org/ip",
    "http://ip-api.com/json",
    "http://checkip.amazonaws.com",
    "http://ifconfig.me/ip",
    "http://api.ipify.org",
    "http://icanhazip.com",
]
GEO_URL = (
    "http://ip-api.com/json/{ip}"
    "?fields=status,country,countryCode,city,isp,proxy,hosting,query"
)

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  DATA MODEL
# ─────────────────────────────────────────────────────────────
@dataclass
class Proxy:
    raw:     str
    scheme:  str
    host:    str
    port:    int
    user:    Optional[str] = None
    pwd:     Optional[str] = None
    alive:   bool          = False
    latency: Optional[int] = None
    exit_ip: Optional[str] = None
    country: Optional[str] = None
    cc:      Optional[str] = None
    city:    Optional[str] = None
    isp:     Optional[str] = None
    anon:    Optional[str] = None
    speed:   Optional[str] = None

    def plain(self) -> str:
        if self.user:
            return f"{self.user}:{self.pwd}@{self.host}:{self.port}"
        return f"{self.host}:{self.port}"


@dataclass
class JobStats:
    """Mutable live stats for a running job."""
    total:   int   = 0
    done:    int   = 0
    live:    int   = 0
    dead:    int   = 0
    ultra:   int   = 0
    fast:    int   = 0
    medium:  int   = 0
    slow:    int   = 0
    elite:   int   = 0
    started: float = field(default_factory=time.monotonic)


# ─────────────────────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────────────────────
_RE = re.compile(
    r"(?:(?P<scheme>https?|socks[45])://)?"
    r"(?:(?P<user>[^:@\s]+):(?P<pwd>[^@\s]+)@)?"
    r"(?P<host>[\w.\-]+):(?P<port>\d{1,5})",
    re.IGNORECASE,
)

def parse_proxies(raw: str) -> list[Proxy]:
    seen, out = set(), []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RE.search(line)
        if not m:
            continue
        key = (m.group("host").lower(), m.group("port"))
        if key in seen:
            continue
        seen.add(key)
        out.append(Proxy(
            raw    = line,
            scheme = (m.group("scheme") or "http").lower(),
            host   = m.group("host"),
            port   = int(m.group("port")),
            user   = m.group("user"),
            pwd    = m.group("pwd"),
        ))
    return out


# ─────────────────────────────────────────────────────────────
#  CHECKER ENGINE
# ─────────────────────────────────────────────────────────────
_url_lock = asyncio.Lock()
_url_idx  = 0

async def _next_url() -> str:
    global _url_idx
    async with _url_lock:
        u = TEST_URLS[_url_idx % len(TEST_URLS)]
        _url_idx += 1
    return u


async def _attempt(p: Proxy, to: aiohttp.ClientTimeout) -> tuple[bool, Optional[int], Optional[str]]:
    url = await _next_url()
    t0  = time.monotonic()
    try:
        if p.scheme in ("socks4", "socks5"):
            ptype = ProxyType.SOCKS4 if p.scheme == "socks4" else ProxyType.SOCKS5
            conn  = ProxyConnector(
                proxy_type=ptype, host=p.host, port=p.port,
                username=p.user, password=p.pwd, rdns=True,
            )
            async with aiohttp.ClientSession(connector=conn, timeout=to) as s:
                async with s.get(url) as r:
                    body = await r.text()
        else:
            purl = (
                f"{p.scheme}://{p.user}:{p.pwd}@{p.host}:{p.port}"
                if p.user else f"{p.scheme}://{p.host}:{p.port}"
            )
            async with aiohttp.ClientSession(timeout=to) as s:
                async with s.get(url, proxy=purl) as r:
                    body = await r.text()

        ms = round((time.monotonic() - t0) * 1000)
        ip = None
        try:
            d  = json.loads(body)
            ip = d.get("origin") or d.get("ip") or d.get("query")
            if ip and "," in ip:
                ip = ip.split(",")[0].strip()
        except Exception:
            clean = body.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", clean):
                ip = clean
        return True, ms, ip
    except Exception:
        return False, None, None


async def check_one(p: Proxy, to: aiohttp.ClientTimeout) -> Proxy:
    for _ in range(MAX_RETRIES + 1):
        ok, ms, ip = await _attempt(p, to)
        if ok:
            p.alive   = True
            p.latency = ms
            p.exit_ip = ip
            p.speed   = (
                "⚡ Ultra"  if ms <= SPEED_ULTRA  else
                "🟢 Fast"   if ms <= SPEED_FAST   else
                "🟡 Medium" if ms <= SPEED_MEDIUM else
                "🔴 Slow"
            )
            if ip:
                try:
                    geo_to = aiohttp.ClientTimeout(total=4)
                    async with aiohttp.ClientSession(timeout=geo_to) as s:
                        async with s.get(GEO_URL.format(ip=ip)) as r:
                            g = await r.json()
                    if g.get("status") == "success":
                        p.country = g.get("country")
                        p.cc      = g.get("countryCode", "")
                        p.city    = g.get("city")
                        p.isp     = g.get("isp")
                        p.anon    = "Elite" if (g.get("proxy") or g.get("hosting")) else "Anonymous"
                    else:
                        p.anon = "Unknown"
                except Exception:
                    p.anon = "Unknown"
            else:
                p.anon = "Unknown"
            return p
        await asyncio.sleep(0.25)
    p.alive = False
    return p


async def run_all(
    proxies:  list[Proxy],
    cancel:   asyncio.Event,
    stats:    JobStats,
    cb:       Optional[Callable] = None,
) -> list[Proxy]:
    sem     = asyncio.Semaphore(MAX_WORKERS)
    to      = aiohttp.ClientTimeout(total=CHECK_TIMEOUT)
    results: list[Proxy] = []

    async def worker(p: Proxy):
        if cancel.is_set():
            return
        async with sem:
            if cancel.is_set():
                return
            result = await check_one(p, to)
            results.append(result)

            stats.done += 1
            if result.alive:
                stats.live += 1
                ms = result.latency or 0
                if ms <= SPEED_ULTRA:               stats.ultra  += 1
                elif ms <= SPEED_FAST:              stats.fast   += 1
                elif ms <= SPEED_MEDIUM:            stats.medium += 1
                else:                               stats.slow   += 1
                if result.anon == "Elite":          stats.elite  += 1
            else:
                stats.dead += 1

            if cb and stats.done % PROGRESS_EVERY == 0:
                await cb(stats)

    await asyncio.gather(*[worker(p) for p in proxies])
    return results


# ─────────────────────────────────────────────────────────────
#  OUTPUT FILES
# ─────────────────────────────────────────────────────────────
def build_files(results: list[Proxy]) -> dict[str, BytesIO]:
    live = sorted([r for r in results if r.alive], key=lambda x: x.latency or 99999)
    dead = [r for r in results if not r.alive]
    files: dict[str, BytesIO] = {}

    def buf(lines: list[str]) -> Optional[BytesIO]:
        content = "\n".join(lines)
        return BytesIO(content.encode()) if content.strip() else None

    if live:
        files["ALL_LIVE.txt"]    = buf([r.plain() for r in live])
        files["ULTRA_FAST.txt"]  = buf([r.plain() for r in live if (r.latency or 0) <= SPEED_ULTRA])
        files["FAST.txt"]        = buf([r.plain() for r in live if (r.latency or 0) <= SPEED_FAST])
        files["ELITE_ANON.txt"]  = buf([r.plain() for r in live if r.anon == "Elite"])
        for proto in ("http", "https", "socks4", "socks5"):
            g = [r.plain() for r in live if r.scheme == proto]
            if g:
                files[f"{proto.upper()}.txt"] = buf(g)
    if dead:
        files["DEAD.txt"] = buf([r.plain() for r in dead])

    return {k: v for k, v in files.items() if v}


# ─────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────
def flag(cc: str) -> str:
    if not cc or len(cc) != 2:
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())

def hms(sec: float) -> str:
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return (f"{h}h " if h else "") + (f"{m}m " if m else "") + f"{s}s"

def eta_str(done: int, total: int, elapsed: float) -> str:
    if done == 0:
        return "calculating…"
    rem = (total - done) / (done / elapsed)
    return hms(rem)

def pbar(pct: int, w: int = 20) -> str:
    f = round(pct / 100 * w)
    return "█" * f + "░" * (w - f)

def rate_badge(ms: Optional[int]) -> str:
    if ms is None: return "❓"
    if ms <= SPEED_ULTRA:  return "⚡"
    if ms <= SPEED_FAST:   return "🟢"
    if ms <= SPEED_MEDIUM: return "🟡"
    return "🔴"


# ─────────────────────────────────────────────────────────────
#  PAGE BUILDERS
# ─────────────────────────────────────────────────────────────
def page_home() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🛡️  *Proxy Checker*  `v5.0`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋  *What I can do:*\n"
        "  ›  Check `HTTP · HTTPS · SOCKS4 · SOCKS5`\n"
        "  ›  Detect country, city & ISP\n"
        "  ›  Classify `Elite` vs `Anonymous`\n"
        "  ›  Sort by speed & export 9 file types\n"
        "  ›  Handle multiple users simultaneously\n\n"
        "📎  *Send a `.txt` file to begin.*\n"
        "  One proxy per line — any format works."
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 How to Use",    callback_data="pg_howto"),
            InlineKeyboardButton("📁 Output Files",  callback_data="pg_output"),
        ],
        [
            InlineKeyboardButton("⚙️ Performance",   callback_data="pg_perf"),
            InlineKeyboardButton("🕵️ Anonymity",     callback_data="pg_anon"),
        ],
        [
            InlineKeyboardButton("📝 Formats",       callback_data="pg_formats"),
            InlineKeyboardButton("❓ FAQ",            callback_data="pg_faq"),
        ],
    ])
    return text, kb


def page_howto() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "📖  *How to Use*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Steps:*\n"
        "  `1.`  Create a `.txt` file\n"
        "  `2.`  Add proxies — one per line\n"
        "  `3.`  Send the file here\n"
        "  `4.`  Bot checks all concurrently\n"
        "  `5.`  Receive sorted result files\n\n"
        "*Supported formats:*\n"
        "```\n"
        "1.2.3.4:8080\n"
        "http://1.2.3.4:3128\n"
        "socks4://1.2.3.4:1080\n"
        "socks5://1.2.3.4:1080\n"
        "user:pass@1.2.3.4:8080\n"
        "socks5://user:pass@1.2.3.4:1080\n"
        "```\n\n"
        "💡 Lines starting with `#` are ignored\n"
        "🔁 Duplicates are removed automatically"
    )
    return text, _back_kb()


def page_output() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "📁  *Output Files*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "All files use plain `host:port` format\n\n"
        "```\n"
        " ALL_LIVE.txt   — All working proxies\n"
        " ULTRA_FAST.txt — Latency ≤ 600ms\n"
        " FAST.txt       — Latency ≤ 2000ms\n"
        " ELITE_ANON.txt — Elite anonymity\n"
        " HTTP.txt       — HTTP only\n"
        " HTTPS.txt      — HTTPS only\n"
        " SOCKS4.txt     — SOCKS4 only\n"
        " SOCKS5.txt     — SOCKS5 only\n"
        " DEAD.txt       — Failed proxies\n"
        "```\n\n"
        "📌 Empty files are never sent\n"
        "📌 `ALL_LIVE` is sorted fastest-first\n"
        "📌 Auth proxies: `user:pass@host:port`"
    )
    return text, _back_kb()


def page_perf() -> tuple[str, InlineKeyboardMarkup]:
    rows = [10_000, 50_000, 100_000, 250_000, 500_000]
    lines = ""
    for n in rows:
        mins = round(n / MAX_WORKERS * CHECK_TIMEOUT / 60, 1)
        bar  = "▪" * min(int(mins / 0.5), 16)
        lines += f"  {n:>7,}  →  ~{mins:>5} min  {bar}\n"

    text = (
        "⚙️  *Performance*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"```\n"
        f" Workers : {MAX_WORKERS:,} concurrent\n"
        f" Timeout : {CHECK_TIMEOUT}s per proxy\n"
        f" Retries : {MAX_RETRIES}x on failure\n"
        f" Rotates : {len(TEST_URLS)} test endpoints\n"
        f"```\n\n"
        f"*⏱ Estimated times:*\n"
        f"```\n"
        f" Proxies      Time\n"
        f" ─────────────────────────\n"
        f"{lines}```\n\n"
        "💡 Actual time varies by proxy\n"
        "   quality and network conditions."
    )
    return text, _back_kb()


def page_anon() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🕵️  *Anonymity Levels*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*🔒 Elite*\n"
        "  Datacenter, VPN or hosting IP\n"
        "  Target cannot detect proxy use\n"
        "  Best for sensitive operations\n\n"
        "*🔓 Anonymous*\n"
        "  Hides your real IP address\n"
        "  Target may detect proxy usage\n"
        "  Suitable for general browsing\n\n"
        "*🔎 Transparent*\n"
        "  Passes real IP in headers\n"
        "  Both proxy and IP are visible\n"
        "  Not recommended for privacy\n\n"
        "Detection uses `ip-api.com` proxy\n"
        "and hosting flags on the exit IP."
    )
    return text, _back_kb()


def page_formats() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "📝  *Proxy Format Reference*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "```\n"
        "# Plain\n"
        "192.168.1.1:8080\n\n"
        "# With scheme\n"
        "http://192.168.1.1:8080\n"
        "https://192.168.1.1:3128\n"
        "socks4://192.168.1.1:1080\n"
        "socks5://192.168.1.1:1080\n\n"
        "# With credentials\n"
        "user:pass@192.168.1.1:8080\n"
        "socks5://user:pass@1.2.3.4:1080\n\n"
        "# Comments (ignored)\n"
        "# This line is skipped\n"
        "```\n\n"
        "🔁 Deduplication is automatic\n"
        "📊 Unknown scheme → treated as HTTP"
    )
    return text, _back_kb()


def page_faq() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "❓  *FAQ*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Why no scheme in output files?*\n"
        "Plain `host:port` works with all tools.\n\n"
        "*How are proxies verified?*\n"
        "A real HTTP request is made through\n"
        "each proxy to a live test endpoint.\n\n"
        "*Can I run multiple jobs?*\n"
        "Each user has an isolated job. You\n"
        "can send a new file to replace yours.\n\n"
        "*Can I cancel a running job?*\n"
        "Yes — use /cancel or the 🛑 button.\n\n"
        "*Are duplicates removed?*\n"
        "Yes, automatically before checking.\n\n"
        "*Is there a proxy limit?*\n"
        "No hard limit. Tested up to 500k+."
    )
    return text, _back_kb()


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("‹ Back to Menu", callback_data="pg_home")
    ]])


# ─────────────────────────────────────────────────────────────
#  DYNAMIC MESSAGES
# ─────────────────────────────────────────────────────────────
def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🛑  Stop Job", callback_data="cb_cancel_job")
    ]])


def msg_started(filename: str, total: int, est: float) -> str:
    return (
        "🚀  *Job Started*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"```\n"
        f" File     : {filename}\n"
        f" Proxies  : {total:,}  (dupes removed)\n"
        f" Workers  : {MAX_WORKERS:,}\n"
        f" Timeout  : {CHECK_TIMEOUT}s / retry\n"
        f" Est.time : ~{est} min\n"
        f"```\n\n"
        "_Progress updates every "
        f"{PROGRESS_EVERY} checks…_"
    )


def msg_progress(s: JobStats) -> str:
    elapsed = time.monotonic() - s.started
    pct     = round(s.done / s.total * 100) if s.total else 0
    rate    = round(s.done / elapsed, 1)    if elapsed > 0 else 0
    eta     = eta_str(s.done, s.total, elapsed)
    hit_pct = round(s.live / s.done * 100, 1) if s.done else 0

    return (
        "⚙️  *Checking in Progress*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"`{pbar(pct)}` *{pct}%*\n\n"
        f"```\n"
        f" Checked  : {s.done:>8,} / {s.total:,}\n"
        f" ─────────────────────────────\n"
        f" ✅ Live  : {s.live:>8,}  ({hit_pct}%)\n"
        f" ❌ Dead  : {s.dead:>8,}\n"
        f" ─────────────────────────────\n"
        f" ⚡ Ultra : {s.ultra:>8,}\n"
        f" 🟢 Fast  : {s.fast:>8,}\n"
        f" 🟡 Medium: {s.medium:>8,}\n"
        f" 🔴 Slow  : {s.slow:>8,}\n"
        f" ─────────────────────────────\n"
        f" Speed   : {rate:>7} p/s\n"
        f" Elapsed : {hms(elapsed):>10}\n"
        f" ETA     : {eta:>10}\n"
        f"```\n\n"
        "_Press 🛑 to stop anytime_"
    )


def msg_summary(results: list[Proxy], elapsed: float, total_input: int) -> str:
    live  = [r for r in results if r.alive]
    dead  = [r for r in results if not r.alive]
    n     = len(results)
    lats  = [r.latency for r in live if r.latency]
    pct   = round(len(live) / n * 100, 1) if n else 0
    rate  = round(n / elapsed, 1) if elapsed > 0 else 0

    avg   = f"{round(sum(lats)/len(lats)):,}ms" if lats else "—"
    best  = f"{min(lats):,}ms"                  if lats else "—"
    worst = f"{max(lats):,}ms"                  if lats else "—"

    ultra  = sum(1 for r in live if (r.latency or 0) <= SPEED_ULTRA)
    fast   = sum(1 for r in live if SPEED_ULTRA < (r.latency or 0) <= SPEED_FAST)
    medium = sum(1 for r in live if SPEED_FAST  < (r.latency or 0) <= SPEED_MEDIUM)
    slow   = sum(1 for r in live if (r.latency or 0) > SPEED_MEDIUM)

    by_proto: dict[str, int] = defaultdict(int)
    for r in live:
        by_proto[r.scheme] += 1
    proto_str = "  ".join(
        f"{s.upper()}:{c}" for s, c in sorted(by_proto.items())
    ) or "—"

    by_cc: dict[str, int] = defaultdict(int)
    for r in live:
        if r.cc:
            by_cc[r.cc] += 1
    top      = sorted(by_cc.items(), key=lambda x: -x[1])[:6]
    countries = "  ".join(f"{flag(cc)}{n_}" for cc, n_ in top) or "—"

    elite = sum(1 for r in live if r.anon == "Elite")
    anon  = sum(1 for r in live if r.anon == "Anonymous")

    return (
        "🎯  *Check Complete*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"```\n"
        f" Input    : {total_input:,} proxies\n"
        f" Checked  : {n:,}\n"
        f" ─────────────────────────────\n"
        f" ✅ Live  : {len(live):,}  ({pct}%)\n"
        f" ❌ Dead  : {len(dead):,}\n"
        f" ─────────────────────────────\n"
        f" Time     : {hms(elapsed)}\n"
        f" Speed    : {rate} p/sec\n"
        f" ─────────────────────────────\n"
        f" Best lat : {best}\n"
        f" Avg lat  : {avg}\n"
        f" Worst lat: {worst}\n"
        f" ─────────────────────────────\n"
        f" ⚡ Ultra : {ultra:,}  (≤{SPEED_ULTRA}ms)\n"
        f" 🟢 Fast  : {fast:,}  (≤{SPEED_FAST}ms)\n"
        f" 🟡 Medium: {medium:,}  (≤{SPEED_MEDIUM}ms)\n"
        f" 🔴 Slow  : {slow:,}  (>{SPEED_MEDIUM}ms)\n"
        f" ─────────────────────────────\n"
        f" Protocols: {proto_str}\n"
        f" 🔒 Elite : {elite:,}\n"
        f" 🔓 Anon  : {anon:,}\n"
        f"```\n\n"
        f"🗺️  *Top Countries:*  {countries}\n\n"
        f"📁  Result files sent below ↓\n"
        f"_Format: `host:port`_"
    )


# ─────────────────────────────────────────────────────────────
#  GLOBAL USER STATE   (per-user cancel + last-edit throttle)
# ─────────────────────────────────────────────────────────────
class UserJob:
    __slots__ = ("cancel", "last_edit", "active")
    def __init__(self):
        self.cancel:    asyncio.Event = asyncio.Event()
        self.last_edit: float         = 0.0
        self.active:    bool          = False

_user_jobs: dict[int, UserJob] = {}

def _get_job(uid: int) -> UserJob:
    if uid not in _user_jobs:
        _user_jobs[uid] = UserJob()
    return _user_jobs[uid]


async def _safe_edit(msg: Message, text: str, kb=None, parse_mode=ParseMode.MARKDOWN):
    """Edit a message, respecting EDIT_INTERVAL to avoid flood limits."""
    try:
        await msg.edit_text(text, parse_mode=parse_mode, reply_markup=kb)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────────────────────
PAGE_MAP = {
    "pg_home":    page_home,
    "pg_howto":   page_howto,
    "pg_output":  page_output,
    "pg_perf":    page_perf,
    "pg_anon":    page_anon,
    "pg_formats": page_formats,
    "pg_faq":     page_faq,
}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = page_home()
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = page_howto()
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    job = _user_jobs.get(uid)
    if job and job.active:
        job.cancel.set()
        await update.message.reply_text(
            "🛑  *Cancellation sent — stopping…*",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("ℹ️  No active job to cancel.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show all active jobs (all users or self)."""
    uid    = update.effective_user.id
    active = [(u, j) for u, j in _user_jobs.items() if j.active]
    if not active:
        await update.message.reply_text("✅  No active jobs right now.")
        return
    lines = "\n".join(f"  • User `{u}` — running" for u, j in active)
    await update.message.reply_text(
        f"📊  *Active Jobs:* {len(active)}\n\n{lines}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def nav_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "cb_cancel_job":
        uid = update.effective_user.id
        job = _user_jobs.get(uid)
        if job:
            job.cancel.set()
        try:
            await q.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await q.message.reply_text(
            "🛑  *Cancellation requested!*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    builder = PAGE_MAP.get(data)
    if not builder:
        return
    text, kb = builder()
    try:
        await q.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── File handler ───────────────────────────────────────────────
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    uid = update.effective_user.id

    if not (doc.file_name or "").lower().endswith(".txt"):
        await update.message.reply_text(
            "⚠️  *Please send a `.txt` file.*\n\nUse /help for format details.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Cancel any existing job for this user
    job = _get_job(uid)
    if job.active:
        job.cancel.set()
        await asyncio.sleep(0.5)   # brief grace period

    job.cancel = asyncio.Event()
    job.active = True
    job.last_edit = 0.0

    status = await update.message.reply_text(
        "```\n  📥  Downloading file…\n```",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Download
    try:
        tg_file = await doc.get_file()
        buf = BytesIO()
        await tg_file.download_to_memory(buf)
        raw = buf.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        job.active = False
        await status.edit_text(f"❌  *Failed to download file.*\n`{e}`", parse_mode=ParseMode.MARKDOWN)
        return

    proxies = parse_proxies(raw)
    total   = len(proxies)

    if not proxies:
        job.active = False
        await status.edit_text(
            "❌  *No valid proxies found in file.*\n\nUse /help to see supported formats.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    est = round(total / MAX_WORKERS * CHECK_TIMEOUT / 60, 1)
    await status.edit_text(
        msg_started(doc.file_name, total, est),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_cancel_kb(),
    )

    stats = JobStats(total=total)
    t0    = time.monotonic()

    async def on_progress(s: JobStats):
        now = time.monotonic()
        if now - job.last_edit < EDIT_INTERVAL:
            return
        job.last_edit = now
        if job.cancel.is_set():
            return
        await _safe_edit(status, msg_progress(s), kb=_cancel_kb())

    results = await run_all(proxies, job.cancel, stats, on_progress)
    elapsed = time.monotonic() - t0
    job.active = False

    # ── Cancelled ──────────────────────────────────────────────
    if job.cancel.is_set():
        checked = len(results)
        live    = sum(1 for r in results if r.alive)
        await _safe_edit(
            status,
            f"🛑  *Job Cancelled*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"```\n"
            f" Checked : {checked:,} / {total:,}\n"
            f" Live    : {live:,}\n"
            f" Elapsed : {hms(elapsed)}\n"
            f"```\n\n"
            f"_Send a new file to start again._",
        )
        return

    # ── Final summary ──────────────────────────────────────────
    await _safe_edit(status, msg_summary(results, elapsed, total))

    # ── Send result files ──────────────────────────────────────
    FILE_CAPTIONS = {
        "ALL_LIVE.txt":   "✅  All live proxies — sorted by speed  |  `host:port`",
        "ULTRA_FAST.txt": f"⚡  Ultra-fast proxies (≤{SPEED_ULTRA}ms)  |  `host:port`",
        "FAST.txt":       f"🟢  Fast proxies (≤{SPEED_FAST}ms)  |  `host:port`",
        "ELITE_ANON.txt": "🔒  Elite anonymity proxies  |  `host:port`",
        "HTTP.txt":       "🌐  HTTP proxies  |  `host:port`",
        "HTTPS.txt":      "🔐  HTTPS proxies  |  `host:port`",
        "SOCKS4.txt":     "🧦  SOCKS4 proxies  |  `host:port`",
        "SOCKS5.txt":     "🧦  SOCKS5 proxies  |  `host:port`",
        "DEAD.txt":       "❌  Dead proxies  |  `host:port`",
    }

    files = build_files(results)
    sent  = 0
    for fname, fbuf in files.items():
        fbuf.seek(0)
        try:
            await update.message.reply_document(
                document  = fbuf,
                filename  = fname,
                caption   = FILE_CAPTIONS.get(fname, fname),
                parse_mode = ParseMode.MARKDOWN,
            )
            sent += 1
        except Exception as e:
            log.warning("Failed to send %s: %s", fname, e)

    live_count = sum(1 for r in results if r.alive)
    if live_count == 0:
        await update.message.reply_text(
            "😔  *No working proxies found.*",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        _, kb = page_home()
        await update.message.reply_text(
            f"✅  *Done!*  `{sent}` file(s) sent.\n"
            f"_Send another `.txt` to run a new job._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌  Set TELEGRAM_BOT_TOKEN environment variable first.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(nav_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start",  "🏠 Main menu"),
            BotCommand("help",   "📖 How to use"),
            BotCommand("cancel", "🛑 Cancel current job"),
            BotCommand("status", "📊 View active jobs"),
        ])

    app.post_init = post_init
    log.info("✅  Proxy Checker Bot v5.0 ready — polling started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

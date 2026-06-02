"""
HFF Banner API — TEAMX uslubida
/banner?uid=UID → PNG rasm

Layout:
┌──────────┬──────────────────────────────────────────┐
│          │  ┌ Daraja (EXP): 597136                  │
│  avatar  │  ├─ Yoqtirishlar: 8 937                  │
│          │  ├─ UID: 9354867157                      │
│  (yashil │  └─ Bio: ...                             │
│  ramka)  │                                          │
├──────────┴──────────────────────────────────────────┤
│  LvL. 56      HeisenbergFF  |  Gildiya              │
└─────────────────────────────────────────────────────┘
"""
import io, os, asyncio, httpx
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ═══════════════════════════════════════════════════════
#   SOZLAMALAR
# ═══════════════════════════════════════════════════════
INFO_API_URL  = "https://hff-infoapi.onrender.com/player-info"
FF_RESOURCES  = "https://raw.githubusercontent.com/0xme/ff-resources/main/pngs/300x300"
FALLBACK_CDN  = "https://raw.githubusercontent.com/ShahGCreator/icon/main/PNG"
ITEM_DATA_URL = "https://raw.githubusercontent.com/0xme/ItemID2/main/assets/itemData.json"

# Canvas
CW, CH = 1850, 800

# Ranglar
GREEN = (0, 210, 80)     # Asosiy rang (chegara, LvL, separator)
WHITE = (255, 255, 255)  # Ism, sarlavhalar
GRAY  = (180, 180, 195)  # Gildiya, qo'shimcha ma'lumotlar
BLACK = (0, 0, 0)
DARK  = (8, 8, 15)

# Koordinatalar
AV_X, AV_Y, AV_W, AV_H = 80, 80, 520, 520   # Avatar
BN_X, BN_Y              = 640, 80            # Banner (ma'lumotlar) boshlanishi
BN_W                     = CW - BN_X - 20   # Banner kengligi
BN_H                     = AV_H             # Banner balandligi
BOT_Y                    = AV_Y + AV_H + 20 # Pastki qator Y
BOT_H                    = CH - BOT_Y - 10  # Pastki qator balandligi

BASE_DIR  = os.path.dirname(__file__)
FONT_BOLD = os.path.join(BASE_DIR, "font_bold.ttf")
FONT_REG  = os.path.join(BASE_DIR, "font_regular.ttf")

_item_cache: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_item_data()
    yield
    await client.aclose()
    pool.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
client = httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"},
                            timeout=30.0, follow_redirects=True)
pool = ThreadPoolExecutor(max_workers=4)


async def load_item_data():
    try:
        r = await client.get(ITEM_DATA_URL)
        if r.status_code == 200:
            for item in r.json():
                _item_cache[str(item.get("itemID",""))] = item.get("icon","")
    except Exception as e:
        print(f"itemData: {e}")


# ═══════════════════════════════════════════════════════
#   YORDAMCHILAR
# ═══════════════════════════════════════════════════════
def fnt(size, bold=True):
    p = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


def fit_text(draw, text, max_size, max_w, bold=True):
    size = max_size
    f = fnt(size, bold)
    while size > 20:
        bb = draw.textbbox((0,0), text, font=f)
        if bb[2]-bb[0] <= max_w:
            break
        size -= 4
        f = fnt(size, bold)
    return f


def stroke_text(draw, x, y, text, f, color, sw=3):
    if not text: return
    sc = (*BLACK, 200)
    for dx in range(-sw, sw+1):
        for dy in range(-sw, sw+1):
            if dx or dy:
                draw.text((x+dx, y+dy), text, font=f, fill=sc)
    draw.text((x, y), text, font=f, fill=color)


async def fetch_icon(icon_name=None, item_id=None) -> bytes|None:
    if icon_name:
        try:
            r = await client.get(f"{FF_RESOURCES}/{icon_name}.png")
            if r.status_code == 200:
                return r.content
        except Exception:
            pass
    if item_id:
        try:
            r = await client.get(f"{FALLBACK_CDN}/{item_id}.png")
            if r.status_code == 200:
                return b"BORDERED:" + r.content
        except Exception:
            pass
    return None


def remove_border(img):
    w, h = img.size
    b = int(min(w,h) * 0.128)
    return img.crop((b, b, w-b, h-b))


def to_img(data, size, fallback=DARK):
    if not data:
        return Image.new("RGB", size, fallback)
    try:
        strip = data.startswith(b"BORDERED:")
        raw   = data[9:] if strip else data
        img   = Image.open(io.BytesIO(raw)).convert("RGB")
        if strip:
            img = remove_border(img)
        aw, ah = img.size
        tw, th = size
        if aw/ah > tw/th:
            nw = int(ah*tw/th)
            img = img.crop(((aw-nw)//2, 0, (aw-nw)//2+nw, ah))
        else:
            nh = int(aw*th/tw)
            img = img.crop((0, (ah-nh)//2, aw, (ah-nh)//2+nh))
        return img.resize(size, Image.LANCZOS)
    except Exception:
        return Image.new("RGB", size, fallback)


# ═══════════════════════════════════════════════════════
#   TEMPLATE
# ═══════════════════════════════════════════════════════
def make_template() -> Image.Image:
    canvas = Image.new("RGB", (CW, CH), DARK)
    draw   = ImageDraw.Draw(canvas)

    # Fon gradient
    for y in range(CH):
        t = y/CH
        r = int(DARK[0] + 15*t)
        g = int(DARK[1] + 10*t)
        b = int(DARK[2] + 25*t)
        draw.line([(0,y),(CW,y)], fill=(r,g,b))

    # Avatar ramkasi (tashqi + ichki)
    draw.rounded_rectangle(
        [AV_X-10, AV_Y-10, AV_X+AV_W+10, AV_Y+AV_H+10],
        radius=22, fill=(5,5,12), outline=GREEN, width=4)

    # Ma'lumotlar qismi ramkasi
    draw.rounded_rectangle(
        [BN_X-6, BN_Y-6, BN_X+BN_W+6, BN_Y+BN_H+6],
        radius=16, fill=(5,5,12), outline=(*GREEN, 60), width=2)

    # Pastki panel
    draw.rectangle([0, BOT_Y-5, CW, CH], fill=(5,5,12))
    draw.line([(0, BOT_Y-5), (CW, BOT_Y-5)], fill=GREEN, width=3)

    # Tashqi chegara — qalin
    draw.rectangle([(0,0),(CW,5)],    fill=GREEN)
    draw.rectangle([(0,CH-5),(CW,CH)], fill=GREEN)
    draw.rectangle([(0,0),(5,CH)],     fill=GREEN)
    draw.rectangle([(CW-5,0),(CW,CH)], fill=GREEN)

    # Burchak dekorlar
    for (cx,cy,dx,dy) in [(15,15,1,1),(CW-15,15,-1,1),
                           (CW-15,CH-15,-1,-1),(15,CH-15,1,-1)]:
        for i, a in enumerate([255, 160, 80]):
            l = 35 - i*10
            draw.line([(cx,cy),(cx+dx*l,cy)], fill=(*GREEN,a), width=2)
            draw.line([(cx,cy),(cx,cy+dy*l)], fill=(*GREEN,a), width=2)

    return canvas


# ═══════════════════════════════════════════════════════
#   BANNER GENERATSIYA
# ═══════════════════════════════════════════════════════
def generate(name, guild, level, uid, exp, likes, bio,
             avatar_bytes) -> bytes:

    canvas = make_template()
    draw   = ImageDraw.Draw(canvas)

    # ── Ma'lumotlar (o'ng yuqori qism) ───────────────────
    INFO_X  = BN_X + 30
    INFO_Y  = BN_Y + 35
    LINE_H  = int((BN_H - 50) / 4)

    info_f = fnt(44, bold=False)
    lines  = [
        (f"Daraja (EXP):    {exp:,}".replace(",", " "), WHITE),
        (f"Yoqtirishlar:    {int(likes):,}".replace(",", " "), GRAY),
        (f"UID:             {uid}", GRAY),
        (f"Bio:             {(bio[:10] + '...' if bio and len(bio) > 10 else bio or '—')}", GRAY),
    ]
    for i, (line, color) in enumerate(lines):
        stroke_text(draw, INFO_X, INFO_Y + i*LINE_H, line, info_f, color, sw=2)

    # ── Avatar ────────────────────────────────────────────
    av_img = to_img(avatar_bytes, (AV_W, AV_H), fallback=(25,25,38))
    mask   = Image.new("L", (AV_W, AV_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0,0),(AV_W-1,AV_H-1)], radius=14, fill=255)
    canvas.paste(av_img, (AV_X, AV_Y), mask)

    # Avatar chegara qayta
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        [AV_X-10, AV_Y-10, AV_X+AV_W+10, AV_Y+AV_H+10],
        radius=22, outline=GREEN, width=4)

    # ── Pastki qator: hammasi bir tekisda ─────────────────
    # Y markazini hisoblash
    BASE_F = fnt(72, bold=True)
    bb_tmp = draw.textbbox((0,0), "LvL. 00", font=BASE_F)
    text_h = bb_tmp[3] - bb_tmp[1]
    BASE_Y = BOT_Y + (BOT_H - text_h) // 2

    cursor = 90  # X boshlanishi

    # LvL. {son}
    lvl_t = f"LvL. {level}"
    stroke_text(draw, cursor, BASE_Y, lvl_t, BASE_F, GREEN)
    bb = draw.textbbox((0,0), lvl_t, font=BASE_F)
    cursor += (bb[2]-bb[0]) + 55

    # Bo'shliq chiziq
    stroke_text(draw, cursor, BASE_Y, "—", fnt(72, bold=False), (*GREEN,120), sw=1)
    cursor += draw.textbbox((0,0), "—", font=fnt(72, bold=False))[2] + 55

    # Ism
    name_t = name or "Unknown"
    max_nm = CW - cursor - 600  # Gildiya uchun joy qoldirish
    name_f = fit_text(draw, name_t, 72, max_nm, bold=True)
    stroke_text(draw, cursor, BASE_Y, name_t, name_f, WHITE)
    bb_nm  = draw.textbbox((0,0), name_t, font=name_f)
    cursor += (bb_nm[2]-bb_nm[0]) + 40

    # Separator |
    if guild:
        sep_f = fnt(72, bold=False)
        stroke_text(draw, cursor, BASE_Y, "|", sep_f, (*GREEN,200), sw=1)
        cursor += draw.textbbox((0,0), "|", font=sep_f)[2] + 40

        # Gildiya
        max_gld = CW - cursor - 30
        gld_f   = fit_text(draw, guild, 72, max_gld, bold=True)
        stroke_text(draw, cursor, BASE_Y, guild, gld_f, GRAY)

    # ── Natija ────────────────────────────────────────────
    out = io.BytesIO()
    canvas.convert("RGB").save(out, "PNG", optimize=True)
    out.seek(0)
    return out.getvalue()


# ═══════════════════════════════════════════════════════
#   ENDPOINTLAR
# ═══════════════════════════════════════════════════════
@app.get("/")
async def home():
    return {"status": "HFF Banner API", "usage": "/banner?uid=YOUR_UID"}


@app.get("/banner")
async def get_banner(uid: str):
    try:
        resp = await client.get(f"{INFO_API_URL}?uid={uid}")
        if resp.status_code != 200:
            raise HTTPException(502, f"Info API: {resp.status_code}")
        data = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))

    basic  = data.get("basicInfo")   or {}
    clan   = data.get("clanBasicInfo") or {}
    social = data.get("socialInfo")   or {}

    if not basic:
        raise HTTPException(404, "O'yinchi topilmadi")

    name    = basic.get("nickname")  or "Unknown"
    level   = basic.get("level")     or 0
    exp     = basic.get("exp")        or 0
    likes   = basic.get("liked")      or 0
    guild   = clan.get("clanName")    or ""
    bio     = social.get("signature") or ""
    head_id = basic.get("headPic")

    icon_name    = _item_cache.get(str(head_id))
    avatar_bytes = await fetch_icon(icon_name, head_id)

    img_bytes = await asyncio.get_event_loop().run_in_executor(
        pool, generate,
        name, guild, level, uid, exp, likes, bio,
        avatar_bytes,
    )
    return Response(img_bytes, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

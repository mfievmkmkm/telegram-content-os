import hashlib
import io
import math
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .formatting import plain_text

FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DISPLAY_FONT="/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
REGULAR="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SCENE_DIR=Path(__file__).with_name("assets")/"card_scenes"
SCENES=("market_phone.webp","alert_vault.webp","liquid_gift.webp","rare_object.webp","fomo_meme.webp","gift_auction.webp","market_whale.webp","fomo_cart.webp",
        "vault_capsule.webp","crystal_market.webp","auction_strike.webp","gift_terminal.webp","chrome_whale.webp","rare_safe.webp","market_cart.webp")
LIGA_SCENES=("stadium_tunnel.webp","tactics_lab.webp","night_training.webp","goalkeeper.webp","golden_bench.webp",
             "sprint_rain.webp","coach_hologram.webp","keeper_flight.webp","empty_bench.webp","duel_fire.webp","tunnel_light.webp","neon_strike.webp")

def font(size,bold=True): return ImageFont.truetype(FONT if bold else REGULAR,size)

def display_font(size): return ImageFont.truetype(DISPLAY_FONT if Path(DISPLAY_FONT).exists() else FONT,size)

def use_gift_card(draft_id): return int(draft_id)%3 != 0

def use_liga_card(draft_id): return int(draft_id)%3 != 0

def _lines(text): return [x.strip() for x in plain_text(text).splitlines() if x.strip()]

def _hook(lines): return re.sub(r"^[^\wА-Яа-я]+\s*","",lines[0] if lines else "РЫНОК БЕЗ ГРИМА")

def _pick_liga_scene(text,seed):
    value=text.lower()
    if any(x in value for x in ("вратар", "голкипер", "сейв", "ворот")): return ("goalkeeper.webp","keeper_flight.webp")[seed%2]
    if any(x in value for x in ("скамей", "состав", "замен", "запас")): return ("golden_bench.webp","empty_bench.webp")[seed%2]
    if any(x in value for x in ("трениров", "упражнен", "скорост", "рывок", "конус")): return ("night_training.webp","sprint_rain.webp")[seed%2]
    if any(x in value for x in ("тактик", "схем", "позици", "разбор", "эпизод", "зон")): return ("tactics_lab.webp","coach_hologram.webp")[seed%2]
    if any(x in value for x in ("удар", "гол", "заверш", "бьёт")): return "neon_strike.webp"
    if any(x in value for x in ("единобор", "отбор", "контакт", "дуэл")): return "duel_fire.webp"
    if any(x in value for x in ("мем", "пов", "когда", "тренер сказал", "лицо")): return ("empty_bench.webp","golden_bench.webp")[seed%2]
    if any(x in value for x in ("дебют", "страх", "давлен", "путь", "характер")): return "tunnel_light.webp"
    return LIGA_SCENES[seed%len(LIGA_SCENES)]

def _pick_gift_scene(text,seed):
    value=text.lower()
    if any(x in value for x in ("кит", "холдер", "разгруз", "вышел")): return ("market_whale.webp","chrome_whale.webp")[seed%2]
    if any(x in value for x in ("аукцион", "торг", "ставк", "покупател")): return ("gift_auction.webp","auction_strike.webp")[seed%2]
    if any(x in value for x in ("fomo", "пик", "корзин", "скуп", "набрал")): return ("fomo_cart.webp","market_cart.webp")[seed%2]
    if any(x in value for x in ("редк", "уник", "коллекц", "эксклюзив")): return ("rare_object.webp","rare_safe.webp","vault_capsule.webp")[seed%3]
    if any(x in value for x in ("график", "рынок", "цена", "floor", "тон")): return ("market_phone.webp","gift_terminal.webp","crystal_market.webp")[seed%3]
    return SCENES[(seed//2)%len(SCENES)]

def _fit(draw,text,box,max_size=72,min_size=34,max_lines=5,bold=True,color=(245,247,250)):
    x,y,w,h=box
    for size in range(max_size,min_size-1,-2):
        f=font(size,bold); width=max(8,int(w/(size*.58))); wrapped=textwrap.wrap(text,width=width,break_long_words=False)
        if len(wrapped)<=max_lines and len(wrapped)*int(size*1.18)<=h:
            for line in wrapped: draw.text((x,y),line,font=f,fill=color); y+=int(size*1.18)
            return y
    clipped=textwrap.shorten(text,width=max(35,int(w/min_size*.9)*max_lines),placeholder="…")
    for line in textwrap.wrap(clipped,width=max(8,int(w/(min_size*.58))),break_long_words=False)[:max_lines]:
        draw.text((x,y),line,font=font(min_size,bold),fill=color); y+=int(min_size*1.18)
    return y

def _brand(draw,accent,label="INTELLIGENCE"):
    draw.text((72,62),"GI",font=font(34),fill=accent); draw.text((145,68),f"GIFTS / {label}",font=font(25),fill=(218,222,230))

def _dashboard(draw,lines,accent,seed):
    draw.rectangle((0,0,1080,1080),fill=(7,10,14)); _brand(draw,accent,"MARKET DESK")
    draw.rounded_rectangle((62,130,1018,640),36,fill=(13,19,25),outline=(40,49,58),width=2)
    numbers=re.findall(r"(?:\$|≈)?\d[\d\s.,]*(?:%|TON|k|K|зв[её]зд)?",plain_text(" ".join(lines)))
    metric=(numbers[0].strip() if numbers else "SIGNAL")[:16]
    draw.text((92,165),"MARKET PULSE",font=font(22),fill=(125,137,148)); draw.text((90,215),metric,font=font(92),fill=accent)
    points=[]
    for i in range(13):
        value=410+math.sin((i+seed%7)*.8)*70+((seed>>(i%16))&7)*9; points.append((100+i*72,int(value)))
    for gy in (360,440,520,600): draw.line((90,gy,990,gy),fill=(29,38,47),width=2)
    draw.line(points,fill=accent,width=9,joint="curve")
    draw.rounded_rectangle((62,676,1018,1000),32,fill=(18,23,29)); _fit(draw,_hook(lines),(92,720,870,190),58,36,3)
    draw.text((92,944),"НЕ ЦЕНА. КОНТЕКСТ.",font=font(22),fill=(130,140,150))

def _meme(draw,lines,accent,seed):
    draw.rectangle((0,0,1080,1080),fill=(235,238,241)); _brand(draw,(25,30,35),"MEME UNIT")
    draw.rounded_rectangle((54,135,1026,1018),48,fill=(20,23,28)); draw.ellipse((88,190,202,304),fill=accent)
    draw.text((122,215),"GI",font=font(26),fill=(10,12,14)); draw.text((228,194),"рынок подарков",font=font(29),fill=(245,247,250)); draw.text((228,240),"был недавно",font=font(20,False),fill=(132,142,152))
    _fit(draw,_hook(lines),(110,350,820,250),58,34,4)
    answer=textwrap.shorten(lines[1] if len(lines)>1 else "рынок: красиво держишь пакет",width=90,placeholder="…")
    draw.rounded_rectangle((255,675,940,870),34,fill=(45,52,61)); _fit(draw,answer,(292,714,610,120),35,25,3,False)
    draw.text((110,932),"FORWARD ЭТОМУ САМОМУ ХОЛДЕРУ",font=font(22),fill=accent)

def _dossier(draw,lines,accent,seed):
    draw.rectangle((0,0,1080,1080),fill=(228,224,212)); draw.polygon([(0,0),(1080,0),(1080,185),(0,255)],fill=(18,20,23)); _brand(draw,accent,"RISK FILE")
    draw.rounded_rectangle((70,210,1010,1008),24,fill=(247,244,234),outline=(28,30,34),width=3)
    draw.rectangle((104,250,410,305),fill=accent); draw.text((126,260),"ДОСЬЕ / ОШИБКА",font=font(24),fill=(10,12,14))
    y=_fit(draw,_hook(lines),(108,352,820,260),62,34,5,color=(28,31,35)); draw.line((108,y+24,930,y+24),fill=(30,33,37),width=4); y+=62
    detail=" ".join(lines[1:3]) or "Красивый актив ещё не означает живой спрос"
    for line in textwrap.wrap(textwrap.shorten(detail,width=180,placeholder="…"),width=47)[:5]:
        draw.ellipse((112,y+7,132,y+27),fill=accent); draw.text((154,y),line,font=font(29,False),fill=(31,34,38)); y+=47
    draw.text((108,946),f"CASE #{seed%9000+1000} / GI INTERNAL",font=font(20),fill=(100,100,96))

def _editorial(draw,lines,accent,seed):
    draw.rectangle((0,0,1080,1080),fill=(12,13,16)); draw.rectangle((0,0,390,1080),fill=accent); draw.rectangle((390,0,420,1080),fill=(235,239,242))
    draw.text((58,70),"GIFTS",font=font(52),fill=(8,10,12)); draw.text((58,132),"INTELLIGENCE",font=font(23),fill=(8,10,12)); draw.text((58,870),"READ",font=font(102),fill=(8,10,12)); draw.text((58,978),"BEFORE BUY",font=font(25),fill=(8,10,12))
    draw.text((470,78),"THE BRIEF",font=font(24),fill=accent); y=_fit(draw,_hook(lines),(470,155,540,390),62,34,6)
    draw.line((470,y+25,990,y+25),fill=accent,width=4); y+=65; detail=" ".join(lines[1:3]) or "Смотри глубже красивой оболочки"
    _fit(draw,textwrap.shorten(detail,width=170,placeholder="…"),(470,y,520,260),34,25,7,False)

def _spotlight(draw,lines,accent,seed):
    draw.rectangle((0,0,1080,1080),fill=(8,10,14)); _brand(draw,accent,"OBJECT LAB"); draw.ellipse((585,120,1085,620),fill=tuple(max(0,c//4) for c in accent))
    draw.rounded_rectangle((675,205,955,515),58,fill=accent,outline=(245,247,250),width=7); draw.polygon([(815,238),(915,350),(815,485),(715,350)],fill=(245,247,250)); draw.polygon([(815,270),(872,350),(815,430),(758,350)],fill=(18,22,27))
    draw.rounded_rectangle((58,610,1022,1015),38,fill=(18,22,28)); _fit(draw,_hook(lines),(92,650,870,225),58,34,4); draw.text((92,950),"OBJECT ≠ LIQUIDITY",font=font(24),fill=accent)

def _cinematic(lines,seed,scene_name,channel="gifts"):
    """Cinematic scene + editorial typography, inspired by high-end thumbnails."""
    image=Image.open(SCENE_DIR/scene_name).convert("RGB").resize((1080,1080),Image.Resampling.LANCZOS)
    shade=Image.new("RGBA",image.size,(0,0,0,0)); px=shade.load()
    for x in range(760):
        alpha=max(0,min(238,int(232-(x/760)*210)))
        for y in range(1080): px[x,y]=(3,5,9,alpha)
    image=Image.alpha_composite(image.convert("RGBA"),shade).convert("RGB"); draw=ImageDraw.Draw(image)
    palettes={
        "gifts":((176,255,0),(91,223,255),(202,112,255),(255,186,51),(255,79,96)),
        "liga":((100,255,171),(67,205,255),(255,177,45),(180,139,255),(242,247,250)),
    }
    accents=palettes[channel]; accent=accents[seed%len(accents)]
    draw.rounded_rectangle((66,58,272,108),25,fill=accent)
    badge="GI  /  SIGNAL" if channel=="gifts" else "LP  /  GAME LAB"
    draw.text((91,70),badge,font=font(20),fill=(5,7,10))
    hook=_hook(lines).upper()
    box=(66,170,565,610); x,y,w,h=box
    for size in range(78,37,-2):
        f=display_font(size); wrapped=textwrap.wrap(hook,width=max(8,int(w/(size*.51))),break_long_words=False)
        if len(wrapped)<=6 and len(wrapped)*int(size*1.03)<=h:
            for i,line in enumerate(wrapped):
                color=accent if i==len(wrapped)-1 and len(wrapped)>1 else (248,249,252)
                draw.text((x,y),line,font=f,fill=color,stroke_width=2,stroke_fill=(4,5,8)); y+=int(size*1.03)
            break
    detail=" ".join(lines[1:3]) or "Сигнал важнее шума"
    detail=textwrap.shorten(detail,width=105,placeholder="…")
    draw.rounded_rectangle((66,825,570,985),24,fill=(7,9,13,230),outline=accent,width=3)
    _fit(draw,detail,(94,852,445,95),28,22,3,False)
    footer="GIFTS INTELLIGENCE  •  MARKET DESK" if channel=="gifts" else "LIGA PROGRESS  •  GAME LAB"
    draw.text((70,1025),footer,font=font(18),fill=(178,184,194))
    return image

def gift_card(post_text,format_key="intelligence"):
    """Cinematic gift-card pool; legacy flat templates are intentionally disabled."""
    lines=_lines(post_text); digest=hashlib.sha256((format_key+plain_text(post_text)).encode()).hexdigest(); seed=int(digest[:8],16)
    scene="fomo_meme.webp" if format_key=="мем" else _pick_gift_scene(plain_text(post_text),seed)
    image=_cinematic(lines,seed,scene)
    output=io.BytesIO(); image.save(output,"PNG",optimize=True); return output.getvalue()

def liga_card(post_text,format_key="football"):
    """Cinematic football card pool with deterministic story-based rotation."""
    lines=_lines(post_text); digest=hashlib.sha256(("liga"+format_key+plain_text(post_text)).encode()).hexdigest(); seed=int(digest[:8],16)
    scene=("empty_bench.webp","golden_bench.webp")[seed%2] if format_key=="мем" else _pick_liga_scene(plain_text(post_text),seed)
    image=_cinematic(lines,seed,scene,"liga")
    output=io.BytesIO(); image.save(output,"PNG",optimize=True); return output.getvalue()

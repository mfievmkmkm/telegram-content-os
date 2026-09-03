import hashlib, io, re, textwrap
from PIL import Image, ImageDraw, ImageFont
from .formatting import plain_text

FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def font(size,bold=True): return ImageFont.truetype(FONT if bold else REGULAR,size)

def use_gift_card(draft_id):
    """Keep the feed varied: two branded cards, then one text-only post."""
    return int(draft_id)%3 != 0

def gift_card(post_text,format_key=" intelligence"):
    """Deterministic, free card with rotating layouts inside one visual identity."""
    seed=int(hashlib.sha256(plain_text(post_text).encode()).hexdigest()[:8],16)
    styles=[((151,255,0),(43,70,15)),((83,228,255),(12,65,76)),((194,128,255),(57,31,75)),((255,194,71),(78,53,14))]
    accent,orb=styles[seed%len(styles)]
    image=Image.new("RGB",(1080,1080),(7,9,12)); draw=ImageDraw.Draw(image)
    if seed%2:
        draw.rounded_rectangle((48,48,1032,1032),radius=42,fill=(12,16,21),outline=accent,width=3)
        draw.ellipse((750,-170,1170,250),fill=orb); draw.ellipse((-140,810,240,1190),fill=(25,43,49))
    else:
        draw.rectangle((0,0,1080,190),fill=orb); draw.line((70,244,1010,244),fill=accent,width=4)
        draw.rounded_rectangle((54,270,1026,1018),radius=34,fill=(12,16,21))
    draw.text((86,86),"GIFTS  /  INTELLIGENCE",font=font(34),fill=accent)
    draw.text((86,150),format_key.replace("_"," ").upper()[:32],font=font(22),fill=(140,150,160))
    lines=[x.strip() for x in plain_text(post_text).splitlines() if x.strip()]
    hook=re.sub(r"^[^\wА-Яа-я]+\s*","",lines[0] if lines else "РЫНОК БЕЗ ГРИМА")
    wrapped=textwrap.wrap(hook,width=20,break_long_words=False)[:5]; y=290
    for line in wrapped:
        draw.text((86,y),line,font=font(68),fill=(244,247,249)); y+=86
    draw.rounded_rectangle((86,870,580,944),radius=30,fill=accent)
    draw.text((118,887),"СМОТРИ ГЛУБЖЕ FLOOR",font=font(25),fill=(7,9,12))
    draw.text((86,980),"GI  •  MARKET SIGNALS WITHOUT FAIRYTALES",font=font(20),fill=(130,140,150))
    output=io.BytesIO(); image.save(output,"PNG",optimize=True); return output.getvalue()

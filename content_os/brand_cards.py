import io, re, textwrap
from PIL import Image, ImageDraw, ImageFont
from .formatting import plain_text

FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def font(size,bold=True): return ImageFont.truetype(FONT if bold else REGULAR,size)

def gift_card(post_text,format_key=" intelligence"):
    """Deterministic 1080px brand card; free, fast and visually consistent."""
    image=Image.new("RGB",(1080,1080),(7,9,12)); draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((48,48,1032,1032),radius=42,fill=(12,16,21),outline=(151,255,0),width=3)
    draw.ellipse((750,-170,1170,250),fill=(43,70,15)); draw.ellipse((-140,810,240,1190),fill=(25,43,49))
    draw.text((86,86),"GIFTS  /  INTELLIGENCE",font=font(34),fill=(151,255,0))
    draw.text((86,150),format_key.replace("_"," ").upper()[:32],font=font(22),fill=(140,150,160))
    lines=[x.strip() for x in plain_text(post_text).splitlines() if x.strip()]
    hook=re.sub(r"^[^\wА-Яа-я]+\s*","",lines[0] if lines else "РЫНОК БЕЗ ГРИМА")
    wrapped=textwrap.wrap(hook,width=20,break_long_words=False)[:5]; y=290
    for line in wrapped:
        draw.text((86,y),line,font=font(68),fill=(244,247,249)); y+=86
    draw.rounded_rectangle((86,870,580,944),radius=30,fill=(151,255,0))
    draw.text((118,887),"СМОТРИ ГЛУБЖЕ FLOOR",font=font(25),fill=(7,9,12))
    draw.text((86,980),"GI  •  MARKET SIGNALS WITHOUT FAIRYTALES",font=font(20),fill=(130,140,150))
    output=io.BytesIO(); image.save(output,"PNG",optimize=True); return output.getvalue()

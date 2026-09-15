import hashlib
import html
import re


SOURCE_LINE = re.compile(
    r"^\s*(?:источник|source|ссылка|подробнее)\s*:\s*.*$",
    re.IGNORECASE,
)


def clean_generated_post(value: str) -> str:
    """Normalize model output and never expose internal research links."""
    text = (value or "").strip()
    text = re.sub(r"^```(?:html|markdown)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    lines = [line for line in text.splitlines() if not SOURCE_LINE.match(line)]
    text = "\n".join(lines)
    text = re.sub(r"(?m)^\s*https?://\S+\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def telegram_html(value: str,custom_emojis:dict[str,str]|None=None) -> str:
    """Render a small, safe subset of model formatting as Telegram HTML."""
    text = clean_generated_post(value)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    escaped = html.escape(text, quote=False)
    for tag in ("b", "strong", "i", "em", "u", "s", "blockquote"):
        escaped = re.sub(
            rf"&lt;(/?){tag}&gt;",
            lambda match: f"<{match.group(1)}{tag}>",
            escaped,
            flags=re.IGNORECASE,
        )
    replacements={}
    for index,(fallback,emoji_id) in enumerate((custom_emojis or {}).items()):
        base=fallback.replace("\ufe0f","")
        if not (base and emoji_id.isdigit()): continue
        def custom_tag(match):
            token=f"__CUSTOM_EMOJI_{index}_{len(replacements)}__"
            replacements[token]=f'<tg-emoji emoji-id="{emoji_id}">{match.group(0)}</tg-emoji>'
            return token
        escaped=re.sub(re.escape(base)+"\ufe0f?",custom_tag,escaped)
    for token,tag in replacements.items(): escaped=escaped.replace(token,tag)
    return escaped


def plain_text(value: str) -> str:
    return re.sub(r"<[^>]+>", "", clean_generated_post(value))


SIGNATURE_EMOJIS = {"liga": ("⚡", "🎯"), "gifts": ("💎", "🧠")}

EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF]"
    "[\uFE0F\u200D\U0001F3FB-\U0001F3FF]*"
)


def _editorial_punctuation(value: str) -> str:
    """Apply the channel's compact Telegram punctuation rules."""
    text = re.sub(r"\.\s*(?=" + EMOJI_RE.pattern + r")", " ", value)
    text = re.sub(r"(" + EMOJI_RE.pattern + r")\.", r"\1", text)
    lines = text.rstrip().splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip():
            lines[index] = re.sub(r"\.\s*(</(?:i|b)>)\s*$", r"\1", lines[index])
            lines[index] = re.sub(r"\.\s*$", "", lines[index])
            break
    return "\n".join(lines)


def decorate_post(value: str, channel_key: str, anchors: tuple[str, ...] | None = None) -> str:
    """Apply one art direction with several deterministic editorial layouts."""
    text=plain_text(value)
    text=re.sub(r"\*\*|__|(?<!\*)\*(?!\*)", "", text)
    # Strip the model's random decoration before applying the house signature.
    text=EMOJI_RE.sub("",text)
    text=re.sub(r"[ \t]{2,}"," ",text)
    paragraphs=[part.strip() for part in re.split(r"\n\s*\n",text) if part.strip() and part.strip()!="—"]
    if not paragraphs: return text
    selected=tuple(anchors or SIGNATURE_EMOJIS.get(channel_key,SIGNATURE_EMOJIS["liga"]))
    if len(selected)<2: selected=SIGNATURE_EMOJIS.get(channel_key,SIGNATURE_EMOJIS["liga"])
    lead,close=selected[:2]
    paragraphs[0]=f"{lead} <b>{paragraphs[0]}</b>"
    if len(paragraphs)>1:
        # Ignore punctuation so a second pass (which removes the final period)
        # keeps exactly the same composition.
        layout_seed=re.sub(r"[\W_]+","",text.lower(),flags=re.UNICODE)
        layout=int(hashlib.sha256(layout_seed.encode("utf-8")).hexdigest()[:2],16)%4
        if layout==0:
            if len(paragraphs)>=4 and len(paragraphs[1])<=220: paragraphs[1]=f"<i>{paragraphs[1]}</i>"
            if len(paragraphs)>=3: paragraphs[-2]=f"<blockquote>{paragraphs[-2]}</blockquote>"
            paragraphs[-1]=f"{close} <i>{paragraphs[-1]}</i>"
        elif layout==1:
            if len(paragraphs)>=3: paragraphs[1]=f"<blockquote>{paragraphs[1]}</blockquote>"
            paragraphs[-1]=f"{close} <i>{paragraphs[-1]}</i>"
        elif layout==2:
            if len(paragraphs)>=4: paragraphs[-2]=f"<i>{paragraphs[-2]}</i>"
            paragraphs[-1]=f"{close} <b>{paragraphs[-1]}</b>"
        else:
            if len(paragraphs)>=4: paragraphs[1]=f"<i>{paragraphs[1]}</i>"
            paragraphs[-1]=f"{close} <i>{paragraphs[-1]}</i>"
    return _editorial_punctuation("\n\n".join(paragraphs))

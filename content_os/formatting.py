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


EMOJI_SETS = {
    "liga": ("⚡", "🧠", "⚽", "🔥", "🎯", "🥶", "👀"),
    "gifts": ("💎", "📉", "🎁", "🔥", "🧠", "👀", "⚠️"),
}

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
            lines[index] = re.sub(r"\.\s*$", "", lines[index])
            break
    return "\n".join(lines)


def decorate_post(value: str, channel_key: str) -> str:
    """Guarantee readable emphasis and emoji anchors even when the LLM ignores markup."""
    text=plain_text(value)
    text=re.sub(r"\*\*|__|(?<!\*)\*(?!\*)", "", text)
    # The editor, not the model, controls visual density: start from clean copy and
    # add only two deliberate anchors. Variation comes from the channel palette.
    text=EMOJI_RE.sub("",text)
    text=re.sub(r"[ \t]{2,}"," ",text)
    paragraphs=[part.strip() for part in re.split(r"\n\s*\n",text) if part.strip()]
    if not paragraphs: return text
    emojis=EMOJI_SETS.get(channel_key,EMOJI_SETS["liga"])
    paragraphs[0]=f"{emojis[0]} <b>{paragraphs[0]}</b>"
    if len(paragraphs)>2:
        paragraphs[-2]=f"{emojis[3]} <i>{paragraphs[-2]}</i>"
    elif len(paragraphs)==2:
        paragraphs[1]=f"{emojis[1]} <i>{paragraphs[1]}</i>"
    return _editorial_punctuation("\n\n".join(paragraphs))

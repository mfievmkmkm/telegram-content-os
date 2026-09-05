from __future__ import annotations

import re
import unicodedata


def spoken_text(value:str)->str:
    """Remove visual Telegram decoration before sending a script to TTS."""
    value=(value or "").replace("⭐"," звёзд ")
    cleaned=[]
    for char in value:
        category=unicodedata.category(char)
        if char in {"\ufe0f","\u200d","\u20e3"} or category in {"So","Sk"}:
            cleaned.append(" ")
        else:
            cleaned.append(char)
    return re.sub(r"\s{2,}"," ","".join(cleaned)).strip()


def clean_script(value:str)->str:
    text=re.sub(r"<[^>]+>","",value or "")
    text=spoken_text(text)
    text=text.replace("—",",").replace("–",",")
    text=re.sub(r"[\r\n]+"," ",text); text=re.sub(r"\.{2,}",".",text)
    return re.sub(r"\s{2,}"," ",text).strip(" ,")


def caption_chunks(script:str,max_words:int=2)->list[str]:
    """Short punchy captions that remain readable on a phone."""
    words=clean_script(script).split()
    chunks=[words[index:index+max_words] for index in range(0,len(words),max_words)]
    chunks=[" ".join(chunk) for chunk in chunks]
    return chunks or ["СМОТРИ ДО КОНЦА"]


def alignment_chunks(alignment:dict,max_words:int=2)->list[tuple[str,float,float]]:
    """Convert character timing into short mobile caption phrases."""
    chars=alignment.get("characters") or []
    starts=alignment.get("character_start_times_seconds") or []
    ends=alignment.get("character_end_times_seconds") or []
    if not chars or not (len(chars)==len(starts)==len(ends)): return []
    words=[]; value=""; start=None; end=0.0
    for char,left,right in zip(chars,starts,ends):
        if str(char).isspace():
            if value: words.append((value,float(start),float(end))); value=""; start=None
            continue
        if start is None: start=float(left)
        value+=str(char); end=float(right)
    if value: words.append((value,float(start),float(end)))
    result=[]
    for index in range(0,len(words),max_words):
        group=words[index:index+max_words]
        result.append((" ".join(word[0] for word in group),group[0][1],group[-1][2]))
    return result


def ass_subtitles(script:str,duration:float,alignment:dict|None=None)->str:
    timed=alignment_chunks(alignment or {})
    chunks=caption_chunks(script); total=sum(len(x.split()) for x in chunks); cursor=0.0; lines=[]
    def stamp(seconds):
        hours=int(seconds//3600); minutes=int(seconds%3600//60); rest=seconds%60
        return f"{hours}:{minutes:02d}:{rest:05.2f}"
    entries=timed or [(chunk,None,None) for chunk in chunks]
    for chunk,aligned_start,aligned_end in entries:
        if aligned_start is None:
            share=max(.7,duration*len(chunk.split())/max(1,total)); start=cursor; end=min(duration,cursor+share)
        else: start=max(0.0,aligned_start-.04); end=min(duration,aligned_end+.08)
        words=chunk.replace("{","(").replace("}",")").replace("\n"," ").split()
        # One accented word gives the eye a target without karaoke clutter.
        safe=" ".join(words[:-1]+([r"{\c&H55FFB0&}"+words[-1]+r"{\c&HFFFFFF&}"] if words else []))
        lines.append(f"Dialogue: 0,{stamp(start)},{stamp(end)},Main,,0,0,0,,{safe}")
        cursor=end
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,62,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,2,68,68,235,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""+"\n".join(lines)+"\n"


def unique_terms(payload:dict)->list[str]:
    result=[]
    for value in payload.get("video_terms") or []:
        term=re.sub(r"[^a-zA-Z0-9 -]","",str(value)).strip()[:70]
        if term and term.lower() not in {x.lower() for x in result}: result.append(term)
    return result[:7]

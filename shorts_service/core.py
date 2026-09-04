from __future__ import annotations

import re


def clean_script(value:str)->str:
    text=re.sub(r"<[^>]+>","",value or "")
    text=text.replace("—",",").replace("–",",")
    text=re.sub(r"[\r\n]+"," ",text); text=re.sub(r"\.{2,}",".",text)
    return re.sub(r"\s{2,}"," ",text).strip(" ,")


def caption_chunks(script:str,max_words:int=3)->list[str]:
    """Short punchy captions that remain readable on a phone."""
    words=clean_script(script).split()
    chunks=[words[index:index+max_words] for index in range(0,len(words),max_words)]
    # Never flash a lonely final word: attach it to the preceding phrase.
    if len(chunks)>1 and len(chunks[-1])==1: chunks[-2].extend(chunks.pop())
    chunks=[" ".join(chunk) for chunk in chunks]
    return chunks or ["СМОТРИ ДО КОНЦА"]


def ass_subtitles(script:str,duration:float)->str:
    chunks=caption_chunks(script); total=sum(len(x.split()) for x in chunks); cursor=0.0; lines=[]
    def stamp(seconds):
        hours=int(seconds//3600); minutes=int(seconds%3600//60); rest=seconds%60
        return f"{hours}:{minutes:02d}:{rest:05.2f}"
    for chunk in chunks:
        share=max(.7,duration*len(chunk.split())/max(1,total)); end=min(duration,cursor+share)
        words=chunk.replace("{","(").replace("}",")").replace("\n"," ").split()
        # One accented word gives the eye a target without karaoke clutter.
        safe=" ".join(words[:-1]+([r"{\c&H55FFB0&}"+words[-1]+r"{\c&HFFFFFF&}"] if words else []))
        lines.append(f"Dialogue: 0,{stamp(cursor)},{stamp(end)},Main,,0,0,0,,{safe}")
        cursor=end
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,68,&H00FFFFFF,&H00FFFFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,0,0,3,3,1,2,52,52,315,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""+"\n".join(lines)+"\n"


def unique_terms(payload:dict)->list[str]:
    result=[]
    for value in payload.get("video_terms") or []:
        term=re.sub(r"[^a-zA-Z0-9 -]","",str(value)).strip()[:70]
        if term and term.lower() not in {x.lower() for x in result}: result.append(term)
    return result[:7]

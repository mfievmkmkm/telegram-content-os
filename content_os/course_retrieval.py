from __future__ import annotations

import re


TERMS={
    "liga":("футбол","игрок","тренер","матч","команд","решен","ошиб","страх","уверенн","конкурен","дисциплин","вниман","привыч"),
    "gifts":("продаж","оффер","рынок","крипт","риск","ценност","аудитор","вниман","довер","покуп","спрос","ликвид","контент","воронк"),
}


def select_course_snippets(rows,channel_key:str,limit:int=7):
    """Pick relevant, source-diverse notes instead of blindly using the newest lessons."""
    terms=TERMS[channel_key]; ranked=[]
    for index,row in enumerate(rows):
        text=str(row["text"]); lowered=text.lower(); hits=sum(len(re.findall(term,lowered)) for term in terms)
        density=hits/max(1,len(text)/1000); ranked.append((hits>0,density,-index,row))
    ranked.sort(key=lambda item:item[:3],reverse=True); selected=[]; per_source={}
    for _,_,_,row in ranked:
        source=str(row.get("source_channel","") if isinstance(row,dict) else row["source_channel"])
        if per_source.get(source,0)>=2: continue
        selected.append(row); per_source[source]=per_source.get(source,0)+1
        if len(selected)>=limit: break
    return selected

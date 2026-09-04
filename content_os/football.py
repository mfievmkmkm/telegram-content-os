import asyncio
from datetime import datetime

import aiohttp


class FootballRadar:
    def __init__(self,settings):
        self.key=settings.api_football_key; self.base=settings.api_football_url
        self.leagues={int(x) for x in settings.football_leagues if x.isdigit()}

    @property
    def ready(self): return bool(self.key)

    async def request(self,path,params):
        if not self.ready: raise RuntimeError("API_FOOTBALL_KEY не задан")
        headers={"x-apisports-key":self.key}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40),headers=headers) as session:
            async with session.get(f"{self.base}/{path}",params=params) as response:
                body=await response.json(content_type=None)
                if response.status>=400: raise RuntimeError(f"Football API HTTP {response.status}")
        errors=body.get("errors") or {}
        if errors: raise RuntimeError("; ".join(str(v) for v in errors.values())[:300])
        return body.get("response",[])

    async def fixtures(self,date:str|None=None):
        date=date or datetime.now().date().isoformat(); rows=await self.request("fixtures",{"date":date,"timezone":"Asia/Yekaterinburg"})
        if self.leagues: rows=[row for row in rows if row.get("league",{}).get("id") in self.leagues]
        return rows

    async def match_facts(self,fixture_id:int):
        rows=await self.request("fixtures",{"id":fixture_id,"timezone":"Asia/Yekaterinburg"})
        if not rows: raise RuntimeError("Матч не найден")
        fixture=rows[0]
        events=fixture.get("events",[])
        home=fixture["teams"]["home"]["name"]; away=fixture["teams"]["away"]["name"]
        score=fixture.get("goals",{}); status_data=fixture.get("fixture",{}).get("status",{}); short=status_data.get("short")
        status=status_data.get("long"); kickoff=fixture.get("fixture",{}).get("date","")
        lines=[f"Матч: {home} — {away}",f"Статус: {status} ({short})",f"Начало: {kickoff}"]
        upcoming=short in {"TBD","NS","PST","CANC","ABD"}
        async def safe(path,params):
            try: return await self.request(path,params)
            except Exception: return []
        if upcoming:
            lines.append("РЕЖИМ: ПРЕВЬЮ ДО МАТЧА. Не описывать события так, будто игра уже прошла.")
            h2h,predictions=await asyncio.gather(
                safe("fixtures/headtohead",{"h2h":f"{fixture['teams']['home']['id']}-{fixture['teams']['away']['id']}","last":5}),
                safe("predictions",{"fixture":fixture_id}),
            )
            if h2h:
                lines.append("Последние очные матчи:")
                for game in h2h[-5:]:
                    a=game.get("teams",{}).get("home",{}).get("name"); b=game.get("teams",{}).get("away",{}).get("name")
                    goals=game.get("goals",{}); lines.append(f"- {a} {goals.get('home')}:{goals.get('away')} {b}")
            if predictions:
                item=predictions[0]; prediction=item.get("predictions",{}); comparison=item.get("comparison",{})
                winner=prediction.get("winner") or {}; lines.append(f"Прогноз API: {winner.get('name') or 'без фаворита'}; комментарий: {winner.get('comment') or '—'}")
                for metric in ("form","att","def","poisson","h2h","goals","total"):
                    value=comparison.get(metric)
                    if value: lines.append(f"- {metric}: {value}")
        else:
            lines.append(f"РЕЖИМ: РАЗБОР СЫГРАННОГО/ИДУЩЕГО МАТЧА. Текущий счёт: {score.get('home')}:{score.get('away')}")
            statistics,players=await asyncio.gather(
                safe("fixtures/statistics",{"fixture":fixture_id}),
                safe("fixtures/players",{"fixture":fixture_id}),
            )
            for team in statistics:
                lines.append(f"\nСтатистика {team.get('team',{}).get('name')}:")
                for stat in team.get("statistics",[]):
                    if stat.get("value") is not None: lines.append(f"- {stat.get('type')}: {stat.get('value')}")
            standout=[]
            for team in players:
                for row in team.get("players",[]):
                    stats=(row.get("statistics") or [{}])[0]; games=stats.get("games",{}); rating=games.get("rating")
                    if rating:
                        standout.append((float(rating),row.get("player",{}).get("name"),team.get("team",{}).get("name"),stats))
            for rating,name,team,stats in sorted(standout,reverse=True)[:5]:
                lines.append(f"- Игрок: {name} ({team}), рейтинг {rating:.1f}, голы {stats.get('goals',{}).get('total') or 0}, передачи {stats.get('passes',{}).get('key') or 0}, отборы {stats.get('tackles',{}).get('total') or 0}")
            for event in events[-16:]:
                player=event.get("player",{}).get("name") or ""; assist=event.get("assist",{}).get("name") or ""
                lines.append(f"- {event.get('time',{}).get('elapsed')}' {event.get('team',{}).get('name')}: {event.get('type')} — {event.get('detail')} {player} {assist}".strip())
        return "\n".join(lines)[:9000]

def fixtures_keyboard_rows(fixtures,limit=12):
    rows=[]
    for item in fixtures[:limit]:
        fixture=item["fixture"]; teams=item["teams"]; moment=datetime.fromisoformat(fixture["date"])
        status=fixture.get("status",{}).get("short","")
        label=f"{moment:%H:%M} · {teams['home']['name'][:13]} — {teams['away']['name'][:13]}"+(f" · {status}" if status else "")
        rows.append((label,int(fixture["id"])))
    return rows

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
        fixture=rows[0]; statistics=await self.request("fixtures/statistics",{"fixture":fixture_id})
        events=fixture.get("events",[])
        home=fixture["teams"]["home"]["name"]; away=fixture["teams"]["away"]["name"]
        score=fixture.get("goals",{}); status=fixture.get("fixture",{}).get("status",{}).get("long")
        lines=[f"Матч: {home} — {away}",f"Статус: {status}",f"Счёт: {score.get('home')}:{score.get('away')}"]
        for team in statistics:
            lines.append(f"\n{team.get('team',{}).get('name')}:")
            for stat in team.get("statistics",[]):
                if stat.get("value") is not None: lines.append(f"- {stat.get('type')}: {stat.get('value')}")
        for event in events[-12:]:
            lines.append(f"- {event.get('time',{}).get('elapsed')}' {event.get('team',{}).get('name')}: {event.get('type')} — {event.get('detail')}")
        return "\n".join(lines)[:9000]

def fixtures_keyboard_rows(fixtures,limit=12):
    rows=[]
    for item in fixtures[:limit]:
        fixture=item["fixture"]; teams=item["teams"]; moment=datetime.fromisoformat(fixture["date"])
        label=f"{moment:%H:%M} · {teams['home']['name'][:13]} — {teams['away']['name'][:13]}"
        rows.append((label,int(fixture["id"])))
    return rows

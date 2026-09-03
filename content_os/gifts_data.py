import asyncio
import json

import aiohttp

ENDPOINTS={
 "greed":"/api/v1/gifts/get_gifts_collections_greed_index",
 "health":"/api/v1/gifts/get_gifts_collections_health_index",
 "volumes":"/api/v1/gifts/get_collections_volumes",
 "attribute_volumes":"/api/v1/gifts/get_attribute_volumes",
 "prices":"/api/v1/gifts/get_gifts_price_list",
 "deals":"/api/v1/gifts/get_top_best_deals",
}

class GiftsDataDesk:
    def __init__(self,settings): self.settings=settings

    async def _json(self,session,url,headers=None):
        async with session.get(url,headers=headers) as response:
            body=await response.text()
            if response.status>=400: raise RuntimeError(f"{url}: HTTP {response.status} {body[:100]}")
            return json.loads(body)

    async def snapshot(self):
        result={"gift_asset":{},"own_signals":[],"errors":[]}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:
            headers={}
            if self.settings.gift_asset_key: headers[self.settings.gift_asset_header]=self.settings.gift_asset_key
            calls={name:asyncio.create_task(self._json(session,self.settings.gift_asset_url+path,headers)) for name,path in ENDPOINTS.items()}
            for name,task in calls.items():
                try: result["gift_asset"][name]=await task
                except Exception as exc: result["errors"].append(f"Gift Asset {name}: {str(exc)[:120]}")
            if self.settings.gifts_supabase_url and self.settings.gifts_supabase_key and self.settings.gifts_signals_path:
                headers={"apikey":self.settings.gifts_supabase_key,"Authorization":f"Bearer {self.settings.gifts_supabase_key}"}
                url=f"{self.settings.gifts_supabase_url}/rest/v1/{self.settings.gifts_signals_path}"
                try: result["own_signals"]=await self._json(session,url,headers)
                except Exception as exc: result["errors"].append(f"Supabase signals: {str(exc)[:120]}")
        return result

    @staticmethod
    def editorial_facts(snapshot):
        facts=[]; ga=snapshot.get("gift_asset",{})
        def payload(value):
            if isinstance(value,dict) and isinstance(value.get("data"), (dict,list)): return value["data"]
            return value

        greed=payload(ga.get("greed",{}))
        if isinstance(greed,dict):
            ranked=sorted(((n,d.get("score")) for n,d in greed.items() if isinstance(d,dict) and isinstance(d.get("score"),(int,float))),key=lambda x:x[1],reverse=True)[:5]
            if ranked: facts.append("Топ greed index: "+", ".join(f"{n} {v:.1f}" for n,v in ranked))
        health=payload(ga.get("health",{}))
        if isinstance(health,dict):
            ranked=sorted(((n,d.get("health_index"),d.get("total_liquidity")) for n,d in health.items() if isinstance(d,dict) and isinstance(d.get("health_index"),(int,float))),key=lambda x:x[1],reverse=True)[:5]
            if ranked: facts.append("Топ health index: "+", ".join(f"{n} {v:.1f} (ликвидность {liq})" for n,v,liq in ranked))
        prices=payload(ga.get("prices",{}))
        if isinstance(prices,dict):
            floors=prices.get("collection_floors",prices)
            rows=[]
            if isinstance(floors,dict):
                for collection,providers in floors.items():
                    if not isinstance(providers,dict): continue
                    numeric=[(name,value) for name,value in providers.items() if isinstance(value,(int,float))]
                    if numeric:
                        name,value=min(numeric,key=lambda item:item[1]); rows.append((collection,name,value))
            if rows: facts.append("Минимальные floor по площадкам: "+", ".join(f"{c} — {v:g} TON ({p})" for c,p,v in rows[:8]))
        volumes=payload(ga.get("volumes",{}))
        if isinstance(volumes,dict):
            leaders=[]
            for provider,collections in volumes.items():
                if not isinstance(collections,dict): continue
                for collection,data in collections.items():
                    if isinstance(data,dict) and isinstance(data.get("hour_sales"),(int,float)):
                        leaders.append((data["hour_sales"],collection,provider))
            leaders.sort(reverse=True)
            if leaders: facts.append("Продажи за последний час: "+", ".join(f"{c} — {n:g} ({p})" for n,c,p in leaders[:8]))
        signals=snapshot.get("own_signals",[])
        if isinstance(signals,list) and signals: facts.append("Последние собственные сигналы JSON: "+json.dumps(signals[:8],ensure_ascii=False,default=str)[:5000])
        return "\n".join(facts)

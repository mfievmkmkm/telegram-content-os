from collections import Counter
from datetime import datetime

from supabase import create_client


class SupabaseDatabase:
    """Same storage contract as SQLite Database, backed by Supabase REST."""

    def __init__(self,url,key,timezone):
        self.client=create_client(url,key); self.timezone=timezone

    def init(self):
        # Tables are created once with supabase_schema.sql.
        self.client.table("content_os_settings").select("key").limit(1).execute()

    def set(self,key,value):
        self.client.table("content_os_settings").upsert({"key":key,"value":value},on_conflict="key").execute()

    def get(self,key):
        rows=self.client.table("content_os_settings").select("value").eq("key",key).limit(1).execute().data
        return rows[0]["value"] if rows else None

    def used_hashes(self,channel_key):
        rows=self.client.table("content_os_drafts").select("source_hash").eq("channel_key",channel_key).not_.is_("source_hash","null").execute().data
        return {row["source_hash"] for row in rows}

    def save_draft(self,channel_key,format_key,text,hook_score,title="",url="",source_hash=None):
        payload={"channel_key":channel_key,"format_key":format_key,"text":text,"hook_score":hook_score,
                 "source_title":title,"source_url":url,"source_hash":source_hash,"created_at":datetime.now(self.timezone).isoformat()}
        rows=self.client.table("content_os_drafts").insert(payload).execute().data
        return rows[0]["id"]

    def draft(self,draft_id):
        rows=self.client.table("content_os_drafts").select("*").eq("id",draft_id).limit(1).execute().data
        return rows[0] if rows else None

    def update(self,draft_id,**fields):
        allowed={"text","hook_score","status","scheduled_at","published_at","published_message_id"}
        clean={k:v for k,v in fields.items() if k in allowed}
        if clean: self.client.table("content_os_drafts").update(clean).eq("id",draft_id).execute()

    def scheduled(self,now):
        return self.client.table("content_os_drafts").select("*").eq("status","scheduled").lte("scheduled_at",now).execute().data

    def future_scheduled(self,now,limit=30):
        return self.client.table("content_os_drafts").select("*").eq("status","scheduled").gt("scheduled_at",now).order("scheduled_at").limit(limit).execute().data

    def published_for_metrics(self,limit=100):
        return self.client.table("content_os_drafts").select("*").eq("status","published").not_.is_("published_message_id","null").order("published_at",desc=True).limit(limit).execute().data

    def save_video_job(self,draft_id,payload):
        rows=self.client.table("content_os_video_jobs").insert({"draft_id":draft_id,"payload":payload,"created_at":datetime.now(self.timezone).isoformat()}).execute().data
        return rows[0]["id"]

    def save_channel_post(self,channel_key,source_channel,source_role,post_id,text,views=None,posted_at=None,
                          reactions=0,forwards=0,media_kind=None,media_ref=None):
        payload={"channel_key":channel_key,"source_channel":source_channel,"source_role":source_role,
                 "telegram_post_id":post_id,"text":text,"views":views,"reactions":reactions,"forwards":forwards,
                 "media_kind":media_kind,"media_ref":media_ref,"posted_at":posted_at,"imported_at":datetime.now(self.timezone).isoformat()}
        existing=self.client.table("content_os_channel_posts").select("id").eq("source_channel",source_channel).eq("telegram_post_id",post_id).limit(1).execute().data
        if existing: return False
        self.client.table("content_os_channel_posts").insert(payload).execute(); return True

    def style_examples(self,channel_key,limit=6):
        return self.client.table("content_os_channel_posts").select("text").eq("channel_key",channel_key).eq("source_role","own").order("telegram_post_id",desc=True).limit(limit).execute().data

    def radar_posts(self,channel_key,limit=8):
        return self.client.table("content_os_channel_posts").select("text").eq("channel_key",channel_key).eq("source_role","radar").order("telegram_post_id",desc=True).limit(limit).execute().data

    def import_counts(self):
        rows=self.client.table("content_os_channel_posts").select("source_channel,source_role").execute().data
        counts=Counter((r["source_channel"],r["source_role"]) for r in rows)
        return [{"source_channel":k[0],"source_role":k[1],"count":v} for k,v in counts.items()]

    def save_metrics(self,draft_id,views,reactions,forwards):
        engagement=((reactions+forwards*2)/views*100) if views else 0
        self.client.table("content_os_post_metrics").insert({"draft_id":draft_id,"views":views,"reactions":reactions,
          "forwards":forwards,"engagement":engagement,"captured_at":datetime.now(self.timezone).isoformat()}).execute()

    def analytics_summary(self,limit=10):
        drafts=self.client.table("content_os_drafts").select("id,channel_key,format_key,hook_score,text").eq("status","published").execute().data
        metrics=self.client.table("content_os_post_metrics").select("*").order("captured_at",desc=True).execute().data
        latest={}
        for row in metrics: latest.setdefault(row["draft_id"],row)
        result=[]
        for draft in drafts:
            metric=latest.get(draft["id"])
            if metric: result.append({**draft,**{k:metric[k] for k in ("views","reactions","forwards","engagement")}})
        return sorted(result,key=lambda x:(x["engagement"],x["views"]),reverse=True)[:limit]

    def editorial_insights(self,channel_key):
        rows=[row for row in self.analytics_summary(500) if row["channel_key"]==channel_key]; grouped={}
        for row in rows: grouped.setdefault(row["format_key"],[]).append(float(row["engagement"]))
        result=[{"format_key":key,"avg_er":sum(values)/len(values),"samples":len(values)} for key,values in grouped.items() if len(values)>=2]
        return sorted(result,key=lambda x:x["avg_er"],reverse=True)[:3]

    def save_match_job(self,source_type,source_ref,player_ref,analysis_mode):
        now=datetime.now(self.timezone).isoformat()
        rows=self.client.table("content_os_match_jobs").insert({"source_type":source_type,"source_ref":source_ref,
          "player_ref":player_ref,"analysis_mode":analysis_mode,"created_at":now,"updated_at":now}).execute().data
        return rows[0]["id"]

    def update_match_job(self,job_id,**fields):
        allowed={"external_id","status","progress","result_url","error","metrics_json"}; clean={k:v for k,v in fields.items() if k in allowed}
        clean["updated_at"]=datetime.now(self.timezone).isoformat()
        self.client.table("content_os_match_jobs").update(clean).eq("id",job_id).execute()

    def match_job(self,job_id):
        rows=self.client.table("content_os_match_jobs").select("*").eq("id",job_id).limit(1).execute().data
        return rows[0] if rows else None

    def save_player(self,display_name,birth_year=None,position="",strong_foot=""):
        rows=self.client.table("content_os_players").insert({"display_name":display_name,"birth_year":birth_year,
          "position":position,"strong_foot":strong_foot,"created_at":datetime.now(self.timezone).isoformat()}).execute().data
        return rows[0]["id"]

    def players(self): return self.client.table("content_os_players").select("*").order("id",desc=True).execute().data

    def link_player_match(self,player_id,match_job_id):
        self.client.table("content_os_player_matches").upsert({"player_id":player_id,"match_job_id":match_job_id,
          "created_at":datetime.now(self.timezone).isoformat()},on_conflict="player_id,match_job_id").execute()

    def player_report(self,player_id):
        players=self.client.table("content_os_players").select("*").eq("id",player_id).limit(1).execute().data
        links=self.client.table("content_os_player_matches").select("match_job_id").eq("player_id",player_id).execute().data
        ids=[row["match_job_id"] for row in links]
        matches=self.client.table("content_os_match_jobs").select("*").in_("id",ids).order("created_at").execute().data if ids else []
        return (players[0] if players else None),matches

    def save_service_order(self,user_id,username,offer_key,brief):
        rows=self.client.table("content_os_service_orders").insert({"user_id":user_id,"username":username,
          "offer_key":offer_key,"brief":brief,"created_at":datetime.now(self.timezone).isoformat()}).execute().data
        return rows[0]["id"]

    def service_orders(self,status="new",limit=30):
        return self.client.table("content_os_service_orders").select("*").eq("status",status).order("id",desc=True).limit(limit).execute().data

    def service_order(self,order_id):
        rows=self.client.table("content_os_service_orders").select("*").eq("id",order_id).limit(1).execute().data
        return rows[0] if rows else None

    def update_service_order(self,order_id,status):
        self.client.table("content_os_service_orders").update({"status":status}).eq("id",order_id).execute()

    def save_funnel_event(self,user_id,event_type,source="",offer_key=""):
        self.client.table("content_os_funnel_events").insert({"user_id":user_id,"event_type":event_type,
          "source":source or None,"offer_key":offer_key or None,"created_at":datetime.now(self.timezone).isoformat()}).execute()

    def funnel_events(self,limit=5000):
        return self.client.table("content_os_funnel_events").select("*").order("id",desc=True).limit(limit).execute().data

    def save_course_note(self,source_channel,message_id,text,posted_at=None):
        existing=self.client.table("content_os_course_notes").select("id").eq("source_channel",source_channel).eq("message_id",message_id).limit(1).execute().data
        if existing: return False
        self.client.table("content_os_course_notes").insert({"source_channel":source_channel,"message_id":message_id,"text":text,
          "posted_at":posted_at,"imported_at":datetime.now(self.timezone).isoformat()}).execute(); return True

    def course_snippets(self,limit=12):
        return self.client.table("content_os_course_notes").select("text,source_channel").order("id",desc=True).limit(limit).execute().data

    def course_stats(self,limit=12):
        rows=self.client.table("content_os_course_notes").select("source_channel,text").execute().data; grouped={}
        for row in rows:
            item=grouped.setdefault(row["source_channel"],{"source_channel":row["source_channel"],"count":0,"chars":0})
            item["count"]+=1; item["chars"]+=len(row.get("text") or "")
        return sorted(grouped.values(),key=lambda item:item["count"],reverse=True)[:limit]

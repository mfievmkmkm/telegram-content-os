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

    def published_for_metrics(self,limit=100):
        return self.client.table("content_os_drafts").select("*").eq("status","published").not_.is_("published_message_id","null").order("published_at",desc=True).limit(limit).execute().data

    def save_video_job(self,draft_id,payload):
        rows=self.client.table("content_os_video_jobs").insert({"draft_id":draft_id,"payload":payload,"created_at":datetime.now(self.timezone).isoformat()}).execute().data
        return rows[0]["id"]

    def save_channel_post(self,channel_key,source_channel,source_role,post_id,text,views=None,posted_at=None):
        payload={"channel_key":channel_key,"source_channel":source_channel,"source_role":source_role,
                 "telegram_post_id":post_id,"text":text,"views":views,"posted_at":posted_at,"imported_at":datetime.now(self.timezone).isoformat()}
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

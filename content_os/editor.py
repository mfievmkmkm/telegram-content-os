import asyncio
import hashlib
import html
import random

import aiohttp
from .channels import CHANNELS, CONTENT_LANES, FORMAT_ROTATION, FORMAT_RULES, POST_RULES
from .hooks import score_hook
from .sources import collect_items
from .formatting import clean_generated_post, decorate_post, plain_text
from .course_retrieval import select_course_snippets
from .fact_layer import FactPack, FactStore


class Editor:
    def __init__(self, settings, database): self.settings, self.db = settings, database

    async def llm(self, system, prompt, temperature=.85):
        if not self.settings.llm_key: raise RuntimeError("LLM_API_KEY не задан")
        payload = {"model": self.settings.llm_model,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],
                   "temperature":temperature,"max_tokens":1600}
        headers = {"Authorization":f"Bearer {self.settings.llm_key}","Content-Type":"application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post(f"{self.settings.llm_url}/chat/completions",json=payload,headers=headers) as response:
                body = await response.text()
                if response.status >= 400: raise RuntimeError(f"LLM HTTP {response.status}: {body[:240]}")
                return (await response.json())["choices"][0]["message"]["content"].strip()

    async def material(self, channel_key):
        if random.random() < .35: return {"title":random.choice(CHANNELS[channel_key]["topics"]),"url":"","summary":""}
        used = self.db.used_hashes(channel_key)
        for item in await asyncio.to_thread(collect_items, channel_key):
            if item["url"] and hashlib.sha256(item["url"].encode()).hexdigest() not in used: return item
        return {"title":random.choice(CHANNELS[channel_key]["topics"]),"url":"","summary":""}

    @staticmethod
    def format_rule(format_key):
        return FORMAT_RULES.get(format_key,"350–700 знаков. Один сильный угол, без воды и повторов.")

    @staticmethod
    def complete(text):
        """Reject visibly truncated LLM answers before they become drafts."""
        value=plain_text(text).strip(); words=value.split(); tail=words[-1].strip(".,!?—–:;") if words else ""
        return len(value)>=90 and bool(words) and not (len(tail)==1 and tail.isalpha())

    async def finish(self,cfg,text,context):
        text=clean_generated_post(text)
        if not self.complete(text):
            text=clean_generated_post(await self.llm(cfg["voice"]+POST_RULES,
                f"Текст оборван или не закончен. Напиши его заново целиком, без выдуманных фактов. {context}\n\n{text}",.82))
        if not self.complete(text): raise RuntimeError("LLM дважды вернул оборванный текст — черновик отклонён")
        return text

    async def create(self, channel_key):
        cfg, material = CHANNELS[channel_key], await self.material(channel_key)
        counter=int(self.db.get(f"editorial_rotation:{channel_key}") or 0); self.db.set(f"editorial_rotation:{channel_key}",str(counter+1))
        rotation=FORMAT_ROTATION[channel_key]; format_key=rotation[counter%len(rotation)]
        lanes=CONTENT_LANES[channel_key]; lane=lanes[counter%len(lanes)]
        facts = (f"Заголовок: {material['title']}\nФрагмент: {material['summary']}\n"
                 f"Источник: {material.get('source_name','internet')} · рейтинг {material.get('score','—')}\nURL: {material['url']}") if material["url"] else f"Тема: {material['title']}"
        examples=[row["text"][:1000] for row in self.db.style_examples(channel_key)]
        style=("\n\nПРИМЕРЫ НАШИХ ПРОШЛЫХ ПОСТОВ — возьми ритм и характер, но не повторяй фразы:\n---\n"+"\n---\n".join(examples)) if examples else ""
        radar=[]
        if channel_key=="gifts":
            for row in self.db.radar_posts(channel_key):
                first=next((line.strip() for line in row["text"].splitlines() if line.strip()),"")
                if first: radar.append(first[:180])
        trends=("\n\nЧУЖОЙ РАДАР ТЕМ — используй только как сигнал интереса. Не копируй формулировки и выводы:\n- "+"\n- ".join(radar)) if radar else ""
        insights=self.db.editorial_insights(channel_key)
        learned=("\n\nНАША СТАТИСТИКА: лучше всего работают "+", ".join(f"{x['format_key']} (ER {x['avg_er']:.2f}%, {x['samples']} пост.)" for x in insights)+
                 ". Это ориентир для ритма и угла, но не повод повторять тему.") if insights else ""
        prompt = (f"Рубрика: {format_key}. Тематический угол этого выпуска: {lane}. Формат: {self.format_rule(format_key)} "
                  f"Создай оригинальный пост. Не своди каждый Gifts-пост к floor/FOMO и каждый футбольный пост к страху тренера.\n{facts}{style}{trends}{learned}")
        text = await self.finish(cfg,await self.llm(cfg["voice"]+POST_RULES,prompt),"Сохрани заданную рубрику и объём.")
        score, reasons = score_hook(plain_text(text))
        if score < 3:
            text = await self.llm(cfg["voice"]+POST_RULES,
                f"Хук получил {score}/5. Проблемы: {', '.join(reasons)}. Перепиши весь пост, начни намного сильнее.\n\n{text}",.95)
            text = await self.finish(cfg,text,"Сохрани заданную рубрику и объём.")
            score, _ = score_hook(plain_text(text))
        text=decorate_post(text,channel_key)
        digest = hashlib.sha256(material["url"].encode()).hexdigest() if material["url"] else None
        return self.db.save_draft(channel_key,format_key,text,score,material["title"],material["url"],digest)

    async def rewrite(self, draft, mode):
        instructions={"harder":"Усиль конфликт, сарказм и первую строку. Не меняй факты.",
                      "rewrite":"Полностью другой заход и структура. Сохрани факты.",
                      "short":"Сократи до 500–700 знаков, оставь ударные мысли."}
        text=clean_generated_post(await self.llm(CHANNELS[draft["channel_key"]]["voice"]+POST_RULES,
                            f"{instructions[mode]} Сохрани характер рубрики: {self.format_rule(draft['format_key'])} Верни только пост.\n\n{draft['text']}"))
        text=decorate_post(text,draft["channel_key"])
        return text, score_hook(plain_text(text))[0]

    async def create_gifts_data_post(self,facts):
        if not facts: raise RuntimeError("Рыночные источники не вернули пригодных данных")
        prompt=("Создай пост только по фактам ниже. Выбери один неожиданный конфликт, а не перечисляй всё. "
                "Не называй это сигналом на покупку. Все использованные цифры сохрани точно. Данные каталога НЕ доказывают "
                "ликвидность, продажи, спрос, сделки, floor или будущую цену — запрещено делать такие выводы без прямых данных.\n\nДАННЫЕ:\n"+facts)
        cfg=CHANNELS["gifts"]
        text=await self.finish(cfg,await self.llm(cfg["voice"]+POST_RULES,prompt,.8),"Не делай выводов, которых нет в данных."); score,_=score_hook(plain_text(text))
        if score<3:
            text=await self.llm(CHANNELS["gifts"]["voice"]+POST_RULES,f"Перепиши с более сильным хуком. Данные не меняй.\n{text}",.9)
            text=await self.finish(cfg,text,"Не делай выводов, которых нет в данных."); score,_=score_hook(plain_text(text))
        text=decorate_post(text,"gifts")
        draft_id=self.db.save_draft("gifts","data_desk",text,score,"Gifts Data Desk","",None)
        FactStore(self.db).save(draft_id,FactPack.create(facts,"Gifts Market Desk"))
        return draft_id

    async def create_match_data_post(self,facts):
        prompt=("Создай оригинальный пост о КОНКРЕТНОМ матче только по данным ниже. Названия обеих команд должны быть в первых двух строках. "
                "Если указан РЕЖИМ ПРЕВЬЮ — не пиши, будто матч уже состоялся: дай интригу, форму/H2H и что смотреть. "
                "Если указан РЕЖИМ РАЗБОРА — обязательно назови счёт, ключевое событие и 2–4 точные цифры. Не перечисляй всю статистику: "
                "найди один конфликт или показатель, который меняет понимание игры. Разделяй факт и своё объяснение. "
                "Не придумывай xG, цитаты и действия игроков, которых нет в данных.\n\nДАННЫЕ:\n"+facts)
        text=clean_generated_post(await self.llm(CHANNELS["liga"]["voice"]+POST_RULES,prompt,.78)); score,_=score_hook(plain_text(text))
        if score<3:
            text=clean_generated_post(await self.llm(CHANNELS["liga"]["voice"]+POST_RULES,f"Усиль первую строку, не меняя факты.\n{text}",.88)); score,_=score_hook(plain_text(text))
        text=decorate_post(text,"liga")
        draft_id=self.db.save_draft("liga","match_radar",text,score,"Match Radar","",None)
        FactStore(self.db).save(draft_id,FactPack.create(facts,"Match Radar"))
        return draft_id

    async def create_from_courses(self,channel_key):
        snippets=select_course_snippets(self.db.course_snippets(200),channel_key,7)
        if not snippets: raise RuntimeError("База курсов пока пуста — сначала запусти /coursesync или загрузи ZIP")
        knowledge="\n---\n".join(row["text"][:1300] for row in snippets)
        prompt=("Ниже приватные учебные заметки, к которым владелец имеет доступ. Извлеки ОДИН общий принцип психологии, продаж, внимания или принятия решений. "
                "Не цитируй, не называй автора или курс, не воспроизводи структуру урока. Полностью переосмысли принцип для аудитории канала. "
                "Если материал про оффер или продажи, используй только честные элементы: конкретная боль, измеримая ценность, снятие риска и один CTA; не выдумывай дефицит. "
                f"Формат: {self.format_rule('course_insight')}\n\n"+knowledge)
        cfg=CHANNELS[channel_key]; text=clean_generated_post(await self.llm(cfg["voice"]+POST_RULES,prompt,.86)); score,reasons=score_hook(plain_text(text))
        if score<3:
            text=clean_generated_post(await self.llm(cfg["voice"]+POST_RULES,
                f"Переосмысли материал ещё раз и усили первую строку. Проблемы хука: {', '.join(reasons)}. Не называй курс и не добавляй факты.\n\n{text}",.92))
            score,_=score_hook(plain_text(text))
        text=decorate_post(text,channel_key)
        return self.db.save_draft(channel_key,"course_insight",text,score,"Course Intelligence","",None)

    async def create_from_brief(self,channel_key,format_key,brief,title="Своя тема",url=""):
        cfg=CHANNELS[channel_key]; examples=[row["text"][:1000] for row in self.db.style_examples(channel_key)]
        style=("\n\nНАШ РИТМ — не копируй фразы:\n---\n"+"\n---\n".join(examples)) if examples else ""
        prompt=(f"Рубрика: {format_key}. Требования к объёму и структуре: {self.format_rule(format_key)} Создай оригинальный пост по редакторскому заданию. "
                "Если в задании мало фактов, не додумывай цифры и цитаты: сделай мнение, практический разбор или вопрос.\n\n"
                f"ЗАДАНИЕ:\n{brief[:8000]}{style}")
        text=await self.finish(cfg,await self.llm(cfg["voice"]+POST_RULES,prompt,.88),"Сохрани редакторское задание и объём."); score,reasons=score_hook(plain_text(text))
        if score<3:
            text=await self.finish(cfg,await self.llm(cfg["voice"]+POST_RULES,f"Усиль хук. Проблемы: {', '.join(reasons)}. Факты не меняй.\n\n{text}",.95),"Сохрани редакторское задание и объём."); score,_=score_hook(plain_text(text))
        if score<3: raise RuntimeError(f"Слабый хук {score}/5 — черновик отклонён, попробуй ещё раз")
        text=decorate_post(text,channel_key); digest=hashlib.sha256(url.encode()).hexdigest() if url else None
        return self.db.save_draft(channel_key,format_key,text,score,title,url,digest)

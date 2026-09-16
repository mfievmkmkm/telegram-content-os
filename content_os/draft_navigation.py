from aiogram.enums import ParseMode

from .remix_runtime import send_block
from .formatting import plain_text


async def back_to_draft(legacy, callback, state):
    if not legacy.admin(callback): return
    raw = callback.data.rsplit(":", 1)[-1]
    if not raw.isdigit(): return await callback.answer("Некорректный черновик", show_alert=True)
    draft = legacy.db.draft(int(raw))
    if not draft or dict(draft).get("status") == "deleted":
        return await callback.answer("Черновик не найден или удалён", show_alert=True)
    await state.clear()
    await callback.answer()
    # Navigation must not polish, rewrite or charge the LLM again.
    rendered = legacy.render(draft["channel_key"], draft["text"])
    if len(rendered.encode("utf-16-le")) // 2 <= 3500:
        await callback.message.answer(f"<b>Исходник · #{raw}</b>\n\n{rendered}", parse_mode=ParseMode.HTML)
    else:
        await send_block(callback.message, f"Исходник · #{raw}", plain_text(draft["text"]))
    await callback.message.answer("Действия с исходником", parse_mode=ParseMode.HTML, reply_markup=legacy.keyboard(int(raw)))

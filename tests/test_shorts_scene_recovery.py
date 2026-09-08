import asyncio

from content_os.shorts.models import ShortBrief, ShortScene
from content_os.shorts.scenes import ShortSceneService


def brief(channel="gifts"):
    return ShortBrief(
        title="title",
        hook="hook",
        voiceover=" ".join(["слово"] * 75),
        scenes=[ShortScene(4, f"old visual {index}", f"copy {index}") for index in range(8)],
        caption="caption",
        music_mood="dark",
        cta="cta",
        channel=channel,
        draft_id=7,
    )


class WrappedEditor:
    async def llm(self, *_args):
        scenes = ",".join(
            f'{{"seconds":9,"visual":"new visual {index}","screen_text":"wrong","asset_type":"stock_video"}}'
            for index in range(8)
        )
        return '{"result":{"scenes":[' + scenes + ']}}'


class BrokenEditor:
    async def llm(self, *_args):
        return "Вот более сильные варианты, но без JSON"


def test_scene_remix_accepts_wrapped_array_and_keeps_copy_and_timing():
    result = asyncio.run(ShortSceneService(WrappedEditor()).remix(brief()))
    assert len(result) == 8
    assert result[0].visual == "new visual 0"
    assert result[0].seconds == 4
    assert result[0].screen_text == "copy 0"


def test_scene_remix_recovers_from_missing_array_with_distinct_visuals():
    result = asyncio.run(ShortSceneService(BrokenEditor()).remix(brief()))
    assert len(result) == 8
    assert len({scene.visual for scene in result}) == 8
    assert sum(scene.asset_type == "brand_card" for scene in result) == 2
    assert all(scene.screen_text == f"copy {index}" for index, scene in enumerate(result))

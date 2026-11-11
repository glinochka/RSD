"""Custom AI content factory: settings, accounts, pipeline, anti-fraud."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import CustomAdmin, CustomAutomation, CustomAutomationCredential
from app.services.custom.content_factory_antifraud import (
    caption_variant,
    factory_return_url,
    pick_media_kind,
    hook_is_strong,
    uniqualize_recipe,
    uniqueness_hash,
    warmup_progress,
)
from app.utils.security import get_password_hash

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="cf_admin",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)
    return admin


@pytest.fixture
async def custom_automation(test_session: AsyncSession, custom_admin: CustomAdmin) -> CustomAutomation:
    from app.services.account_pool_service import get_or_create_default_pool
    from app.services.custom.prompt_service import create_default_prompts

    automation = CustomAutomation(
        name="Content Factory",
        client_name="Factory Client",
        status="active",
        created_by_admin_id=custom_admin.id,
    )
    test_session.add(automation)
    await test_session.flush()
    await get_or_create_default_pool(test_session, automation.id)
    await create_default_prompts(test_session, automation.id)
    await test_session.commit()
    await test_session.refresh(automation)
    return automation


@pytest.fixture
async def client_token(client: AsyncClient, test_session: AsyncSession, custom_automation: CustomAutomation) -> str:
    credential = CustomAutomationCredential(
        custom_automation_id=custom_automation.id,
        username="cf_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    response = await client.post("/api/custom/login", json={"username": "cf_client", "password": "password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_hook_and_uniqualization():
    assert hook_is_strong("Стоп. Вот почему холодный аккаунт сжигает охваты.")
    assert not hook_is_strong("Привет")
    youtube = uniqualize_recipe(platform="youtube", seed="v1", enabled=True)
    tiktok = uniqualize_recipe(platform="tiktok", seed="v1", enabled=True)
    assert youtube["speed"] != tiktok["speed"] or youtube["crop_pct"] != tiktok["crop_pct"]
    assert uniqueness_hash(script="a", hook="b", recipes=youtube) != uniqueness_hash(
        script="a", hook="b", recipes=tiktok
    )
    captions = {
        "youtube": caption_variant("База", "youtube", "https://x.test", "seed", hashtags=["saas", "growth"]),
        "instagram": caption_variant("База", "instagram", "https://x.test", "seed", hashtags=["saas"]),
    }
    assert captions["youtube"] != captions["instagram"]
    assert "https://x.test" in captions["youtube"]
    assert "#saas" in captions["youtube"]
    varied = {
        caption_variant("База", "vk", "", f"account-{index}", hashtags=["one", "two"])
        for index in range(12)
    }
    assert len(varied) >= 3
    assert factory_return_url("https://evil.test/phish", 9, base_url="https://app.test") == "https://app.test/custom/automations/9/content-factory/accounts"
    assert factory_return_url(
        "https://evil.test/custom/automations/9/content-factory/accounts",
        9,
        base_url="https://app.test",
    ) == "https://app.test/custom/automations/9/content-factory/accounts"
    assert factory_return_url(
        "https://app.test/custom/automations/9/content-factory/accounts",
        9,
        base_url="https://app.test",
    ).endswith("/content-factory/accounts")


def test_warmup_needs_time_and_actions():
    from datetime import datetime, timedelta

    started = datetime.utcnow() - timedelta(days=8)
    early = warmup_progress(
        started_at=datetime.utcnow() - timedelta(hours=2),
        completed_at=None,
        actions_done=80,
        warmup_days=7,
        actions_per_day=8,
    )
    done = warmup_progress(
        started_at=started,
        completed_at=None,
        actions_done=80,
        warmup_days=7,
        actions_per_day=8,
    )
    assert early["complete"] is False
    assert done["complete"] is True


async def test_settings_roundtrip_hides_secrets(client: AsyncClient, custom_automation: CustomAutomation, client_token: str):
    automation_id = custom_automation.id
    created = await client.get(
        f"/api/custom/automations/{automation_id}/content-factory/settings",
        headers=_auth(client_token),
    )
    assert created.status_code == 200
    body = created.json()
    assert body["enabled"] is False
    assert body["sandbox_mode"] is True
    assert "openai_api_key" not in body
    assert body["openai_api_key_set"] is False

    updated = await client.put(
        f"/api/custom/automations/{automation_id}/content-factory/settings",
        headers=_auth(client_token),
        json={
            "enabled": True,
            "product_name": "RSD Flow",
            "audience": "основатели SaaS",
            "content_formats": ["educational", "storytelling"],
            "visual_styles": ["realism"],
            "openai_api_key": "sk-test-secret",
            "videos_per_day": 2,
        },
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()
    assert data["enabled"] is True
    assert data["product_name"] == "RSD Flow"
    assert data["openai_api_key_set"] is True
    assert "sk-test-secret" not in str(data)


async def test_account_connect_and_generate_sandbox(
    client: AsyncClient,
    custom_automation: CustomAutomation,
    client_token: str,
):
    automation_id = custom_automation.id
    prepared = await client.put(
        f"/api/custom/automations/{automation_id}/content-factory/settings",
        headers=_auth(client_token),
        json={"product_name": "RSD Flow", "audience": "основатели SaaS"},
    )
    assert prepared.status_code == 200, prepared.text

    blocked = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/accounts",
        headers=_auth(client_token),
        json={"platform": "instagram", "display_name": "IG", "credentials": {"access_token": "tok"}},
    )
    assert blocked.status_code == 400

    connected = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/accounts",
        headers=_auth(client_token),
        json={
            "platform": "youtube",
            "display_name": "Demo Shorts",
            "handle": "@demo",
            "credentials": {"refresh_token": "refresh-demo", "access_token": "access-demo"},
        },
    )
    assert connected.status_code == 201, connected.text
    account = connected.json()
    assert account["platform"] == "youtube"
    assert account["has_credentials"] is True
    assert "refresh_token" not in str(account)
    assert account["status"] == "warming"
    assert account["warmup"]["complete"] is False

    generated = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/generate",
        headers=_auth(client_token),
    )
    assert generated.status_code == 200, generated.text
    video = generated.json()
    assert video["hook"]
    assert hook_is_strong(video["hook"]) or len(video["hook"]) > 12
    assert video["script"]
    assert video["uniqueness_hash"]
    assert video["status"] in {"posted", "ready", "sandbox"} or video["posts"]
    if video["posts"] and all(item["status"] == "sandbox" for item in video["posts"]):
        assert video["status"] == "sandbox"
    assert video["token_cost_usd"] >= 0
    if video["posts"]:
        assert video["posts"][0]["status"] in {"sandbox", "posted", "held"}
        if video["posts"][0]["status"] == "sandbox":
            assert not video["posts"][0]["posted_url"]

    dashboard = await client.get(
        f"/api/custom/automations/{automation_id}/content-factory",
        headers=_auth(client_token),
    )
    assert dashboard.status_code == 200
    kpis = dashboard.json()["kpis"]
    assert kpis["in_flight"] + kpis["posted"] >= 1
    assert kpis["accounts_total"] == 1


async def test_live_posting_waits_for_warmup(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from app.services.custom.content_factory_pipeline import generate_now
    from app.services.custom.content_factory_service import (
        apply_settings_update,
        connect_account,
        get_or_create_settings,
    )

    async def _no_llm(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.custom.content_factory_pipeline._llm_json", _no_llm)
    settings = await get_or_create_settings(test_session, custom_automation.id)
    apply_settings_update(settings, {
        "sandbox_mode": False,
        "enabled": True,
        "product_name": "Live SaaS",
        "posting_window_start": "00:00",
        "posting_window_end": "23:59",
        "timezone": "UTC",
    })
    account = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="tiktok",
        display_name="Fresh",
        handle="@fresh",
        external_id="tt1",
        credentials={"access_token": "tok"},
    )
    video = await generate_now(test_session, custom_automation.id)
    await test_session.commit()
    from sqlalchemy import select
    from app.alembic.models import CustomContentFactoryPost

    posts = list(
        (
            await test_session.execute(
                select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == video.id)
            )
        ).scalars().all()
    )
    assert posts
    assert posts[0].status == "held"
    assert "Прогрев" in (posts[0].hold_reason or "")
    assert account.status == "warming"


async def test_generate_requires_product(client: AsyncClient, custom_automation: CustomAutomation, client_token: str):
    response = await client.post(
        f"/api/custom/automations/{custom_automation.id}/content-factory/generate",
        headers=_auth(client_token),
    )
    assert response.status_code == 400


async def test_retry_and_skip_video(
    client: AsyncClient,
    custom_automation: CustomAutomation,
    client_token: str,
):
    automation_id = custom_automation.id
    await client.put(
        f"/api/custom/automations/{automation_id}/content-factory/settings",
        headers=_auth(client_token),
        json={"product_name": "Retry SaaS"},
    )
    generated = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/generate",
        headers=_auth(client_token),
    )
    assert generated.status_code == 200, generated.text
    video_id = generated.json()["id"]
    skipped = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/videos/{video_id}/skip",
        headers=_auth(client_token),
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    retried = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/videos/{video_id}/retry",
        headers=_auth(client_token),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] in {"queued", "rendering", "uniqualizing", "ready", "posted", "sandbox"}


def test_plan_clip_durations_covers_brief():
    from app.services.custom.content_factory_media import plan_clip_durations

    for total in (8, 16, 30, 35, 45, 60):
        parts = plan_clip_durations(total)
        assert parts
        assert all(5 <= part <= 8 for part in parts)
        assert len(parts) <= 8
        assert sum(parts) in {total, min(total, 64), min(8, total)} or abs(sum(parts) - min(total, 64)) <= len(parts)


async def test_multi_clip_kling_stitches_master(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
    tmp_path,
):
    from app.config import settings as app_settings
    from app.services.custom.content_factory_pipeline import generate_now
    from app.services.custom.content_factory_service import (
        apply_settings_update,
        connect_account,
        get_or_create_settings,
    )

    class FakeKling:
        def __init__(self, *args, **kwargs):
            pass

        async def submit_render(self, **kwargs):
            return str(kwargs.get("idempotency_key") or "task")

        async def poll_render(self, *, task_id: str):
            return {"status": "rendered", "video_url": f"https://clips.test/{task_id}.mp4"}

    async def fake_download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"clip-" + str(url).encode("utf-8")[-12:])
        return dest

    def fake_concat(paths, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"|".join(path.read_bytes() for path in paths))
        return dest

    def fake_uniq(*, source, dest, recipe, aspect_ratio):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes() + b"-uniq")
        return dest

    async def no_sleep(*_args, **_kwargs):
        return None

    async def _no_llm(*args, **kwargs):
        return None

    monkeypatch.setattr(app_settings, "MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.custom.content_factory_media.settings.MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.KlingClient", FakeKling)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.download_to_file", fake_download)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.concat_clips", fake_concat)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.uniqualize_file", fake_uniq)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.write_thumbnail", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.asyncio.sleep", no_sleep)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline._llm_json", _no_llm)

    settings = await get_or_create_settings(test_session, custom_automation.id)
    apply_settings_update(settings, {
        "sandbox_mode": True,
        "enabled": True,
        "product_name": "Stitch SaaS",
        "kling_api_key": "kling-test-key",
        "duration_min": 16,
        "duration_max": 16,
        "videos_per_day": 1,
    })
    await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="youtube",
        display_name="Shorts",
        handle="@shorts",
        external_id="yt1",
        credentials={"refresh_token": "refresh-demo", "access_token": "access-demo"},
    )
    video = await generate_now(test_session, custom_automation.id)
    await test_session.commit()

    assert video.status == "sandbox"
    extra = video.extra or {}
    assert extra.get("stitched") is True
    assert extra.get("clips_done") == extra.get("clips_total") == 2
    assert len(extra.get("clip_plan") or []) == 2
    assert video.video_url
    assert "master" in (video.video_url or "")
    recipes = video.uniqualization or {}
    assert recipes
    first = next(iter(recipes.values()))
    assert first.get("video_url")


def test_shadowban_counts_only_live_posts():
    from datetime import datetime, timedelta

    from app.services.custom.content_factory_antifraud import should_flag_shadowban

    old = datetime.utcnow() - timedelta(hours=40)
    sandbox = [{"status": "sandbox", "posted_at": old, "views": 0} for _ in range(4)]
    assert should_flag_shadowban(recent_posts=sandbox, threshold=3) is False
    live = [{"status": "posted", "posted_at": old, "views": 0, "views_known": True} for _ in range(3)]
    assert should_flag_shadowban(recent_posts=live, threshold=3) is True
    unknown = [{"status": "posted", "posted_at": old, "views": 0, "views_known": False} for _ in range(4)]
    assert should_flag_shadowban(recent_posts=unknown, threshold=3) is False


def test_publish_keeps_video_when_a_sibling_is_still_held():
    from datetime import datetime, timedelta

    from app.services.custom.content_factory_antifraud import (
        live_daily_cap,
        publish_attempt_due,
        settle_publish_status,
    )

    assert settle_publish_status(["held", "failed"], has_retryable_failure=True) == "ready"
    assert settle_publish_status(["held", "failed"], has_retryable_failure=False) == "ready"
    assert settle_publish_status(["failed", "failed"], has_retryable_failure=False) == "failed"
    assert settle_publish_status(["posted", "failed"], has_retryable_failure=False) == "posted"
    assert settle_publish_status(["processing", "held"], has_retryable_failure=False) == "posting"
    assert settle_publish_status(["sandbox", "sandbox"], has_retryable_failure=False) == "sandbox"

    now = datetime.utcnow()
    assert publish_attempt_due(attempts=1, retry_after=now + timedelta(minutes=10), now=now) is False
    assert publish_attempt_due(attempts=1, retry_after=now - timedelta(minutes=1), now=now) is True
    assert publish_attempt_due(attempts=4, retry_after=None, now=now) is False

    completed = now - timedelta(days=1)
    assert live_daily_cap(max_posts_per_day=4, warmup_completed_at=completed, owner_confirmed=False, now=now) == 1
    assert live_daily_cap(max_posts_per_day=4, warmup_completed_at=completed, owner_confirmed=False, ramp=False, now=now) == 4
    assert live_daily_cap(max_posts_per_day=4, warmup_completed_at=completed, owner_confirmed=True, now=now) == 4
    assert live_daily_cap(
        max_posts_per_day=4,
        warmup_completed_at=now - timedelta(days=4),
        owner_confirmed=False,
        now=now,
    ) == 2


async def test_accounts_list_and_mark_warmed(
    client: AsyncClient,
    custom_automation: CustomAutomation,
    client_token: str,
):
    automation_id = custom_automation.id
    connected = await client.post(
        f"/api/custom/automations/{automation_id}/content-factory/accounts",
        headers=_auth(client_token),
        json={
            "platform": "youtube",
            "display_name": "Demo Shorts",
            "credentials": {"refresh_token": "refresh-demo"},
        },
    )
    assert connected.status_code == 201, connected.text
    account_id = connected.json()["id"]
    assert connected.json()["warmup"]["complete"] is False

    listed = await client.get(
        f"/api/custom/automations/{automation_id}/content-factory/accounts",
        headers=_auth(client_token),
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["items"][0]["id"] == account_id
    assert "youtube_oauth_ready" in body

    warmed = await client.patch(
        f"/api/custom/automations/{automation_id}/content-factory/accounts/{account_id}",
        headers=_auth(client_token),
        json={"mark_warmed": True},
    )
    assert warmed.status_code == 200, warmed.text
    assert warmed.json()["status"] == "ready"
    assert warmed.json()["warmup"]["complete"] is True


def test_carousel_share_is_the_photo_slice():
    assert pick_media_kind(0, 1) == "video"
    assert pick_media_kind(30, 30) == "carousel"
    assert pick_media_kind(30, 31) == "video"
    assert pick_media_kind(100, 100) == "carousel"


def test_carousel_goes_to_photo_platforms_and_slideshow_elsewhere():
    from app.services.custom.content_factory_publishers import publish_uses_slides, vk_clip_url

    assert publish_uses_slides("instagram", "carousel") is True
    assert publish_uses_slides("tiktok", "carousel") is True
    assert publish_uses_slides("pinterest", "carousel") is True
    assert publish_uses_slides("youtube", "carousel") is False
    assert publish_uses_slides("vk", "carousel") is False
    assert vk_clip_url(-123, 456) == "https://vk.com/clip-123_456"


def test_one_grok_bot_returns_frames_in_swipe_order():
    import base64

    from app.services.custom.content_factory_media import factory_grok_bot_id, grok_agent_pack, grok_carousel_message

    assert factory_grok_bot_id(4) == factory_grok_bot_id(4)
    first = grok_carousel_message(company="Масштаб", description="ведём соцсети", audience="", niche="", brief="строгий стиль", avoid=["старая тема"], follow_up=False)
    again = grok_carousel_message(company="Масштаб", description="", audience="", niche="", brief="", avoid=[], follow_up=True)
    assert "Выбери тематику" in first
    assert "другой тематикой" in again
    assert "старая тема" in first
    blob = base64.b64encode(b"png-a").decode()
    blob_b = base64.b64encode(b"png-b").decode()
    pack = grok_agent_pack({
        "id": "resp_1",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": "Тема: очередь в кофейне"}]},
            {"type": "image_generation_call", "status": "completed", "prompt": "кадр 1", "result": blob},
            {"type": "image_generation_call", "status": "completed", "prompt": "кадр 2", "result": blob_b},
        ],
    })
    assert pack["response_id"] == "resp_1"
    assert [item["bytes"] for item in pack["images"]] == [b"png-a", b"png-b"]
    assert "очередь" in pack["text"]


async def test_grok_bot_carousel_reaches_sandbox(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
    tmp_path,
):
    from app.config import settings as app_settings
    from app.services.custom.content_factory_pipeline import generate_now
    from app.services.custom.content_factory_service import (
        apply_settings_update,
        connect_account,
        get_or_create_settings,
    )

    calls = {"llm": 0, "grok": 0}

    async def _no_llm(*_args, **_kwargs):
        calls["llm"] += 1
        return None

    async def fake_pack(**kwargs):
        calls["grok"] += 1
        folder = kwargs["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for index in range(6):
            dest = folder / f"slide-{index:02d}.png"
            dest.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index + 1]))
            paths.append(dest)
        return {
            "paths": paths,
            "prompts": [f"кадр {index + 1}" for index in range(6)],
            "text": "Стоп. Очередь в кофейне\nВторой кадр про смену",
            "response_id": "resp_e2e",
            "continued": False,
        }

    def fake_slides(slide_paths, dest, seconds=2.4):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"slideshow-" + str(len(slide_paths)).encode())
        return dest

    def fake_uniq(*, source, dest, recipe, aspect_ratio):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes() + b"-uniq")
        return dest

    monkeypatch.setattr(app_settings, "MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.custom.content_factory_media.settings.MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.custom.content_factory_pipeline._llm_json", _no_llm)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.generate_grok_carousel_pack", fake_pack)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.slides_to_mp4", fake_slides)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.uniqualize_file", fake_uniq)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.write_thumbnail", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.asyncio.sleep", lambda *_args, **_kwargs: None)

    settings = await get_or_create_settings(test_session, custom_automation.id)
    apply_settings_update(settings, {
        "sandbox_mode": True,
        "enabled": True,
        "product_name": "Кофейня",
        "image_provider": "grok",
        "xai_api_key": "xai-test",
        "carousel_share": 100,
        "music_mode": "off",
    })
    await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="instagram",
        display_name="IG",
        handle="@cafe",
        external_id="1789",
        credentials={"access_token": "tok", "ig_user_id": "1789"},
    )
    video = await generate_now(test_session, custom_automation.id)
    await test_session.commit()
    await test_session.refresh(settings)

    assert calls["llm"] == 0
    assert calls["grok"] == 1
    assert video.status == "sandbox"
    assert "кофейне" in (video.idea or "").lower() or "кофейне" in (video.hook or "").lower()
    assert len(video.storyboard or []) == 6
    assert (video.storyboard or [])[0].get("voiceover")
    extra = video.extra or {}
    assert extra.get("media_kind") == "carousel"
    assert extra.get("grok_bot_id", "").startswith("cf-carousel-")
    assert len(extra.get("slide_urls") or []) == 6
    assert video.video_url
    assert settings.grok_bot_response_id == "resp_e2e"
    from sqlalchemy import select
    from app.alembic.models import CustomContentFactoryPost

    posts = list(
        (
            await test_session.execute(
                select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == video.id)
            )
        ).scalars().all()
    )
    assert posts
    assert posts[0].status == "sandbox"
    assert posts[0].platform == "instagram"


def test_music_bed_is_an_original_wav(tmp_path):
    from app.services.custom.content_factory_media import voiceover_lines, write_music_bed

    bed = write_music_bed(tmp_path / "bed.wav", seconds=4, seed="clip-1")
    assert bed.read_bytes()[:4] == b"RIFF"
    assert bed.stat().st_size > 1000

    class _Video:
        hook = "Стоп. Это тот самый ролик."
        storyboard = [{"voiceover": "Кадр про новость"}, {"voiceover": "Кадр про новость"}]

    text = voiceover_lines(_Video())
    assert text.startswith("Стоп")
    assert text.count("Кадр про новость") == 1


def test_access_only_is_not_painted_healthy():
    from app.services.custom.content_factory_antifraud import credential_status, present_health_score
    from app.services.custom.content_factory_publishers import merge_platform_credentials

    instagram = credential_status("instagram", {"access_token": "tok", "ig_user_id": "1789"})
    assert instagram["credential_mode"] == "access_only"
    assert "refresh не отдаёт" in instagram["credential_note"]
    assert present_health_score(78, credential_mode="access_only", proxy_ok=True) <= 49

    youtube = credential_status("youtube", {"refresh_token": "refresh.from.platform", "access_token": "ya"})
    assert youtube["credential_mode"] == "refresh"
    saved = merge_platform_credentials(
        {"access_token": "old", "refresh_token": "refresh.from.platform"},
        {"access_token": "ya29.new"},
    )
    assert saved["refresh_token"] == "refresh.from.platform"
    assert saved["access_token"] == "ya29.new"


@pytest.mark.asyncio
async def test_factory_proxy_is_own_and_blocks_direct_publish(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from datetime import datetime, timedelta

    from app.alembic.models import AccountPool, CustomProxy, PoolAccount, SocialAccount
    from app.services.custom.content_factory_proxy import handshake_proxy, httpx_proxy_url, proxy_url_for_account
    from app.services.custom.content_factory_publishers import PublisherError, publish_to_platform
    from app.services.custom.content_factory_service import connect_account, decrypt_json
    from app.services.custom.proxy_service import proxy_fingerprint
    from app.services.youtube_client import YouTubeClient

    alive = {"ok": True}

    async def _probe(host, port, timeout=3.0):
        return alive["ok"]

    async def _no_link(platform, credentials, *, proxy_url):
        return dict(credentials or {}), None, {}

    monkeypatch.setattr("app.services.custom.content_factory_proxy.probe_proxy_tcp", _probe)
    monkeypatch.setattr("app.services.custom.content_factory_service.check_platform_link", _no_link)

    now = datetime.utcnow()

    def add_proxy(host, *, dedicated=False):
        row = CustomProxy(
            custom_automation_id=custom_automation.id,
            scheme="socks5",
            host=host,
            port=1080,
            fingerprint=proxy_fingerprint("socks5", host, 1080, None),
            is_dedicated=dedicated,
            is_active=True,
            is_healthy=True,
            created_at=now,
            updated_at=now,
        )
        test_session.add(row)
        return row

    set_a = add_proxy("10.7.0.1")
    set_b = add_proxy("10.7.0.2")
    current = add_proxy("10.7.0.3")
    add_proxy("10.7.0.4", dedicated=True)
    free_e = add_proxy("10.7.0.5")
    free_f = add_proxy("10.7.0.6")
    free_g = add_proxy("10.7.0.7")
    await test_session.flush()

    social = SocialAccount(
        provider="telegram",
        phone_number="+79990001122",
        username="tg_proxy_holder",
        encrypted_session="session",
        created_at=now,
        updated_at=now,
    )
    test_session.add(social)
    await test_session.flush()
    pool = AccountPool(
        custom_automation_id=custom_automation.id,
        name="Ферма",
        created_at=now,
        updated_at=now,
    )
    test_session.add(pool)
    await test_session.flush()
    test_session.add(
        PoolAccount(
            custom_automation_id=custom_automation.id,
            account_pool_id=pool.id,
            social_account_id=social.id,
            proxy_id=current.id,
            proxy_set_ids=[set_a.id, set_b.id],
            roles=[],
            added_at=now,
        )
    )
    await test_session.flush()

    first = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="instagram",
        display_name="Первый",
        handle="@one",
        external_id="1789001",
        credentials={"access_token": "tok-1", "ig_user_id": "1789001"},
    )
    second = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="tiktok",
        display_name="Второй",
        handle="@two",
        external_id="tt-2",
        credentials={"access_token": "tok-2", "refresh_token": "refresh.from.tiktok"},
    )
    await test_session.flush()

    occupied = {set_a.id, set_b.id, current.id}
    assert first.proxy_id != second.proxy_id
    assert first.proxy_id in {free_e.id, free_f.id}
    assert second.proxy_id in {free_e.id, free_f.id}
    assert first.proxy_id not in occupied
    assert second.proxy_id not in occupied
    assert first.proxy_problem is False
    assert decrypt_json(second.credentials_enc)["refresh_token"] == "refresh.from.tiktok"

    owned = first.proxy_id
    alive["ok"] = False
    assert await proxy_url_for_account(test_session, first) == ""
    assert first.proxy_id == owned
    assert first.proxy_problem is True
    assert second.proxy_id != owned

    opened = []

    class _BlockedClient:
        def __init__(self, *args, **kwargs):
            opened.append(kwargs)

    monkeypatch.setattr("app.services.custom.content_factory_publishers.httpx.AsyncClient", _BlockedClient)
    with pytest.raises(PublisherError, match="Нет прокси"):
        await publish_to_platform(
            platform="instagram",
            credentials={"access_token": "tok-1", "ig_user_id": "1789001"},
            video_url="https://cdn.example/clip.mp4",
            title="Клип",
            caption="Текст",
            sandbox=False,
            video_id=1,
            account_id=first.id,
            proxy_url=None,
        )
    assert opened == []

    alive["ok"] = True
    own_url = await proxy_url_for_account(test_session, first)
    other_url = httpx_proxy_url(await test_session.get(CustomProxy, second.proxy_id))
    assert own_url
    assert own_url != other_url
    assert first.proxy_id == owned

    class _Response:
        status_code = 200
        is_success = True
        text = '{"id":"container-1"}'
        content = b'{"id":"container-1"}'

        def json(self):
            return {"id": "container-1"}

    class _ProxyClient:
        def __init__(self, *args, **kwargs):
            opened.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data=None, **kwargs):
            return _Response()

    monkeypatch.setattr("app.services.custom.content_factory_publishers.httpx.AsyncClient", _ProxyClient)
    posted = await publish_to_platform(
        platform="instagram",
        credentials={"access_token": "tok-1", "ig_user_id": "1789001"},
        video_url="https://cdn.example/clip.mp4",
        title="Клип",
        caption="Текст",
        sandbox=False,
        video_id=1,
        account_id=first.id,
        proxy_url=own_url,
    )
    assert posted["status"] == "processing"
    assert opened[0]["proxy"] == own_url
    assert opened[0]["trust_env"] is False
    assert first.status == "warming"

    calls = []

    class _TokenResponse:
        status_code = 200
        is_success = True
        text = "{}"
        content = b"{}"

        def json(self):
            return {"access_token": "ya29.refreshed", "expires_in": 3600, "token_type": "Bearer"}

    class _TokenClient:
        def __init__(self, *args, **kwargs):
            calls.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, method, url, **kwargs):
            return _TokenResponse()

    monkeypatch.setattr("app.services.youtube_client.httpx.AsyncClient", _TokenClient)
    client = YouTubeClient(client_id="client-id", client_secret="client-secret", redirect_uri="https://app.example/callback")
    bundle = await client.ensure_fresh_access_token(
        token_bundle={
            "access_token": "expired",
            "refresh_token": "refresh.from.platform",
            "expires_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
        },
        proxy=own_url,
    )
    assert calls[0]["proxy"] == own_url
    assert calls[0]["trust_env"] is False
    assert bundle["access_token"] == "ya29.refreshed"
    assert bundle["refresh_token"] == "refresh.from.platform"

    kept = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="tiktok",
        display_name="Второй",
        handle="@two",
        external_id="tt-2",
        credentials={"access_token": "tok-2-new"},
    )
    saved = decrypt_json(kept.credentials_enc)
    assert saved["refresh_token"] == "refresh.from.tiktok"
    assert saved["access_token"] == "tok-2-new"
    assert kept.proxy_id == second.proxy_id
    assert kept.status != "restricted"

    youtube = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="youtube",
        display_name="Канал",
        handle="@yt",
        external_id="yt-9",
        credentials={"access_token": "ya-old", "refresh_token": "refresh.from.platform"},
    )
    assert youtube.proxy_id == free_g.id
    assert decrypt_json(youtube.credentials_enc)["refresh_token"] == "refresh.from.platform"
    assert await handshake_proxy(test_session, custom_automation.id) is None
    own = await handshake_proxy(test_session, custom_automation.id, account_id=youtube.id)
    assert own is not None
    assert own.id == youtube.proxy_id
    alive["ok"] = False
    assert await handshake_proxy(test_session, custom_automation.id, account_id=youtube.id) is None
    assert youtube.proxy_id == free_g.id


@pytest.mark.asyncio
async def test_second_youtube_login_does_not_take_existing_proxy(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from datetime import datetime

    from sqlalchemy import func, select

    from app.alembic.models import CustomContentFactoryAccount, CustomProxy
    from app.services.custom.content_factory_proxy import handshake_proxy
    from app.services.custom.content_factory_service import connect_account
    from app.services.custom.proxy_service import proxy_fingerprint

    alive = {"ok": True}

    async def _probe(host, port, timeout=3.0):
        return alive["ok"]

    async def _no_link(platform, credentials, *, proxy_url):
        return dict(credentials or {}), None, {}

    monkeypatch.setattr("app.services.custom.content_factory_proxy.probe_proxy_tcp", _probe)
    monkeypatch.setattr("app.services.custom.content_factory_service.check_platform_link", _no_link)

    now = datetime.utcnow()

    def add_proxy(host):
        row = CustomProxy(
            custom_automation_id=custom_automation.id,
            scheme="socks5",
            host=host,
            port=1080,
            fingerprint=proxy_fingerprint("socks5", host, 1080, None),
            is_dedicated=False,
            is_active=True,
            is_healthy=True,
            created_at=now,
            updated_at=now,
        )
        test_session.add(row)
        return row

    owned = add_proxy("10.8.0.1")
    await test_session.flush()
    first = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="youtube",
        display_name="Первый канал",
        handle="@yt-1",
        external_id="yt-1",
        credentials={"access_token": "ya-1", "refresh_token": "refresh-1"},
    )
    assert first.proxy_id == owned.id

    assert await handshake_proxy(test_session, custom_automation.id) is None
    youtube_count = await test_session.scalar(
        select(func.count()).select_from(CustomContentFactoryAccount).where(
            CustomContentFactoryAccount.custom_automation_id == custom_automation.id,
            CustomContentFactoryAccount.platform == "youtube",
        )
    )
    assert youtube_count == 1
    repeat = await handshake_proxy(test_session, custom_automation.id, account_id=first.id)
    assert repeat is not None
    assert repeat.id == first.proxy_id

    free = add_proxy("10.8.0.2")
    await test_session.flush()
    fresh = await handshake_proxy(test_session, custom_automation.id)
    assert fresh is not None
    assert fresh.id == free.id
    assert fresh.id != first.proxy_id
    second = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="youtube",
        display_name="Второй канал",
        handle="@yt-2",
        external_id="yt-2",
        credentials={"access_token": "ya-2", "refresh_token": "refresh-2"},
        preferred_proxy_id=fresh.id,
    )
    assert second.id != first.id
    assert second.proxy_id == fresh.id
    assert second.proxy_id != first.proxy_id

    again = await handshake_proxy(test_session, custom_automation.id, account_id=first.id)
    assert again is not None
    assert again.id == first.proxy_id
    assert await handshake_proxy(test_session, custom_automation.id) is None
    owned_id = first.proxy_id
    alive["ok"] = False
    assert await handshake_proxy(test_session, custom_automation.id, account_id=first.id) is None
    assert first.proxy_id == owned_id
    assert second.proxy_id == free.id


@pytest.mark.asyncio
async def test_instagram_refresh_stays_on_account_proxy(monkeypatch):
    from app.services.custom.content_factory_publishers import _rotate_instagram, _use_proxy

    seen = []

    class _Response:
        status_code = 200
        is_success = True
        content = b"{}"

        def json(self):
            return {"access_token": "ig-long", "expires_in": 5184000}

    class _Client:
        def __init__(self, *args, **kwargs):
            seen.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None, **kwargs):
            seen.append({"url": url})
            return _Response()

    monkeypatch.setattr("app.services.custom.content_factory_publishers.httpx.AsyncClient", _Client)
    token = _use_proxy("socks5://10.7.0.8:1080")
    try:
        updated = await _rotate_instagram({"access_token": "ig-short", "ig_user_id": "1789"}, force=True)
    finally:
        from app.services.custom.content_factory_publishers import _proxy_url

        _proxy_url.reset(token)
    assert updated["access_token"] == "ig-long"
    assert updated["expires_at"]
    assert updated["token_type"] == "ig_refresh"
    assert seen[0]["proxy"] == "socks5://10.7.0.8:1080"
    assert seen[0]["trust_env"] is False


def test_login_methods_follow_what_each_platform_accepts():
    from datetime import datetime, timedelta

    from app.services.custom.content_factory_antifraud import (
        credential_status,
        now_utc,
        present_health_score,
        validate_platform_credentials,
        youtube_refresh_badge_ok,
    )

    youtube = validate_platform_credentials("youtube", {"refresh_token": "refresh-yt"})
    assert youtube["refresh_token"] == "refresh-yt"
    access_only = validate_platform_credentials("youtube", {"access_token": "ya-live"})
    assert access_only["access_token"] == "ya-live"
    instagram = validate_platform_credentials(
        "instagram",
        {"access_token": "ig-live", "ig_user_id": "1789"},
    )
    assert instagram["ig_user_id"] == "1789"
    tiktok = validate_platform_credentials(
        "tiktok",
        {"access_token": "tt-live", "refresh_token": "tt-refresh"},
    )
    assert tiktok["refresh_token"] == "tt-refresh"
    pinterest = validate_platform_credentials(
        "pinterest",
        {"access_token": "pin-live", "board_id": "board-1"},
    )
    assert pinterest["board_id"] == "board-1"
    vk = validate_platform_credentials("vk", {"access_token": "vk-live", "group_id": "club42"})
    assert vk["group_id"] == "42"
    with pytest.raises(ValueError, match="cookie"):
        validate_platform_credentials("tiktok", {"access_token": "tt", "sessionid": "browser-session"})
    with pytest.raises(ValueError, match="Пароль"):
        validate_platform_credentials("instagram", {"access_token": "ig", "ig_user_id": "1", "password": "secret"})

    past = (now_utc() - timedelta(hours=2)).isoformat()
    dead = credential_status("tiktok", {"access_token": "tt", "refresh_token": "saved", "expires_at": past})
    assert dead["credential_mode"] == "expired"
    assert present_health_score(90, credential_mode=dead["credential_mode"], proxy_ok=True) <= 49
    stale_refresh = {"access_token": "ya", "refresh_token": "refresh-yt", "expires_at": past}
    living = credential_status("youtube", stale_refresh)
    assert living["credential_mode"] == "refresh"
    assert youtube_refresh_badge_ok(stale_refresh, last_error=None) is True
    assert youtube_refresh_badge_ok(
        stale_refresh,
        last_error="YouTube не подтвердил канал через прокси аккаунта.",
    ) is False
    future = (datetime.utcnow() + timedelta(days=20)).isoformat()
    renewable = credential_status("instagram", {"access_token": "ig", "ig_user_id": "1789", "expires_at": future})
    assert renewable["credential_mode"] == "renewable"


async def test_grok_script_uses_the_factory_bot_not_a_side_llm(monkeypatch):
    from types import SimpleNamespace

    from app.services.custom.content_factory_pipeline import _generate_pack

    calls = {"bot": 0, "llm": 0}

    async def fake_author(**kwargs):
        calls["bot"] += 1
        assert kwargs["previous_response_id"] == "resp-old"
        assert "JSON" in kwargs["message"]
        return {
            "text": (
                '{"idea":"очередь","hook":"Стоп. Очередь","script":"текст","caption":"подпись",'
                '"hashtags":["кофе"],"storyboard":[{"visual":"кадр 1","voiceover":"раз"},'
                '{"visual":"кадр 2","voiceover":"два"}],"content_format":"ugc","visual_style":"realism"}'
            ),
            "response_id": "resp-new",
        }

    async def fake_llm(*_args, **_kwargs):
        calls["llm"] += 1
        return None

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.generate_grok_authoring", fake_author)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline._llm_json", fake_llm)
    monkeypatch.setattr(
        "app.services.custom.content_factory_pipeline.decrypted_secret",
        lambda _row, field: "xai-test" if field == "xai_api_key" else "",
    )
    settings = SimpleNamespace(
        product_name="Кофейня",
        product_description="кофе",
        audience="гости",
        niche="кофе",
        language="ru",
        tone="expert_friendly",
        brand_voice="",
        forbidden_topics="",
        cta_text="",
        product_url="",
        script_model="grok-4.7",
        idea_model="grok-4.7",
        grok_bot_response_id="resp-old",
        xai_api_key_enc="enc",
        image_provider="chatgpt",
        duration_min=30,
        hook_required=False,
        updated_at=None,
    )
    video = SimpleNamespace(
        id=1,
        content_format="ugc",
        visual_style="realism",
        duration_seconds=30,
        aspect_ratio="9:16",
        extra={"media_kind": "video"},
    )
    pack = await _generate_pack(settings, video, [])
    assert calls["bot"] == 1
    assert calls["llm"] == 0
    assert settings.grok_bot_response_id == "resp-new"
    assert pack["storyboard"][0]["visual"] == "кадр 1"
    assert pack["usage"]["provider"] == "grok"

    async def broken_author(**_kwargs):
        calls["bot"] += 1
        return {"text": "это не сценарий", "response_id": "resp-bad"}

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.generate_grok_authoring", broken_author)
    with pytest.raises(RuntimeError, match="разборный сценарий"):
        await _generate_pack(settings, video, [])
    assert calls["llm"] == 0

    async def dead_author(**_kwargs):
        calls["bot"] += 1
        raise RuntimeError("Grok Bot: HTTP 500")

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.generate_grok_authoring", dead_author)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await _generate_pack(settings, video, [])
    assert calls["llm"] == 0

    settings.script_model = "deepseek-chat"
    settings.image_provider = "grok"
    bot_before = calls["bot"]

    async def quiet_llm(*_args, **_kwargs):
        calls["llm"] += 1
        return None

    monkeypatch.setattr("app.services.custom.content_factory_pipeline._llm_json", quiet_llm)
    other = await _generate_pack(settings, video, [])
    assert calls["bot"] == bot_before
    assert calls["llm"] == 1
    assert "продаёте" in other["hook"] or "рутину" in other["hook"]


async def test_carousel_frames_come_from_the_same_grok_bot(tmp_path, monkeypatch):
    from app.services.custom.content_factory_media import generate_grok_carousel_pack

    calls = []

    async def fake_ask(**kwargs):
        calls.append(kwargs)
        images = [
            {"bytes": b"\x89PNG\r\n\x1a\n" + bytes([index + 1]), "prompt": f"кадр {index + 1}"}
            for index in range(4)
        ]
        return {"images": images, "text": "Тема", "response_id": "resp-c"}

    monkeypatch.setattr("app.services.custom.content_factory_media.ask_grok_bot", fake_ask)
    pack = await generate_grok_carousel_pack(
        api_key="xai-test",
        company="Кофейня",
        description="кофе",
        audience="",
        niche="",
        brief="",
        avoid=[],
        previous_response_id="resp-prev",
        folder=tmp_path,
    )
    assert calls[0]["previous_response_id"] == "resp-prev"
    assert calls[0]["tools"]
    assert pack["response_id"] == "resp-c"
    assert [path.name for path in pack["paths"]] == ["slide-00.png", "slide-01.png", "slide-02.png", "slide-03.png"]


@pytest.mark.asyncio
async def test_manual_carousel_keeps_card_order_and_skips_platform_without_proxy(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from sqlalchemy import select

    from app.alembic.models import CustomContentFactoryPost
    from app.services.custom.content_factory_pipeline import publish_own_material
    from app.services.custom.content_factory_service import connect_account, get_or_create_settings

    calls = []

    async def fake_publish(**kwargs):
        calls.append(list(kwargs.get("image_urls") or []))
        return {"status": "posted", "external_id": "manual-1", "posted_url": "https://example.test/p"}

    def no_show(*_args, **_kwargs):
        raise RuntimeError("ffmpeg skipped")

    async def no_link(*_args, **_kwargs):
        return {}, None, {}

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.publish_to_platform", fake_publish)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.slides_to_mp4", no_show)
    monkeypatch.setattr("app.services.custom.content_factory_service.check_platform_link", no_link)

    settings = await get_or_create_settings(test_session, custom_automation.id)
    settings.sandbox_mode = False
    account = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="instagram",
        display_name="Свой",
        handle="@own",
        external_id="1789009",
        credentials={"access_token": "tok-own", "ig_user_id": "1789009"},
    )
    from app.services.custom.content_factory_antifraud import now_utc

    account.warmup_started_at = now_utc()
    account.warmup_completed_at = now_utc()
    account.status = "ready"
    held = await publish_own_material(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        title="Заголовок",
        caption="Описание своего поста",
        media_kind="carousel",
        files=[
            ("a.png", b"\x89PNG\r\n\x1a\nA"),
            ("b.png", b"\x89PNG\r\n\x1a\nB"),
            ("c.png", b"\x89PNG\r\n\x1a\nC"),
        ],
    )
    assert calls == []
    assert (held.extra or {}).get("slide_names") == ["slide-00.png", "slide-01.png", "slide-02.png"]
    post = await test_session.scalar(
        select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == held.id)
    )
    assert post is not None
    assert post.status == "held"
    assert post.hold_reason == "Нет прокси"
    assert account.status != "restricted"

    async def own_proxy(_session, _account):
        return "socks5://10.9.0.8:1080"

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.proxy_url_for_account", own_proxy)
    posted = await publish_own_material(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        title="Заголовок",
        caption="Описание своего поста",
        media_kind="carousel",
        files=[
            ("first.png", b"\x89PNG\r\n\x1a\n1"),
            ("second.png", b"\x89PNG\r\n\x1a\n2"),
            ("third.png", b"\x89PNG\r\n\x1a\n3"),
        ],
    )
    assert len(calls) == 1
    assert [item.rsplit("/", 1)[-1] for item in calls[0]] == ["slide-00.png", "slide-01.png", "slide-02.png"]
    assert (posted.extra or {}).get("slide_names") == ["slide-00.png", "slide-01.png", "slide-02.png"]
    assert posted.status == "posted"


async def test_account_update_does_not_store_password_or_cookie(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from app.services.custom.content_factory_service import connect_account, decrypt_json, update_account

    async def no_link(*_args, **_kwargs):
        return {}, None, {}

    monkeypatch.setattr("app.services.custom.content_factory_service.check_platform_link", no_link)
    account = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="instagram",
        display_name="Лента",
        handle="@feed",
        external_id="1789011",
        credentials={"access_token": "tok-old", "ig_user_id": "1789011"},
    )
    updated = await update_account(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        payload={
            "credentials": {
                "access_token": "tok-next",
                "password": "secret-pass",
                "cookie": "browser-cookie",
                "cookies": "browser-jar",
                "sessionid": "browser-session",
            }
        },
    )
    stored = decrypt_json(updated.credentials_enc)
    assert stored["access_token"] == "tok-next"
    assert stored["ig_user_id"] == "1789011"
    for key in ("password", "cookie", "cookies", "sessionid"):
        assert key not in stored
    assert "secret-pass" not in stored.values()
    assert "browser-cookie" not in stored.values()

    untouched = await update_account(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        payload={"credentials": {"password": "again", "cookie": "again"}},
    )
    kept = decrypt_json(untouched.credentials_enc)
    assert kept["access_token"] == "tok-next"
    assert "password" not in kept
    assert "cookie" not in kept


async def test_manual_retry_outside_window_reaches_publisher_without_skipping_daily_cap(
    test_session: AsyncSession,
    custom_automation: CustomAutomation,
    monkeypatch,
):
    from datetime import timedelta

    from sqlalchemy import select

    from app.alembic.models import CustomContentFactoryPost
    from app.services.custom.content_factory_antifraud import now_utc
    from app.services.custom.content_factory_pipeline import _process_next_video, publish_own_material
    from app.services.custom.content_factory_service import connect_account, get_or_create_settings

    calls = []

    async def fake_publish(**_kwargs):
        calls.append(True)
        return {"status": "posted", "external_id": "manual-tick", "posted_url": "https://example.test/p"}

    def no_show(*_args, **_kwargs):
        raise RuntimeError("ffmpeg skipped")

    async def no_link(*_args, **_kwargs):
        return {}, None, {}

    def window_closed(*_args, **_kwargs):
        return False

    proxy_box = {"url": ""}

    async def own_proxy(_session, _account):
        return proxy_box["url"]

    monkeypatch.setattr("app.services.custom.content_factory_pipeline.publish_to_platform", fake_publish)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.slides_to_mp4", no_show)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.in_posting_window", window_closed)
    monkeypatch.setattr("app.services.custom.content_factory_pipeline.proxy_url_for_account", own_proxy)
    monkeypatch.setattr("app.services.custom.content_factory_service.check_platform_link", no_link)

    settings = await get_or_create_settings(test_session, custom_automation.id)
    settings.sandbox_mode = False
    settings.max_posts_per_account_per_day = 2
    account = await connect_account(
        test_session,
        automation_id=custom_automation.id,
        platform="instagram",
        display_name="Свой",
        handle="@own2",
        external_id="1789012",
        credentials={"access_token": "tok-own", "ig_user_id": "1789012"},
    )
    account.warmup_started_at = now_utc()
    account.warmup_completed_at = now_utc()
    account.status = "ready"
    account.extra = {"apply_post_ramp": True}

    slides = [
        ("a.png", b"\x89PNG\r\n\x1a\nA"),
        ("b.png", b"\x89PNG\r\n\x1a\nB"),
    ]
    held = await publish_own_material(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        title="Снаружи окна",
        caption="Свой пост",
        media_kind="carousel",
        files=slides,
    )
    assert calls == []
    assert held.status == "ready"
    assert (held.extra or {}).get("hold_reason") != "Вне окна публикаций"
    first_post = await test_session.scalar(
        select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == held.id)
    )
    assert first_post.hold_reason == "Нет прокси"

    proxy_box["url"] = "socks5://10.9.0.9:1080"
    retried = await _process_next_video(test_session, custom_automation.id, settings)
    assert retried is not None
    assert retried.id == held.id
    assert len(calls) == 1
    assert retried.status == "posted"
    assert int(account.posts_today or 0) == 1

    account.last_posted_at = now_utc() - timedelta(hours=3)
    again = await publish_own_material(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        title="Рамп не режет свой материал",
        caption="Второй свой пост",
        media_kind="carousel",
        files=slides,
    )
    assert len(calls) == 2
    assert again.status == "posted"

    account.last_posted_at = now_utc() - timedelta(hours=3)
    capped = await publish_own_material(
        test_session,
        automation_id=custom_automation.id,
        account_id=account.id,
        title="Потолок",
        caption="Третий свой пост",
        media_kind="carousel",
        files=slides,
    )
    assert len(calls) == 2
    capped_post = await test_session.scalar(
        select(CustomContentFactoryPost).where(CustomContentFactoryPost.video_id == capped.id)
    )
    assert capped_post.hold_reason == "Дневной лимит постов исчерпан"
    ticked = await _process_next_video(test_session, custom_automation.id, settings)
    assert ticked is not None
    assert ticked.id == capped.id
    assert len(calls) == 2
    assert capped_post.hold_reason == "Дневной лимит постов исчерпан"


async def test_instagram_carousel_published_container_is_not_published_again(monkeypatch):
    from app.services.custom.content_factory_publishers import _proxy_url, _publish_instagram_carousel, _use_proxy

    posts = []

    class _Response:
        def __init__(self, payload):
            self._payload = payload
            self.is_success = True
            self.status_code = 200
            self.text = ""

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None, **kwargs):
            return _Response({"status_code": "PUBLISHED"})

        async def post(self, url, data=None, **kwargs):
            posts.append(str(url))
            return _Response({"id": "should-not-publish"})

    monkeypatch.setattr("app.services.custom.content_factory_publishers.httpx.AsyncClient", _Client)
    token = _use_proxy("socks5://10.8.0.8:1080")
    try:
        result = await _publish_instagram_carousel(
            credentials={"access_token": "ig", "ig_user_id": "1789"},
            image_urls=["https://example.test/a.jpg", "https://example.test/b.jpg"],
            caption="Карусель",
            publisher_state={"ig_container_id": "container-already"},
        )
    finally:
        _proxy_url.reset(token)
    assert result["status"] == "posted"
    assert result["external_id"] == "container-already"
    assert posts == []
    assert not any("media_publish" in url for url in posts)

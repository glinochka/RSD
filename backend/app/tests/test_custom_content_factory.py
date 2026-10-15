"""Custom AI content factory: settings, accounts, pipeline, anti-fraud."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import CustomAdmin, CustomAutomation, CustomAutomationCredential
from app.services.custom.content_factory_antifraud import (
    caption_variant,
    factory_return_url,
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
    assert factory_return_url("https://evil.test/phish", 9, base_url="https://app.test") == "https://app.test/custom/automations/9/content-factory/accounts"
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

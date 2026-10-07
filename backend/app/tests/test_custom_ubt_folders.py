"""Task folders, parser user folders, and per-account session streams."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import (
    ChatFolder,
    ChatTarget,
    CustomAdmin,
    CustomAutomation,
    CustomAutomationCredential,
    ParserUser,
    UserFolder,
)
from app.utils.security import get_password_hash


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="ubt_folder_admin",
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
        name="UBT Folders",
        client_name="Folder Client",
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
async def custom_credential(test_session: AsyncSession, custom_automation: CustomAutomation) -> CustomAutomationCredential:
    credential = CustomAutomationCredential(
        custom_automation_id=custom_automation.id,
        username="ubt_folder_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    await test_session.refresh(credential)
    return credential


@pytest.fixture
async def client_token(client: AsyncClient, custom_credential: CustomAutomationCredential) -> str:
    response = await client.post("/api/custom/login", json={
        "username": "ubt_folder_client",
        "password": "password",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestTaskChatFolders:
    async def test_resolve_folder_ids_into_chat_pool(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.custom.task_targets import resolve_task_chat_ids

        folder = ChatFolder(custom_automation_id=custom_automation.id, name="seo_base", created_at=_now(), updated_at=_now())
        test_session.add(folder)
        await test_session.flush()
        chat = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="SEO Chat",
            invite_link="https://t.me/seo_chat",
            folder_id=folder.id,
            is_active=True,
        )
        outsider = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="Other",
            invite_link="https://t.me/other",
            is_active=True,
        )
        test_session.add_all([chat, outsider])
        await test_session.commit()

        ids = await resolve_task_chat_ids(test_session, custom_automation.id, {"folder_ids": [folder.id]})
        assert chat.id in ids
        assert outsider.id not in ids

    async def test_chats_api_lists_folders_then_folder_contents(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        folder = ChatFolder(
            custom_automation_id=custom_automation.id, name="seo_excel", created_at=_now(), updated_at=_now()
        )
        test_session.add(folder)
        await test_session.flush()
        inside = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="Inside",
            invite_link="https://t.me/inside_folder",
            folder_id=folder.id,
            is_active=True,
        )
        orphan = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="Orphan",
            invite_link="https://t.me/orphan_chat",
            is_active=True,
        )
        test_session.add_all([inside, orphan])
        await test_session.commit()
        await test_session.refresh(folder)
        await test_session.refresh(inside)

        headers = {"Authorization": f"Bearer {client_token}"}
        folders = await client.get(
            f"/api/custom/automations/{custom_automation.id}/chats/folders",
            headers=headers,
        )
        assert folders.status_code == 200, folders.text
        names = [item["name"] for item in folders.json()["items"]]
        assert "seo_excel" in names
        scoped = await client.get(
            f"/api/custom/automations/{custom_automation.id}/chats",
            headers=headers,
            params={"folder_id": folder.id},
        )
        assert scoped.status_code == 200, scoped.text
        items = scoped.json()["items"]
        assert [item["id"] for item in items] == [inside.id]
        assert all(item["folder_id"] == folder.id for item in items)

    async def test_broadcast_empty_folder_does_not_scan_all(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_broadcast_service import _target_chats

        folder = ChatFolder(
            custom_automation_id=custom_automation.id, name="empty_pool", created_at=_now(), updated_at=_now()
        )
        outsider = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="Group",
            invite_link="https://t.me/group_all",
            chat_type="megagroup",
            is_active=True,
        )
        test_session.add_all([folder, outsider])
        await test_session.commit()
        await test_session.refresh(folder)
        chats = await _target_chats(
            test_session,
            custom_automation.id,
            {"folder_ids": [folder.id], "only_joined": False},
            accounts=[],
        )
        assert chats == []

    async def test_neurocommenting_saves_folder_ids(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        folder = ChatFolder(custom_automation_id=custom_automation.id, name="nc_pool", created_at=_now(), updated_at=_now())
        test_session.add(folder)
        await test_session.commit()
        await test_session.refresh(folder)

        saved = await client.put(
            f"/api/custom/automations/{custom_automation.id}/modules/neurocommenting",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"enabled": True, "account_ids": [], "folder_ids": [folder.id], "chat_ids": []},
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert folder.id in body["settings"]["folder_ids"]
        assert any(item["id"] == folder.id for item in body["folders"])
        assert "Каналы не указаны" not in body["issues"]


class TestParserUserFolders:
    async def test_snapshot_creates_folder_for_dm_and_masspriming(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client: AsyncClient,
        client_token: str,
    ):
        from app.services.custom.user_folder_service import snapshot_parser_users

        test_session.add(
            ParserUser(
                custom_automation_id=custom_automation.id,
                telegram_user_id=777001,
                username="lead_one",
                first_name="Lead",
                source_mode="messages",
                source_chat_id="-1001",
            )
        )
        await test_session.commit()
        folder = await snapshot_parser_users(test_session, custom_automation.id, name="Парсинг тест")
        await test_session.commit()
        assert folder is not None
        stored = await test_session.get(UserFolder, folder.id)
        assert stored is not None
        assert stored.source == "parser"
        assert stored.name.startswith("Парсинг")

        dm = await client.put(
            f"/api/custom/automations/{custom_automation.id}/modules/dm-broadcasts",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"enabled": True, "account_ids": [], "recipients": [], "user_folder_ids": [folder.id], "messages": [{"text": "hi"}]},
        )
        assert dm.status_code == 200, dm.text
        assert folder.id in dm.json()["settings"]["user_folder_ids"]
        assert any(item["id"] == folder.id for item in dm.json()["user_folders"])

        priming = await client.put(
            f"/api/custom/automations/{custom_automation.id}/modules/masspriming",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"enabled": True, "account_ids": [], "targets": [], "user_folder_ids": [folder.id]},
        )
        assert priming.status_code == 200, priming.text
        assert folder.id in priming.json()["settings"]["user_folder_ids"]

    async def test_resolve_user_folder_peers_usernames_only(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.custom.task_targets import resolve_user_folder_peers
        from app.services.custom.user_folder_service import snapshot_parser_users

        test_session.add_all([
            ParserUser(
                custom_automation_id=custom_automation.id,
                telegram_user_id=1,
                username="with_nick",
                source_mode="messages",
                source_chat_id="a",
            ),
            ParserUser(
                custom_automation_id=custom_automation.id,
                telegram_user_id=2,
                username=None,
                source_mode="messages",
                source_chat_id="b",
            ),
        ])
        await test_session.commit()
        folder = await snapshot_parser_users(test_session, custom_automation.id)
        await test_session.commit()
        named = await resolve_user_folder_peers(
            test_session, custom_automation.id, {"user_folder_ids": [folder.id]}, usernames_only=True
        )
        all_peers = await resolve_user_folder_peers(
            test_session, custom_automation.id, {"user_folder_ids": [folder.id]}
        )
        assert named == ["@with_nick"]
        assert "@with_nick" in all_peers
        assert "2" in all_peers


class TestAccountSessionStreams:
    async def test_enabled_streams_keep_tasks_inside_one_session(self, custom_automation: CustomAutomation):
        from app.services.custom.account_session_orchestrator import _enabled_streams

        custom_automation.account_warmup_enabled = True
        custom_automation.module_settings = {
            "neurocommenting": {"enabled": True},
            "neurochatting": {"enabled": True},
            "chat_broadcasts": {"enabled": True},
            "dm_broadcasts": {"enabled": True},
            "warmup": {"mode": "auto"},
        }
        names = [name for name, _fn in _enabled_streams(custom_automation)]
        assert names[0] == "join"
        assert "neurocommenting" in names
        assert "neurochatting" in names
        assert "chat_broadcast" in names
        assert "dm_broadcast" in names
        assert "peer_dialog" in names
        assert "idle_browse" in names
        assert "parser" not in names
        assert names.count("peer_dialog") == 1
        assert names.count("idle_browse") == 1
        from app.services.custom.account_session_orchestrator import _work_streams

        work = [name for name, _fn in _work_streams(custom_automation)]
        assert "join" not in work
        assert "neurocommenting" in work
        assert work[0] != "join"


class TestJoinScenarioBranches:
    def test_folder_only_and_warmup_column_join_only_joined_skips(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import collect_task_join_specs
        from app.services.custom.task_targets import has_chat_pool

        assert has_chat_pool({"channel_ids": [8]})
        assert not has_chat_pool({"chat_ids": [], "folder_ids": []})

        auto = SimpleNamespace(
            is_neurocommenting_enabled=True,
            is_shilling_enabled=False,
            is_digital_footprint_enabled=True,
            account_warmup_enabled=True,
            module_settings={
                "neurocommenting": {"folder_ids": [3], "chat_ids": [], "account_ids": [11]},
                "warmup": {"folder_ids": [3], "account_ids": [], "do_joins": True},
                "neurochatting": {
                    "enabled": True,
                    "only_joined": True,
                    "folder_ids": [3],
                    "account_ids": [11],
                    "chat_ids": [],
                },
                "chat_broadcasts": {
                    "enabled": True,
                    "only_joined": True,
                    "folder_ids": [3],
                    "account_ids": [11],
                    "chat_ids": [4],
                },
            },
        )
        keys = {spec["task_key"] for spec in collect_task_join_specs(auto)}
        assert "neurocommenting" in keys
        assert "warmup" in keys
        assert "neurochatting" not in keys
        assert "chat_broadcasts" not in keys
        warmup = next(spec for spec in collect_task_join_specs(auto) if spec["task_key"] == "warmup")
        assert warmup["account_ids"] == []

    async def test_snapshot_unique_names(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.custom.user_folder_service import snapshot_parser_users

        test_session.add(
            ParserUser(
                custom_automation_id=custom_automation.id,
                telegram_user_id=9001,
                username="uniq",
                source_mode="messages",
                source_chat_id="-1",
            )
        )
        await test_session.commit()
        first = await snapshot_parser_users(test_session, custom_automation.id, name="Парсинг дубль")
        second = await snapshot_parser_users(test_session, custom_automation.id, name="Парсинг дубль")
        await test_session.commit()
        assert first is not None and second is not None
        assert first.name != second.name

    async def test_discovery_logs_completed_counts_found_chats(self):
        from datetime import datetime
        from types import SimpleNamespace

        from app.services.custom.job_service import _discovery_logs, serialize_discovery

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        task = SimpleNamespace(
            id=7,
            query="SEO",
            status="completed",
            created_at=now,
            updated_at=now,
            completed_at=now,
            found_chats=[{"title": "A"}, {"title": "B"}, "skip"],
            max_chats=10,
            relevance_threshold=0.5,
            require_approval=False,
            mode="monitoring",
            joined_chats=0,
            rejected_chats=0,
        )
        logs = _discovery_logs(task)
        assert any(row["message"] == "Завершено: 2 чатов" for row in logs)
        payload = serialize_discovery(task)
        assert payload["result"]["Всего каналов"] == 2


class TestJobLifecycle:
    def test_persistent_vs_finite(self):
        from app.services.custom.job_service import is_persistent_job

        assert is_persistent_job("neurocommenting") is True
        assert is_persistent_job("discussion") is True
        assert is_persistent_job("shilling") is True
        assert is_persistent_job("chat_broadcast", {"scenario": "loop"}) is True
        assert is_persistent_job("chat_broadcast", {"scenario": "once"}) is False
        assert is_persistent_job("chat_broadcast", {"skip_sent": True}) is False
        assert is_persistent_job("parser") is False
        assert is_persistent_job("masspriming") is False
        assert is_persistent_job("dm_broadcast") is False
        assert is_persistent_job("masslooking") is False

    def test_folder_splits_into_unique_account_pools(self):
        from app.services.custom.chat_addlist_service import _reusable_folders, even_redistribute

        assignment = even_redistribute([10, 20, 30], list(range(1, 10)))
        pooled = [cid for ids in assignment.values() for cid in ids]
        assert len(pooled) == len(set(pooled))
        assert set(pooled) == set(range(1, 10))
        sizes = [len(ids) for ids in assignment.values()]
        assert max(sizes) - min(sizes) <= 1
        reusable, covered = _reusable_folders(
            [{"slug": "poolA", "chat_ids": [1, 2, 3]}, {"slug": "other", "chat_ids": [1, 9]}],
            [1, 2, 3],
        )
        assert reusable == [{"slug": "poolA", "chat_ids": [1, 2, 3]}]
        assert covered == {1, 2, 3}

    def test_floodwait_parks_old_joiners(self):
        from datetime import datetime, timedelta, timezone
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import join_account_is_parked

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        idle = SimpleNamespace(next_action_at=now + timedelta(minutes=40), flood_quarantined_until=None)
        ready = SimpleNamespace(next_action_at=None, flood_quarantined_until=None)
        assert join_account_is_parked(idle, now=now) is True
        assert join_account_is_parked(ready, now=now) is False

    def test_flood_quarantine_is_global_12_to_24h(self):
        from datetime import datetime, timedelta, timezone
        from types import SimpleNamespace

        from app.services.custom.account_pacing import (
            account_is_flood_quarantined,
            account_should_idle,
            looks_like_flood_quarantine,
            schedule_flood_quarantine,
        )
        from app.services.custom.account_roles import account_is_live

        class TooMany(Exception):
            pass

        class FakeFlood(Exception):
            seconds = 90

            def __init__(self):
                super().__init__("A wait of 90 seconds is required")

        FakeFlood.__name__ = "FloodWaitError"
        assert looks_like_flood_quarantine(TooMany("Too many attempts, try later")) is True
        assert looks_like_flood_quarantine(FakeFlood()) is True
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        account = SimpleNamespace(
            id=7,
            is_active=True,
            is_banned=False,
            is_frozen=False,
            session_file_path="/tmp/x.session",
            encrypted_session="x",
            next_action_at=None,
            next_humanization_at=None,
            flood_quarantined_until=None,
            updated_at=now,
        )
        until = schedule_flood_quarantine(account, now=now)
        wait = (until - now).total_seconds()
        assert 12 * 3600 <= wait <= 24 * 3600
        assert account_is_flood_quarantined(account, now=now) is True
        assert account_should_idle(account, now=now, ignore_hours=True) is True
        assert account_is_live(account) is False
        account.flood_quarantined_until = now - timedelta(minutes=1)
        account.next_action_at = None
        account.next_humanization_at = None
        assert account_is_flood_quarantined(account, now=now) is False
        assert account_is_live(account) is True

    def test_addlist_slug_on_chat(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import chat_addlist_slug, set_chat_addlist_slug

        chat = SimpleNamespace(invite_link="https://t.me/channel", monitoring_config={})
        set_chat_addlist_slug(chat, "AbCdEfGhIj")
        assert chat_addlist_slug(chat) == "AbCdEfGhIj"
        assert "addlist/AbCdEfGhIj" in (chat.invite_link or "")

    def test_finite_complete_rules(self):
        from app.services.custom.job_service import _finite_should_complete

        assert _finite_should_complete({"status": "ok"}, "parser") is True
        assert _finite_should_complete({"status": "skipped", "reason": "night"}, "parser") is True
        assert _finite_should_complete({"status": "skipped", "reason": "night"}, "masspriming") is False
        assert _finite_should_complete({"status": "ok", "remaining": 4}, "dm_broadcast") is False
        assert _finite_should_complete({"status": "ok", "remaining": 0}, "dm_broadcast") is True

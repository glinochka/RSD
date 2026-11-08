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

        channel = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="SEO Channel",
            invite_link="https://t.me/seo_channel",
            folder_id=folder.id,
            chat_type="channel",
            is_active=True,
        )
        group = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="SEO Group",
            invite_link="https://t.me/seo_group",
            folder_id=folder.id,
            chat_type="chat",
            is_active=True,
        )
        test_session.add_all([channel, group])
        await test_session.commit()
        channels = await resolve_task_chat_ids(
            test_session,
            custom_automation.id,
            {"folder_ids": [folder.id]},
            task_key="neurocommenting",
        )
        chats_only = await resolve_task_chat_ids(
            test_session,
            custom_automation.id,
            {"folder_ids": [folder.id]},
            task_key="neurochatting",
        )
        assert channel.id in channels
        assert group.id not in channels
        assert group.id in chats_only
        assert channel.id not in chats_only

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

    def test_paused_jobs_stay_active_and_can_resume(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace

        from app.services.custom.job_service import (
            PAUSED_STATUS,
            _matches,
            serialize_custom,
        )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        running = SimpleNamespace(
            id=11,
            job_type="neurocommenting",
            title="Нейрокомментинг",
            status="running",
            params={"delay_before_min": 90, "presets": []},
            result={},
            logs=[],
            error=None,
            created_at=now,
            started_at=now,
            completed_at=None,
            updated_at=now,
        )
        live = serialize_custom(running)
        assert live["can_pause"] is True
        assert live["can_resume"] is False
        assert live["can_edit"] is True
        assert live["can_cancel"] is True
        assert "presets" not in live["params"]
        assert live["params"]["max_per_account"] == 15
        assert live["params"]["comment_delay_min"] == 20 * 60
        assert live["params"]["comment_delay_max"] == 40 * 60
        assert live["params"]["join_delay_min"] == 20 * 60
        assert live["params"]["join_delay_max"] == 40 * 60
        assert live["params"]["delay_before_min"] == 90

        running.status = PAUSED_STATUS
        paused = serialize_custom(running)
        assert paused["status"] == "paused"
        assert paused["can_pause"] is False
        assert paused["can_resume"] is True
        assert paused["can_edit"] is True
        assert paused["completed_at"] is None
        assert _matches(paused, bucket="active", category=None, search=None) is True
        assert _matches(paused, bucket="history", category=None, search=None) is False

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
        idle = SimpleNamespace(next_action_at=None, flood_quarantined_until=now + timedelta(hours=12))
        resting = SimpleNamespace(next_action_at=now + timedelta(minutes=40), flood_quarantined_until=None)
        ready = SimpleNamespace(next_action_at=None, flood_quarantined_until=None)
        assert join_account_is_parked(idle, now=now) is True
        assert join_account_is_parked(resting, now=now) is False
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

    def test_farm_sleeps_outside_configured_hours(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app.services.custom.work_mode import farm_work_overlap

        moscow = ZoneInfo("Europe/Moscow")
        mode = {"hour_start": 8, "hour_end": 20, "weekdays": [0, 1, 2, 3, 4]}
        assert farm_work_overlap(datetime(2026, 10, 9, 7, 20, tzinfo=moscow), mode=mode) is False
        assert farm_work_overlap(datetime(2026, 10, 9, 12, 0, tzinfo=moscow), mode=mode) is True
        assert farm_work_overlap(datetime(2026, 10, 9, 22, 0, tzinfo=moscow), mode=mode) is False
        saturday = datetime(2026, 10, 10, 12, 0, tzinfo=moscow)
        assert farm_work_overlap(saturday, mode=mode) is True

    def test_task_join_delay_is_independent_of_comment_knobs(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import task_join_delay_seconds
        from app.services.custom.module_delays import JOIN_DELAY_MIN_DEFAULT
        from app.services.custom.neurocommenting_module_service import normalize_nc_settings

        automation = SimpleNamespace(
            module_settings={
                "neurocommenting": {
                    "delay_before_min": 90,
                    "delay_before_max": 90,
                    "join_delay_min": 1500,
                    "join_delay_max": 1500,
                },
                "neurochatting": {
                    "delay_before_min": 45,
                    "delay_before_max": 45,
                    "join_delay_min": 75,
                    "join_delay_max": 75,
                },
            }
        )
        assert task_join_delay_seconds(automation, "neurocommenting") == 1500
        assert task_join_delay_seconds(automation, "neurochatting") == 75
        defaulted = task_join_delay_seconds(SimpleNamespace(module_settings={}), "parser")
        assert defaulted >= JOIN_DELAY_MIN_DEFAULT
        normalized = normalize_nc_settings({"delay_before_min": 90, "delay_before_max": 90})
        assert normalized["delay_before_min"] == 90
        assert normalized["join_delay_min"] == JOIN_DELAY_MIN_DEFAULT
        assert normalized["max_per_account"] == 15
        assert normalized["comment_delay_min"] == 20 * 60
        migrated = normalize_nc_settings({"join_delay_min": 180, "join_delay_max": 240})
        assert migrated["join_delay_min"] == JOIN_DELAY_MIN_DEFAULT
        assert migrated["join_delay_max"] == 40 * 60

        from app.services.custom.chat_broadcast_module_service import normalize_bc_settings
        from app.services.custom.dm_broadcast_module_service import normalize_dm_settings
        from app.services.custom.neurochatting_module_service import normalize_chat_settings
        from app.services.custom.neuroshilling_module_service import normalize_shill_settings

        for normalized in (
            normalize_chat_settings({}),
            normalize_shill_settings({}),
            normalize_bc_settings({}),
            normalize_dm_settings({}),
        ):
            assert normalized["max_per_account"] == 15
            assert normalized["comment_delay_min"] == 20 * 60
            assert normalized["comment_delay_max"] == 40 * 60

    def test_folder_grows_chat_ids_instead_of_resetting(self):
        from app.services.custom.chat_addlist_service import merge_folder_chat_ids

        previous = {"slug": "grown", "filter_id": 7, "chat_ids": [1, 2]}
        assert merge_folder_chat_ids(previous, [2, 3, 4]) == [1, 2, 3, 4]
        assert merge_folder_chat_ids(None, [9]) == [9]

    def test_addlist_slug_on_chat(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import chat_addlist_slug, set_chat_addlist_slug

        chat = SimpleNamespace(invite_link="https://t.me/channel", monitoring_config={})
        set_chat_addlist_slug(chat, "AbCdEfGhIj")
        assert chat_addlist_slug(chat) == "AbCdEfGhIj"
        assert "addlist/AbCdEfGhIj" in (chat.invite_link or "")

    def test_shareable_folder_serializes_with_short_title(self):
        from app.services.custom.chat_addlist_service import _build_dialog_filter, _folder_title

        title = _folder_title("ROMAAAAN (917777800855)")
        assert 1 <= len(title) <= 12
        folder = _build_dialog_filter(2, "ROMAAAAN (917777800855)", [])
        assert type(folder.title).__name__ == "TextWithEntities"
        assert folder.title.text == title
        assert bytes(folder)
        assert type(folder).__name__ == "DialogFilterChatlist"

    def test_addlist_peer_keys_skip_folder_link(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import _match_indexed_peer, _peer_lookup_keys

        chat = SimpleNamespace(
            invite_link="https://t.me/addlist/AbCdEfGhIj",
            external_chat_id="-1001234567890",
            title="Журнал «iQTiSAD»",
        )
        keys = _peer_lookup_keys(chat)
        assert "-1001234567890" in keys
        assert "1234567890" in keys
        assert all("addlist" not in key.lower() for key in keys)
        peer = object()
        assert _match_indexed_peer(chat, {"1234567890": peer}, {}) is peer
        assert _match_indexed_peer(
            SimpleNamespace(invite_link=None, external_chat_id=None, title="Журнал «iQTiSAD»"),
            {},
            {"журнал «iqtisad»": peer},
        ) is peer

    def test_finite_complete_rules(self):
        from app.services.custom.job_service import _finite_should_complete

        assert _finite_should_complete({"status": "ok"}, "parser") is True
        assert _finite_should_complete({"status": "skipped", "reason": "night"}, "parser") is True
        assert _finite_should_complete({"status": "skipped", "reason": "night"}, "masspriming") is False
        assert _finite_should_complete({"status": "ok", "remaining": 4}, "dm_broadcast") is False
        assert _finite_should_complete({"status": "ok", "remaining": 0}, "dm_broadcast") is True

    def test_unique_assign_covers_all_targets_once(self):
        from app.services.custom.parser_service import user_passes_filters
        from app.services.custom.task_dedup import bio_has_link, looks_like_userbot, unique_assign

        targets = ["@a", "@b", "@c", "@d", "@e"]
        assigned = unique_assign([11, 22], targets)
        pooled = [item for items in assigned.values() for item in items]
        assert sorted(pooled) == targets
        assert len(pooled) == len(set(pooled))
        assert assigned[11] and assigned[22]
        again = unique_assign([11, 22], targets, assigned)
        assert again == assigned
        grown = unique_assign([11, 22, 33], targets, assigned)
        pooled_grown = [item for items in grown.values() for item in items]
        assert sorted(pooled_grown) == targets
        assert len(pooled_grown) == len(set(pooled_grown))

        from types import SimpleNamespace

        from app.services.custom.task_dedup import account_owns_chat, persist_unique_chats

        auto = SimpleNamespace(module_settings={})
        persist_unique_chats(auto, "neurocommenting", [11, 22], [101, 102, 103])
        owners = [
            aid
            for aid in (11, 22)
            if account_owns_chat(auto, "neurocommenting", aid, 101)
        ]
        assert len(owners) == 1

        assert bio_has_link("https://t.me/shop") is True
        assert bio_has_link("Пиши t.me/help") is True
        assert bio_has_link("www.example.com") is True
        assert bio_has_link("site.io/x") is True
        assert bio_has_link("просто текст без ссылки") is False
        assert bio_has_link("@only_mention") is False
        assert looks_like_userbot(about="реклама https://t.me/x") is True
        userbot = {"telegram_user_id": 9, "is_bot": False, "is_self": False, "has_bio_link": True}
        person = {"telegram_user_id": 8, "is_bot": False, "is_self": False, "has_bio_link": False}
        assert user_passes_filters(userbot, skip_bots=True) is False
        assert user_passes_filters(person, skip_bots=True) is True
        assert user_passes_filters(userbot, skip_bots=False) is True

    def test_action_delay_is_capped_and_humanized(self):
        from types import SimpleNamespace as NS

        from app.services.custom.module_delays import ACTION_DELAY_MAX_SECONDS, clamp_action_delay_pair, format_delay_ru
        from app.services.custom.telegram_rpc_log_service import humanize_telegram_request

        lo, hi = clamp_action_delay_pair(
            {"delay_before_min": 2951, "delay_before_max": 5391},
            default_min=180,
            default_max=240,
        )
        assert lo == ACTION_DELAY_MAX_SECONDS
        assert hi == ACTION_DELAY_MAX_SECONDS
        assert format_delay_ru(45) == "45 с"
        assert format_delay_ru(90) == "1 мин 30 с"
        assert format_delay_ru(2951) == "49 мин 11 с"
        assert humanize_telegram_request(type("UpdateStatusRequest", (), {"offline": False})()) == "вошёл в онлайн"
        assert humanize_telegram_request(type("PingRequest", (), {})()) is None
        assert humanize_telegram_request(type("GetUsersRequest", (), {})()) is None
        assert humanize_telegram_request(type("GetChannelDifferenceRequest", (), {})()) is None
        assert humanize_telegram_request(type("FooBarRequest", (), {})()) is None
        assert "прочитал" in (humanize_telegram_request(type("GetHistoryRequest", (), {})()) or "")
        assert humanize_telegram_request(type("GetAuthorizationsRequest", (), {})()) is None
        assert humanize_telegram_request(type("GetPasswordRequest", (), {})()) is None
        assert humanize_telegram_request(type("GetAllStoriesRequest", (), {})()) == "открыл ленту историй"
        assert humanize_telegram_request(
            type("ForwardMessagesRequest", (), {"to_peer": type("InputPeerSelf", (), {})()})()
        ) == "переслал в избранное"
        assert "отключил уведомления" in (
            humanize_telegram_request(
                type("UpdateNotifySettingsRequest", (), {"settings": NS(mute_until=2_147_483_647, silent=True)})()
            ) or ""
        )

        from app.services.custom.telegram_rpc_log_service import install_telegram_rpc_logger

        class Sender:
            async def send(self, request, ordered=False):
                return "ok"

        sender = Sender()
        client = NS(_sender=sender)
        install_telegram_rpc_logger(client, account_id=7, automation_id=3)
        assert client._rsd_account_id == 7
        assert client._rsd_automation_id == 3
        assert getattr(sender, "_rsd_rpc_logged", False) is True
        assert sender.send is not Sender.send

    def test_manual_distribute_keeps_uneven_split_and_lists_addlists(self):
        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import (
            TASK_JOINS_KEY,
            apply_task_chat_assignment,
            list_task_addlists,
        )

        even = apply_task_chat_assignment([1, 2, 3], [10, 20, 30, 40, 50, 60])
        sizes = [len(ids) for ids in even.values()]
        assert max(sizes) - min(sizes) <= 1
        manual = apply_task_chat_assignment(
            [1, 2, 3],
            [10, 20, 30, 40],
            manual={1: [10, 20, 30], 2: [40], 3: []},
        )
        assert manual[1] == [10, 20, 30]
        assert manual[2] == [40]
        assert manual[3] == []
        auto = SimpleNamespace(
            module_settings={
                TASK_JOINS_KEY: {
                    "neurocommenting": {
                        "folders": {
                            "11": [{"slug": "AbCd123456", "chat_ids": [1, 2, 3], "url": "https://t.me/addlist/AbCd123456"}]
                        }
                    }
                }
            }
        )
        items = list_task_addlists(auto)
        assert items[0]["url"] == "https://t.me/addlist/AbCd123456"
        assert items[0]["task_key"] == "neurocommenting"
        assert items[0]["chat_count"] == 3

        from app.services.custom.chat_addlist_service import host_export_chat_ids, joins_complete_by_job_type

        assert host_export_chat_ids([], [10, 20, 30]) == [10, 20, 30]
        assert host_export_chat_ids([10], [10, 20]) == [10, 20]
        flags = joins_complete_by_job_type(
            SimpleNamespace(
                module_settings={
                    TASK_JOINS_KEY: {
                        "neurocommenting": {"joins_complete": True, "folders": {}},
                    }
                }
            )
        )
        assert flags["neurocommenting"] is True
        assert flags["discussion"] is False

    def test_task_assignment_caps_at_50_and_reserve_holds_overflow(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app.services.custom.chat_addlist_service import (
            JOIN_WAVE_MAX,
            JOIN_WAVE_MIN,
            TASK_CHATS_PER_ACCOUNT,
            pick_join_wave,
            split_task_assignment,
            wave_rest_until,
        )

        chats = list(range(1, 161))
        assignment, reserve = split_task_assignment([1, 2, 3], chats)
        assert all(len(ids) == TASK_CHATS_PER_ACCOUNT for ids in assignment.values())
        assert len(reserve) == 10
        assert sorted([cid for ids in assignment.values() for cid in ids] + reserve) == chats

        manual, leftover = split_task_assignment(
            [10, 20],
            list(range(1, 81)),
            manual={10: list(range(1, 81)), 20: []},
        )
        assert len(manual[10]) == 50
        assert manual[20] == []
        assert len(leftover) == 30
        assert set(leftover).isdisjoint(manual[10])

        class Seq:
            def randint(self, lo, hi):
                del hi
                return lo

            def sample(self, pool, size):
                return list(pool)[:size]

            def shuffle(self, items):
                return items

        wave = pick_join_wave(list(range(1, 40)), rng=Seq())
        assert JOIN_WAVE_MIN <= len(wave) <= JOIN_WAVE_MAX
        assert wave == list(range(1, JOIN_WAVE_MIN + 1))
        short = pick_join_wave([7, 8, 9], rng=Seq())
        assert sorted(short) == [7, 8, 9]
        refill = pick_join_wave(list(range(1, 40)), rng=Seq(), size=4)
        assert refill == [1, 2, 3, 4]
        from app.services.custom.chat_addlist_service import wave_quota_hit
        assert wave_quota_hit({"joined": 2, "size": 18}, already_joined=2) is False
        assert wave_quota_hit({"joined": 18, "size": 18}, already_joined=18) is True
        assert wave_quota_hit({}, already_joined=2) is False
        assert wave_quota_hit({}, already_joined=JOIN_WAVE_MIN) is True

        from datetime import timedelta

        from app.services.custom.account_pacing import moscow_day_start_utc

        now = datetime(2026, 10, 13, 18, 0, tzinfo=ZoneInfo("Europe/Moscow")).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        rest = wave_rest_until(now)
        assert rest == moscow_day_start_utc(now) + timedelta(days=2)

    def test_shuffle_mixes_folders_fill_keeps_existing_mix_keeps_joined(self):
        from app.services.custom.chat_addlist_service import even_redistribute, split_task_assignment

        folder1 = list(range(1, 101))
        folder2 = list(range(101, 201))
        chats = folder1 + folder2
        sequential, _ = split_task_assignment([1], chats, shuffle=False)
        assert sequential[1] == list(range(1, 51))
        assert set(sequential[1]).issubset(set(folder1))

        class Reverse:
            def shuffle(self, items):
                items.reverse()

        mixed, reserve = split_task_assignment([1], chats, shuffle=True, rng=Reverse())
        assert mixed[1] == list(range(200, 150, -1))
        assert set(mixed[1]).issubset(set(folder2))
        assert not set(mixed[1]).issubset(set(folder1))
        assert 1 in reserve

        previous = {1: list(range(1, 51))}
        filled, leftover = split_task_assignment(
            [1, 2],
            list(range(1, 61)),
            previous=previous,
            shuffle=False,
        )
        assert filled[1] == list(range(1, 51))
        assert filled[2] == list(range(51, 61))
        assert leftover == []

        remixed = even_redistribute(
            [1],
            chats,
            previous={1: [1, 2, 3]},
            shuffle=True,
            rng=Reverse(),
            max_per_account=50,
        )
        assert remixed[1][:3] == [1, 2, 3]
        assert remixed[1][3:] == list(range(200, 153, -1))

        assignment = {1: [10, 20, 30], 2: [40, 50]}
        already = {1: [10, 20]}
        joined_pairs = {(int(aid), int(cid)) for aid, ids in already.items() for cid in ids}
        pending = sum(
            1
            for aid, ids in assignment.items()
            for cid in ids
            if (int(aid), int(cid)) not in joined_pairs
        )
        assert pending == 3

        from types import SimpleNamespace

        from app.services.custom.chat_addlist_service import pool_actor_selectable, pool_actor_status
        from app.services.custom.job_service import actor_label

        parked = SimpleNamespace(
            id=32,
            display_name="Maksim Toples",
            username="MaksimToples",
            phone_number="15674004008",
            is_active=True,
            is_banned=False,
            is_frozen=False,
            flood_quarantined_until=datetime(2099, 1, 1, 12, 0),
            session_file_path="ok.session",
            encrypted_session="x",
        )
        assert actor_label(parked) == "Maksim Toples (15674004008)"
        assert pool_actor_status(parked) == "карантин"
        assert pool_actor_selectable(parked) is True
        assert pool_actor_status(None) == "нет в базе"

        from app.services.custom.chat_addlist_service import claim_joined_folders

        folder_of = {cid: 1 for cid in range(1, 61)}
        stolen, leftover = split_task_assignment(
            [32, 17],
            list(range(1, 61)),
            previous=claim_joined_folders(
                {17: list(range(1, 17)), 32: []},
                {17: [1, 2], 32: list(range(1, 28))},
                folder_of,
                list(range(1, 61)),
                max_per_account=50,
            ),
            shuffle=False,
            folder_of=folder_of,
        )
        assert stolen[32][:27] == list(range(1, 28))
        assert len(stolen[32]) == 50
        assert set(stolen[32]).isdisjoint(stolen[17])
        assert not set(range(1, 28)) & set(stolen[17])

    def test_sibling_tasks_keep_the_same_chat_owners(self):
        from app.services.custom.chat_addlist_service import (
            merge_assignment_previous,
            sibling_previous,
            split_task_assignment,
        )

        chatting = {1: [10, 20, 30], 2: [40, 50, 60]}
        plans = {"neurochatting": {"assignments": {"1": [10, 20, 30], "2": [40, 50, 60]}}}
        hint = sibling_previous(plans, "neuroshilling", [1, 2])
        assert hint[1] == [10, 20, 30]
        assert hint[2] == [40, 50, 60]
        previous = merge_assignment_previous({}, hint)
        assignment, reserve = split_task_assignment(
            [1, 2],
            [10, 20, 30, 40, 50, 60],
            previous=previous,
        )
        assert assignment[1] == chatting[1]
        assert assignment[2] == chatting[2]
        assert reserve == []
        other_accounts = sibling_previous(plans, "neuroshilling", [3, 4])
        assert other_accounts == {}

    def test_sibling_owners_win_over_conflicting_task_plan(self):
        from app.services.custom.chat_addlist_service import (
            merge_assignment_previous,
            sibling_previous,
            split_task_assignment,
        )

        plans = {"neurochatting": {"assignments": {"1": [10, 20], "2": [30, 40]}}}
        swapped = {1: [30, 40], 2: [10, 20]}
        hint = sibling_previous(plans, "neuroshilling", [1, 2])
        previous = merge_assignment_previous(swapped, hint)
        assignment, _ = split_task_assignment([1, 2], [10, 20, 30, 40, 50, 60], previous=previous)
        assert assignment[1][:2] == [10, 20]
        assert assignment[2][:2] == [30, 40]
        assert 50 in assignment[1] + assignment[2]
        assert 60 in assignment[1] + assignment[2]

    def test_ready_addlists_cover_sibling_assignment(self):
        from app.services.custom.chat_addlist_service import (
            addlists_from_chat_targets,
            best_addlist_for_chats,
            covering_addlist_rows,
            merge_sibling_folders,
            spec_is_live,
            warmup_task_joins_enabled,
        )

        plans = {
            "neurochatting": {
                "assignments": {"1": [10, 20, 30, 40]},
                "folders": {
                    "1": [{"slug": "ReadyFolder1", "url": "https://t.me/addlist/ReadyFolder1", "chat_ids": [10, 20, 30, 40]}]
                },
            }
        }
        covered = covering_addlist_rows(plans, [10, 20, 30, 40, 50])
        assert covered[0]["slug"] == "ReadyFolder1"
        merged = merge_sibling_folders(plans, {1: [10, 20, 30, 40], 2: [50, 60]}, {})
        assert merged["1"][0]["slug"] == "ReadyFolder1"
        assert "2" not in merged
        row, cover = best_addlist_for_chats(covered, [10, 20, 50])
        assert row["slug"] == "ReadyFolder1"
        assert cover == [10, 20]
        from types import SimpleNamespace

        class Chat:
            def __init__(self, ident, slug):
                self.id = ident
                self.invite_link = f"https://t.me/addlist/{slug}"
                self.monitoring_config = {"addlist_slug": slug}

        rows = addlists_from_chat_targets([Chat(10, "ReadyFolder1"), Chat(20, "ReadyFolder1"), Chat(99, "OtherFold")])
        slugs = {item["slug"] for item in rows}
        assert slugs == {"ReadyFolder1", "OtherFold"}
        assert spec_is_live({"task_key": "neuroshilling"}, {"shilling"})
        assert not spec_is_live({"task_key": "neuroshilling"}, {"discussion"})
        assert spec_is_live({"task_key": "warmup"}, set(), warmup_joins=True)
        assert not spec_is_live({"task_key": "warmup"}, set(), warmup_joins=False)
        auto = SimpleNamespace(
            account_warmup_enabled=True,
            module_settings={"warmup": {"mode": "auto", "do_joins": True, "folder_ids": [], "chat_ids": []}},
        )
        assert warmup_task_joins_enabled(auto) is False
        auto.module_settings["warmup"]["folder_ids"] = [3]
        assert warmup_task_joins_enabled(auto) is True


class TestReplaceTaskPoolAccount:
    async def _account(
        self,
        session: AsyncSession,
        automation: CustomAutomation,
        *,
        username: str,
        phone: str,
        in_pool: bool = True,
        banned: bool = False,
    ):
        from app.alembic.models import PoolAccount, SocialAccount
        from app.services.account_pool_service import get_or_create_default_pool

        account = SocialAccount(
            provider="telegram",
            phone_number=phone,
            username=username,
            display_name=username,
            account_class="one_day",
            encrypted_session="mock_encrypted_session",
            session_file_path=f"sessions/{username}.session",
            is_active=True,
            is_banned=banned,
        )
        session.add(account)
        await session.flush()
        if in_pool:
            pool = await get_or_create_default_pool(session, automation.id)
            session.add(
                PoolAccount(
                    account_pool_id=pool.id,
                    social_account_id=account.id,
                    assigned_class="one_day",
                    custom_automation_id=automation.id,
                )
            )
            await session.flush()
        return account

    def _chat(self, automation: CustomAutomation, title: str):
        return ChatTarget(
            custom_automation_id=automation.id,
            provider="telegram",
            title=title,
            invite_link=f"https://t.me/{title}",
            chat_type="channel",
            is_active=True,
        )

    def _guards(self):
        from contextlib import ExitStack
        from unittest.mock import AsyncMock, patch

        stack = ExitStack()
        stack.enter_context(patch(
            "app.services.custom.job_service.log_active",
            new=AsyncMock(),
        ))
        stack.enter_context(patch(
            "app.services.custom.telegram_account_client.TelegramAccountClient.for_account",
            side_effect=AssertionError("telegram session"),
        ))
        stack.enter_context(patch(
            "app.services.custom.chat_addlist_service.join_pending_addlists",
            side_effect=AssertionError("join_pending_addlists"),
        ))
        stack.enter_context(patch(
            "app.services.custom.chat_join_service.join_task_waves",
            side_effect=AssertionError("join_task_waves"),
        ))
        return stack

    async def test_replace_moves_only_this_task_pool(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from copy import deepcopy

        from app.alembic.models import (
            AccountChatMembership,
            ChatJoinStatus,
            CustomJob,
            MembershipPurpose,
        )
        from app.services.custom.chat_addlist_service import (
            collect_plan_addlists,
            list_task_addlists,
            pick_task_host,
            replace_task_pool_account,
        )
        from app.services.custom.chat_membership_service import get_membership, get_reader_account
        from app.services.custom.task_dedup import account_owns_chat

        assert pick_task_host(5, 5, 9, [9], set()) is None
        assert pick_task_host(5, 5, 9, [9, 3], {3, 9}) == 3
        assert pick_task_host(3, 5, 9, [9, 3], {9}) == 3

        old = await self._account(test_session, custom_automation, username="repl_old", phone="+79993000001")
        new = await self._account(test_session, custom_automation, username="repl_new", phone="+79993000002")
        second = await self._account(test_session, custom_automation, username="repl_second", phone="+79993000003")
        kept = self._chat(custom_automation, "repl_kept")
        moved_late = self._chat(custom_automation, "repl_late")
        shared = self._chat(custom_automation, "repl_shared")
        second_chat = self._chat(custom_automation, "repl_second_chat")
        reserve = self._chat(custom_automation, "repl_reserve")
        other = self._chat(custom_automation, "repl_other")
        test_session.add_all([kept, moved_late, shared, second_chat, reserve, other])
        await test_session.flush()
        moved = [moved_late.id, kept.id, shared.id]
        now = _now()
        for chat in (kept, moved_late, shared, other):
            test_session.add(
                AccountChatMembership(
                    custom_automation_id=custom_automation.id,
                    social_account_id=old.id,
                    chat_target_id=chat.id,
                    join_status=ChatJoinStatus.JOINED.value,
                    purpose=MembershipPurpose.WATCHER.value,
                    priority=0,
                    join_attempts=0,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        slug = "ReadyPoolSlug1"
        empty_slug = "EmptySlugRow1"
        stay_slug = "StaySlugRow01"
        other_slug = "OtherSlug0001"
        custom_automation.module_settings = {
            "neurocommenting": {
                "enabled": True,
                "account_ids": [old.id, second.id],
                "chat_ids": [moved_late.id, kept.id, shared.id, second_chat.id, reserve.id],
                "folder_ids": [4],
                "chat_assignments": {
                    str(old.id): list(moved),
                    str(second.id): [second_chat.id],
                },
                "reserve_chat_ids": [reserve.id],
            },
            "neurochatting": {
                "enabled": True,
                "account_ids": [old.id],
                "chat_ids": [other.id, shared.id],
                "chat_assignments": {str(old.id): [other.id, shared.id]},
                "reserve_chat_ids": [],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {
                        str(old.id): list(moved),
                        str(second.id): [second_chat.id],
                    },
                    "reserve": [reserve.id],
                    "folders": {
                        str(old.id): [
                            {
                                "slug": slug,
                                "url": f"https://t.me/addlist/{slug}",
                                "filter_id": 7,
                                "chat_ids": list(moved),
                                "title": "old pool",
                            },
                            {
                                "slug": empty_slug,
                                "url": f"https://t.me/addlist/{empty_slug}",
                                "filter_id": 9,
                                "chat_ids": [],
                                "title": "empty slug",
                            },
                            {
                                "slug": stay_slug,
                                "url": f"https://t.me/addlist/{stay_slug}",
                                "filter_id": 3,
                                "chat_ids": [reserve.id],
                                "title": "not this pool",
                            },
                        ],
                    },
                    "host_account_id": old.id,
                    "waves": {str(old.id): {"joined": 1}},
                    "pending_joins": 3,
                    "joins_complete": False,
                },
                "neurochatting": {
                    "assignments": {str(old.id): [other.id, shared.id]},
                    "reserve": [],
                    "folders": {
                        str(old.id): [{
                            "slug": other_slug,
                            "url": f"https://t.me/addlist/{other_slug}",
                            "chat_ids": [other.id, shared.id],
                        }],
                    },
                    "host_account_id": old.id,
                },
            },
        }
        nc_job = CustomJob(
            custom_automation_id=custom_automation.id,
            category="module",
            job_type="neurocommenting",
            title="Нейрокомментинг",
            status="running",
            params={
                "account_ids": [old.id, second.id],
                "chat_assignments": {str(old.id): list(moved), str(second.id): [second_chat.id]},
                "reserve_chat_ids": [reserve.id],
            },
            result={},
            logs=[],
        )
        other_job = CustomJob(
            custom_automation_id=custom_automation.id,
            category="module",
            job_type="discussion",
            title="Нейрочаттинг",
            status="running",
            params={"account_ids": [old.id], "chat_assignments": {str(old.id): [other.id, shared.id]}},
            result={},
            logs=[],
        )
        test_session.add_all([nc_job, other_job])
        await test_session.commit()
        other_task = deepcopy(custom_automation.module_settings["neurochatting"])
        other_plan = deepcopy(custom_automation.module_settings["_task_joins"]["neurochatting"])
        other_job_params = deepcopy(other_job.params)

        with self._guards():
            data = await replace_task_pool_account(
                test_session,
                custom_automation,
                "neurocommenting",
                account_id=old.id,
                replacement_account_id=new.id,
            )

        plan = custom_automation.module_settings["_task_joins"]["neurocommenting"]
        settings = custom_automation.module_settings["neurocommenting"]
        assert settings["account_ids"] == [new.id, second.id]
        assert old.id not in settings["account_ids"]
        assert settings["chat_assignments"][str(new.id)] == moved
        assert settings["chat_assignments"][str(second.id)] == [second_chat.id]
        assert str(old.id) not in settings["chat_assignments"]
        assert settings["reserve_chat_ids"] == [reserve.id]
        assert settings["chat_ids"] == [moved_late.id, kept.id, shared.id, second_chat.id, reserve.id]
        assert settings["folder_ids"] == [4]
        assert plan["assignments"][str(new.id)] == moved
        assert plan["assignments"][str(second.id)] == [second_chat.id]
        assert str(old.id) not in plan["assignments"]
        assert plan["reserve"] == [reserve.id]
        assert plan["host_account_id"] == second.id
        assert plan["waves"] == {str(old.id): {"joined": 1}}
        rows = {row["slug"]: row for row in plan["folders"][str(new.id)]}
        assert set(rows) == {slug, empty_slug}
        assert "filter_id" not in rows[slug]
        assert rows[slug]["chat_ids"] == moved
        assert "filter_id" not in rows[empty_slug]
        assert rows[empty_slug]["chat_ids"] == []
        stayed = plan["folders"][str(old.id)]
        assert len(stayed) == 1
        assert stayed[0]["slug"] == stay_slug
        assert stayed[0]["filter_id"] == 3
        pins = plan["replacement_pins"]
        assert pins[str(moved_late.id)] == new.id
        assert pins[str(kept.id)] == new.id
        assert pins[str(shared.id)] == new.id
        assert custom_automation.module_settings["neurochatting"] == other_task
        assert custom_automation.module_settings["_task_joins"]["neurochatting"] == other_plan
        assert other_job.params == other_job_params
        assert nc_job.params["account_ids"] == [new.id, second.id]
        assert nc_job.params["chat_assignments"][str(new.id)] == moved
        assert nc_job.params["chat_assignments"][str(second.id)] == [second_chat.id]
        assert nc_job.params["reserve_chat_ids"] == [reserve.id]
        slugs = {item["slug"] for item in collect_plan_addlists(custom_automation.module_settings["_task_joins"])}
        assert slug in slugs
        assert empty_slug in slugs
        assert stay_slug in slugs
        assert other_slug in slugs
        listed = {item["slug"]: item for item in list_task_addlists(custom_automation)}
        assert listed[slug]["account_id"] == new.id
        assert listed[empty_slug]["account_id"] == new.id
        assert listed[stay_slug]["account_id"] == old.id
        assert listed[other_slug]["account_id"] == old.id
        assert "не запускалась" not in data["notice"]
        for chat in (kept, moved_late):
            assert await get_membership(test_session, chat.id, old.id) is None
            member = await get_membership(test_session, chat.id, new.id)
            assert member is not None
            assert member.purpose == MembershipPurpose.ACTOR.value
            assert member.join_status != ChatJoinStatus.JOINED.value
            assert member.join_status != ChatJoinStatus.LEFT.value
            assert await get_reader_account(test_session, chat) is None
            assert account_owns_chat(custom_automation, "neurocommenting", new.id, chat.id)
            assert not account_owns_chat(custom_automation, "neurocommenting", old.id, chat.id)
        shared_old = await get_membership(test_session, shared.id, old.id)
        assert shared_old is not None
        assert shared_old.join_status == ChatJoinStatus.JOINED.value
        shared_new = await get_membership(test_session, shared.id, new.id)
        assert shared_new is not None
        assert shared_new.join_status != ChatJoinStatus.JOINED.value
        other_member = await get_membership(test_session, other.id, old.id)
        assert other_member is not None
        assert other_member.join_status == ChatJoinStatus.JOINED.value
        assert account_owns_chat(custom_automation, "neurochatting", old.id, other.id)
        assert not account_owns_chat(custom_automation, "neurocommenting", second.id, kept.id)
        assert account_owns_chat(custom_automation, "neurocommenting", second.id, second_chat.id)

    async def test_replace_without_addlist_does_not_mark_joined(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from sqlalchemy import select

        from app.alembic.models import AccountChatMembership, ChatJoinStatus, MembershipPurpose
        from app.services.custom.chat_addlist_service import (
            NO_ADDLIST_JOIN_NOTICE,
            replace_task_pool_account,
        )
        from app.services.custom.chat_membership_service import get_membership

        old = await self._account(test_session, custom_automation, username="noslug_old", phone="+79993000011")
        new = await self._account(test_session, custom_automation, username="noslug_new", phone="+79993000012")
        chat = self._chat(custom_automation, "noslug_chat")
        spare = self._chat(custom_automation, "noslug_spare")
        test_session.add_all([chat, spare])
        await test_session.flush()
        now = _now()
        test_session.add(
            AccountChatMembership(
                custom_automation_id=custom_automation.id,
                social_account_id=old.id,
                chat_target_id=chat.id,
                join_status=ChatJoinStatus.JOINED.value,
                purpose=MembershipPurpose.WATCHER.value,
                priority=0,
                join_attempts=0,
                joined_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        custom_automation.module_settings = {
            "neurocommenting": {
                "enabled": True,
                "account_ids": [old.id],
                "chat_ids": [chat.id, spare.id],
                "chat_assignments": {str(old.id): [chat.id]},
                "reserve_chat_ids": [spare.id],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {str(old.id): [chat.id]},
                    "reserve": [spare.id],
                    "folders": {},
                    "host_account_id": old.id,
                },
            },
        }
        await test_session.commit()
        with self._guards():
            data = await replace_task_pool_account(
                test_session,
                custom_automation,
                "neurocommenting",
                account_id=old.id,
                replacement_account_id=new.id,
            )
        assert data["notice"] == NO_ADDLIST_JOIN_NOTICE
        assert "addlist" in data["notice"].lower()
        assert custom_automation.module_settings["neurocommenting"]["account_ids"] == [new.id]
        assert custom_automation.module_settings["neurocommenting"]["reserve_chat_ids"] == [spare.id]
        assert custom_automation.module_settings["_task_joins"]["neurocommenting"]["host_account_id"] == new.id
        assert await get_membership(test_session, chat.id, old.id) is None
        member = await get_membership(test_session, chat.id, new.id)
        assert member is not None
        assert member.join_status != ChatJoinStatus.JOINED.value
        rows = (
            await test_session.execute(
                select(AccountChatMembership).where(AccountChatMembership.chat_target_id.in_([chat.id, spare.id]))
            )
        ).scalars().all()
        assert rows
        assert all(row.join_status != ChatJoinStatus.JOINED.value for row in rows)
        assert all(row.join_status != ChatJoinStatus.LEFT.value for row in rows)

    async def test_replace_rejects_and_keeps_state(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from copy import deepcopy

        from app.services.custom.chat_addlist_service import replace_task_pool_account

        old = await self._account(test_session, custom_automation, username="rej_old", phone="+79993000021")
        second = await self._account(test_session, custom_automation, username="rej_second", phone="+79993000022")
        outsider = await self._account(
            test_session, custom_automation, username="rej_out", phone="+79993000023", in_pool=False,
        )
        banned = await self._account(
            test_session, custom_automation, username="rej_ban", phone="+79993000024", banned=True,
        )
        chat = self._chat(custom_automation, "rej_chat")
        test_session.add(chat)
        await test_session.flush()
        custom_automation.module_settings = {
            "neurocommenting": {
                "account_ids": [old.id, second.id],
                "chat_assignments": {str(old.id): [chat.id], str(second.id): [chat.id]},
                "reserve_chat_ids": [],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {str(old.id): [chat.id], str(second.id): []},
                    "reserve": [],
                    "host_account_id": old.id,
                },
            },
        }
        await test_session.commit()
        before = deepcopy(custom_automation.module_settings)
        with self._guards():
            with pytest.raises(ValueError, match="уже"):
                await replace_task_pool_account(
                    test_session,
                    custom_automation,
                    "neurocommenting",
                    account_id=old.id,
                    replacement_account_id=second.id,
                )
            with pytest.raises(ValueError, match="не из пула"):
                await replace_task_pool_account(
                    test_session,
                    custom_automation,
                    "neurocommenting",
                    account_id=old.id,
                    replacement_account_id=outsider.id,
                )
            with pytest.raises(ValueError, match="нельзя выбрать"):
                await replace_task_pool_account(
                    test_session,
                    custom_automation,
                    "neurocommenting",
                    account_id=old.id,
                    replacement_account_id=banned.id,
                )
        assert custom_automation.module_settings == before

    async def test_replace_route_returns_400(
        self,
        client: AsyncClient,
        client_token: str,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        old = await self._account(test_session, custom_automation, username="http_old", phone="+79993000031")
        second = await self._account(test_session, custom_automation, username="http_second", phone="+79993000032")
        chat = self._chat(custom_automation, "http_chat")
        test_session.add(chat)
        await test_session.flush()
        custom_automation.module_settings = {
            "neurocommenting": {
                "account_ids": [old.id, second.id],
                "chat_assignments": {str(old.id): [chat.id]},
                "reserve_chat_ids": [],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {str(old.id): [chat.id], str(second.id): []},
                    "reserve": [],
                },
            },
        }
        await test_session.commit()
        response = await client.post(
            f"/api/custom/automations/{custom_automation.id}/task-pool/replace",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "task_key": "neurocommenting",
                "account_id": old.id,
                "replacement_account_id": second.id,
            },
        )
        assert response.status_code == 400, response.text
        assert "уже" in response.json()["detail"]
        await test_session.refresh(custom_automation)
        assert second.id in custom_automation.module_settings["neurocommenting"]["account_ids"]
        assert old.id in custom_automation.module_settings["neurocommenting"]["account_ids"]

    async def test_replace_pins_survive_joined_folder_claim(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.alembic.models import AccountChatMembership, ChatJoinStatus, MembershipPurpose
        from app.services.custom.chat_addlist_service import (
            ensure_task_join_plan,
            replace_task_pool_account,
        )

        old = await self._account(test_session, custom_automation, username="pin_old", phone="+79993000021")
        new = await self._account(test_session, custom_automation, username="pin_new", phone="+79993000022")
        neighbor = await self._account(test_session, custom_automation, username="pin_neighbor", phone="+79993000023")
        folder = ChatFolder(
            custom_automation_id=custom_automation.id,
            name="repl_pin_folder",
            created_at=_now(),
            updated_at=_now(),
        )
        test_session.add(folder)
        await test_session.flush()
        moved_a = self._chat(custom_automation, "pin_moved_a")
        moved_b = self._chat(custom_automation, "pin_moved_b")
        neighbor_chat = self._chat(custom_automation, "pin_neighbor_chat")
        for chat in (moved_a, moved_b, neighbor_chat):
            chat.folder_id = folder.id
        test_session.add_all([moved_a, moved_b, neighbor_chat])
        await test_session.flush()
        now = _now()
        for chat in (moved_a, moved_b):
            test_session.add(
                AccountChatMembership(
                    custom_automation_id=custom_automation.id,
                    social_account_id=old.id,
                    chat_target_id=chat.id,
                    join_status=ChatJoinStatus.JOINED.value,
                    purpose=MembershipPurpose.WATCHER.value,
                    priority=0,
                    join_attempts=0,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        test_session.add(
            AccountChatMembership(
                custom_automation_id=custom_automation.id,
                social_account_id=neighbor.id,
                chat_target_id=neighbor_chat.id,
                join_status=ChatJoinStatus.JOINED.value,
                purpose=MembershipPurpose.WATCHER.value,
                priority=0,
                join_attempts=0,
                joined_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        moved = [moved_a.id, moved_b.id]
        custom_automation.module_settings = {
            "neurocommenting": {
                "enabled": True,
                "account_ids": [old.id, neighbor.id],
                "chat_ids": [moved_a.id, moved_b.id, neighbor_chat.id],
                "chat_assignments": {
                    str(old.id): list(moved),
                    str(neighbor.id): [neighbor_chat.id],
                },
                "reserve_chat_ids": [],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {
                        str(old.id): list(moved),
                        str(neighbor.id): [neighbor_chat.id],
                    },
                    "reserve": [],
                    "folders": {},
                    "host_account_id": old.id,
                },
            },
        }
        await test_session.commit()
        chat_ids = [moved_a.id, moved_b.id, neighbor_chat.id]

        with self._guards():
            await replace_task_pool_account(
                test_session,
                custom_automation,
                "neurocommenting",
                account_id=old.id,
                replacement_account_id=new.id,
            )
            account_ids = list(custom_automation.module_settings["neurocommenting"]["account_ids"])
            await ensure_task_join_plan(
                test_session,
                custom_automation,
                "neurocommenting",
                account_ids,
                chat_ids,
                mix=False,
            )

        plan = custom_automation.module_settings["_task_joins"]["neurocommenting"]
        assert set(plan["assignments"][str(new.id)]) == set(moved)
        assert moved_a.id not in plan["assignments"].get(str(neighbor.id), [])
        assert moved_b.id not in plan["assignments"].get(str(neighbor.id), [])
        assert neighbor_chat.id in plan["assignments"][str(neighbor.id)]
        assert plan["replacement_pins"][str(moved_a.id)] == new.id
        assert plan["replacement_pins"][str(moved_b.id)] == new.id

        with self._guards():
            await ensure_task_join_plan(
                test_session,
                custom_automation,
                "neurocommenting",
                account_ids,
                chat_ids,
                mix=True,
            )

        mixed = custom_automation.module_settings["_task_joins"]["neurocommenting"]
        assert not mixed.get("replacement_pins")
        assert set(mixed["assignments"][str(neighbor.id)]) == set(chat_ids)
        assert moved_a.id not in mixed["assignments"].get(str(new.id), [])
        assert moved_b.id not in mixed["assignments"].get(str(new.id), [])

    async def test_ensure_watcher_after_replace_keeps_single_slot(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from sqlalchemy import select

        from app.alembic.models import AccountChatMembership, ChatJoinStatus, MembershipPurpose
        from app.services.custom.chat_addlist_service import (
            ensure_task_join_plan,
            replace_task_pool_account,
        )
        from app.services.custom.chat_membership_service import ensure_watcher_membership
        from app.services.custom.chat_scope import is_public_readable

        old = await self._account(test_session, custom_automation, username="watch_old", phone="+79993000031")
        new = await self._account(test_session, custom_automation, username="watch_new", phone="+79993000032")
        exclusive = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="closed exclusive",
            invite_link="https://t.me/+Abcd1234secretWatch",
            chat_type="channel",
            is_active=True,
        )
        shared = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            title="closed shared",
            invite_link="https://t.me/+Abcd1234secretShare",
            chat_type="channel",
            is_active=True,
        )
        test_session.add_all([exclusive, shared])
        await test_session.flush()
        assert not is_public_readable(exclusive)
        assert not is_public_readable(shared)
        now = _now()
        for chat in (exclusive, shared):
            test_session.add(
                AccountChatMembership(
                    custom_automation_id=custom_automation.id,
                    social_account_id=old.id,
                    chat_target_id=chat.id,
                    join_status=ChatJoinStatus.JOINED.value,
                    purpose=MembershipPurpose.WATCHER.value,
                    priority=0,
                    join_attempts=0,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        custom_automation.module_settings = {
            "neurocommenting": {
                "enabled": True,
                "account_ids": [old.id],
                "chat_ids": [exclusive.id, shared.id],
                "chat_assignments": {str(old.id): [exclusive.id, shared.id]},
                "reserve_chat_ids": [],
            },
            "neurochatting": {
                "enabled": True,
                "account_ids": [old.id],
                "chat_ids": [shared.id],
                "chat_assignments": {str(old.id): [shared.id]},
                "reserve_chat_ids": [],
            },
            "_task_joins": {
                "neurocommenting": {
                    "assignments": {str(old.id): [exclusive.id, shared.id]},
                    "reserve": [],
                    "folders": {},
                    "host_account_id": old.id,
                },
                "neurochatting": {
                    "assignments": {str(old.id): [shared.id]},
                    "reserve": [],
                    "folders": {},
                    "host_account_id": old.id,
                },
            },
        }
        await test_session.commit()

        with self._guards():
            await replace_task_pool_account(
                test_session,
                custom_automation,
                "neurocommenting",
                account_id=old.id,
                replacement_account_id=new.id,
            )
            settings = custom_automation.module_settings["neurocommenting"]
            await ensure_task_join_plan(
                test_session,
                custom_automation,
                "neurocommenting",
                list(settings["account_ids"]),
                [exclusive.id, shared.id],
                mix=False,
            )
            created = await ensure_watcher_membership(
                test_session, custom_automation.id, exclusive
            )
            shared_created = await ensure_watcher_membership(
                test_session, custom_automation.id, shared
            )

        assert created == 0
        assert shared_created == 0
        exclusive_rows = (
            await test_session.execute(
                select(AccountChatMembership).where(
                    AccountChatMembership.chat_target_id == exclusive.id
                )
            )
        ).scalars().all()
        occupied = [
            row for row in exclusive_rows
            if row.join_status not in {ChatJoinStatus.LEFT.value, ChatJoinStatus.BANNED.value}
        ]
        assert len(occupied) == 1
        assert occupied[0].social_account_id == new.id
        assert all(row.social_account_id != old.id for row in exclusive_rows)
        shared_rows = (
            await test_session.execute(
                select(AccountChatMembership).where(
                    AccountChatMembership.chat_target_id == shared.id
                )
            )
        ).scalars().all()
        shared_old = [
            row for row in shared_rows
            if row.social_account_id == old.id and row.join_status == ChatJoinStatus.JOINED.value
        ]
        assert len(shared_old) == 1
        assert shared_old[0].purpose == MembershipPurpose.WATCHER.value

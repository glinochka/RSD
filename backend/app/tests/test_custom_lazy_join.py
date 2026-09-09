"""Lazy join coverage: watchers, on-demand actors, per-account join delays."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import (
    AccountChatMembership,
    AccountClass,
    ChatJoinStatus,
    ChatTarget,
    CustomAdmin,
    CustomAutomation,
    MembershipPurpose,
    PendingChatAction,
    PendingChatActionStatus,
    PoolAccount,
    SocialAccount,
)
from app.utils.security import get_password_hash
from app.services.account_pool_service import get_or_create_default_pool
from app.services.custom.account_roles import default_roles_for_class
from app.services.custom.chat_membership_service import (
    ACTION_JOIN_PRIORITY,
    WATCHER_REPLACE_PRIORITY,
    apply_account_join_cooldown,
    ensure_memberships_for_chat,
    ensure_memberships_for_automation,
    get_reader_account,
    is_chat_watchable,
    pick_next_pending_membership,
    queue_actor_for_chat,
    replace_watchers_for_dead_account,
    retire_reader_and_replace,
)
from app.services.custom.chat_scope import is_public_readable
from app.services.custom.pending_action_service import (
    enqueue_pending_action,
    ensure_accounts_ready,
    has_pending_action,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="lazy_join_admin",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)
    return admin


@pytest.fixture
async def custom_automation(test_session: AsyncSession, custom_admin: CustomAdmin) -> CustomAutomation:
    from app.services.custom.prompt_service import create_default_prompts

    automation = CustomAutomation(
        name="Lazy Join Automation",
        client_name="Test Client",
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


async def _add_account(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    username: str,
    phone: str,
    account_class: str = AccountClass.TRUSTED.value,
) -> SocialAccount:
    pool = await get_or_create_default_pool(session, automation.id)
    account = SocialAccount(
        provider="telegram",
        phone_number=phone,
        username=username,
        display_name=username,
        account_class=account_class,
        encrypted_session="mock_encrypted_session",
        session_file_path=f"sessions/{username}.session",
        is_active=True,
        is_banned=False,
    )
    session.add(account)
    await session.flush()
    session.add(
        PoolAccount(
            account_pool_id=pool.id,
            social_account_id=account.id,
            assigned_class=account_class,
            custom_automation_id=automation.id,
            roles=default_roles_for_class(account_class),
        )
    )
    await session.commit()
    await session.refresh(account)
    return account


async def _add_chat(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    title: str = "Group",
    chat_type: str = "chat",
    invite_link: str = "https://t.me/+invitehash12",
    join_status: str = ChatJoinStatus.PENDING.value,
) -> ChatTarget:
    chat = ChatTarget(
        custom_automation_id=automation.id,
        provider="telegram",
        invite_link=invite_link,
        title=title,
        chat_type=chat_type,
        mode="monitoring",
        source="manual",
        join_status=join_status,
        is_active=True,
    )
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


class TestLazyJoinCoverage:
    async def test_public_channel_is_readable_without_join(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        chat = await _add_chat(
            test_session,
            custom_automation,
            title="News",
            chat_type="channel",
            invite_link="https://t.me/publicnews",
        )
        assert is_public_readable(chat) is True
        created = await ensure_memberships_for_chat(test_session, custom_automation.id, chat)
        await test_session.commit()
        assert created == 0
        await test_session.refresh(chat)
        assert chat.join_status == ChatJoinStatus.JOINED.value
        assert await is_chat_watchable(test_session, chat) is True

    async def test_group_gets_single_watcher(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        await _add_account(test_session, custom_automation, username="w1", phone="+79991001001")
        await _add_account(test_session, custom_automation, username="w2", phone="+79991001002")
        chat = await _add_chat(test_session, custom_automation)
        created = await ensure_memberships_for_automation(test_session, custom_automation.id)
        await test_session.commit()
        assert created == 1
        total = (
            await test_session.execute(
                select(func.count()).select_from(AccountChatMembership).where(
                    AccountChatMembership.chat_target_id == chat.id
                )
            )
        ).scalar_one()
        assert total == 1
        purpose = await test_session.scalar(
            select(AccountChatMembership.purpose).where(AccountChatMembership.chat_target_id == chat.id)
        )
        assert purpose == MembershipPurpose.WATCHER.value

    async def test_actor_join_is_prioritized(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        watcher = await _add_account(test_session, custom_automation, username="watch", phone="+79991001003")
        actor = await _add_account(
            test_session,
            custom_automation,
            username="actor",
            phone="+79991001004",
            account_class=AccountClass.MID.value,
        )
        coverage = await _add_chat(test_session, custom_automation, title="Coverage", invite_link="https://t.me/+coverhash12")
        action_chat = await _add_chat(test_session, custom_automation, title="Action", invite_link="https://t.me/+actionhash1")
        await ensure_memberships_for_chat(
            test_session,
            custom_automation.id,
            coverage,
            account_ids=[watcher.id],
            purpose=MembershipPurpose.WATCHER.value,
        )
        await queue_actor_for_chat(test_session, custom_automation.id, action_chat, actor)
        await test_session.commit()

        picked = await pick_next_pending_membership(test_session, custom_automation.id, ignore_retry_delay=True)
        assert picked is not None
        assert picked.social_account_id == actor.id
        assert picked.chat_target_id == action_chat.id
        assert picked.priority == ACTION_JOIN_PRIORITY

    async def test_per_account_cooldown_skips_same_account(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        account = await _add_account(test_session, custom_automation, username="cool", phone="+79991001005")
        first = await _add_chat(test_session, custom_automation, title="One", invite_link="https://t.me/+onehash1234")
        second = await _add_chat(test_session, custom_automation, title="Two", invite_link="https://t.me/+twohash1234")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, first, account_ids=[account.id]
        )
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, second, account_ids=[account.id]
        )
        membership = await test_session.scalar(
            select(AccountChatMembership).where(AccountChatMembership.chat_target_id == first.id)
        )
        membership.last_join_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await apply_account_join_cooldown(test_session, custom_automation.id, account.id, wait_seconds=180)
        await test_session.commit()

        picked = await pick_next_pending_membership(test_session, custom_automation.id)
        assert picked is None

    async def test_ensure_accounts_ready_queues_pending_action(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        actor = await _add_account(test_session, custom_automation, username="neuro", phone="+79991001006")
        chat = await _add_chat(
            test_session,
            custom_automation,
            title="Channel",
            chat_type="channel",
            invite_link="https://t.me/neurochan",
            join_status=ChatJoinStatus.JOINED.value,
        )
        ready = await ensure_accounts_ready(
            test_session,
            custom_automation.id,
            chat,
            [actor],
            action_type="neurocommenting",
            target_id=f"{chat.id}:15",
            payload={"post_id": 15, "post_text": "hi"},
        )
        await test_session.commit()
        assert ready is False
        assert await has_pending_action(test_session, custom_automation.id, "neurocommenting", f"{chat.id}:15")
        membership = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == actor.id,
            )
        )
        assert membership is not None
        assert membership.purpose == MembershipPurpose.ACTOR.value
        assert membership.priority == ACTION_JOIN_PRIORITY
        pending = await test_session.scalar(select(PendingChatAction))
        assert pending is not None
        assert pending.status == PendingChatActionStatus.PENDING.value

    async def test_enqueue_pending_is_idempotent(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        actor = await _add_account(test_session, custom_automation, username="idem", phone="+79991001007")
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+idemhash123")
        first = await enqueue_pending_action(
            test_session,
            automation_id=custom_automation.id,
            chat_target=chat,
            account=actor,
            action_type="dm",
            target_id="99",
        )
        second = await enqueue_pending_action(
            test_session,
            automation_id=custom_automation.id,
            chat_target=chat,
            account=actor,
            action_type="dm",
            target_id="99",
        )
        await test_session.commit()
        assert first.id == second.id
        count = (
            await test_session.execute(select(func.count()).select_from(PendingChatAction))
        ).scalar_one()
        assert count == 1


async def _mark_joined(
    session: AsyncSession,
    chat: ChatTarget,
    account: SocialAccount,
    *,
    purpose: str = MembershipPurpose.WATCHER.value,
) -> AccountChatMembership:
    membership = await session.scalar(
        select(AccountChatMembership).where(
            AccountChatMembership.chat_target_id == chat.id,
            AccountChatMembership.social_account_id == account.id,
        )
    )
    assert membership is not None
    membership.join_status = ChatJoinStatus.JOINED.value
    membership.purpose = purpose
    membership.joined_at = datetime.now(timezone.utc).replace(tzinfo=None)
    chat.join_status = ChatJoinStatus.JOINED.value
    chat.joined_by_account_id = account.id
    await session.commit()
    await session.refresh(membership)
    return membership


class TestWatcherFailover:
    async def test_chat_ban_is_read_lost_write_forbidden_is_not(self):
        from app.services.custom.telegram_error_handler import is_chat_read_lost

        class UserBannedInChannelError(Exception):
            pass

        class ChatWriteForbiddenError(Exception):
            pass

        from app.services.custom.chat_inspect_service import is_account_restricted_error

        assert is_chat_read_lost(UserBannedInChannelError("banned")) is True
        assert is_chat_read_lost(Exception("USER_BANNED_IN_CHANNEL")) is True
        assert is_chat_read_lost(ChatWriteForbiddenError("no write")) is False
        assert is_account_restricted_error(ChatWriteForbiddenError("no write")) is False

    async def test_banned_watcher_is_replaced(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        watcher = await _add_account(test_session, custom_automation, username="oldw", phone="+79991001011")
        replacement = await _add_account(test_session, custom_automation, username="neww", phone="+79991001012")
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+banwatch12")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[watcher.id]
        )
        await _mark_joined(test_session, chat, watcher)

        await retire_reader_and_replace(test_session, chat, watcher.id, error="USER_BANNED_IN_CHANNEL")
        await test_session.commit()

        old = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == watcher.id,
            )
        )
        assert old.join_status == ChatJoinStatus.BANNED.value
        assert old.purpose == MembershipPurpose.ACTOR.value

        new = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == replacement.id,
            )
        )
        assert new is not None
        assert new.purpose == MembershipPurpose.WATCHER.value
        assert new.join_status == ChatJoinStatus.PENDING.value
        assert new.priority == WATCHER_REPLACE_PRIORITY

        reader = await get_reader_account(test_session, chat)
        assert reader is None or reader.id != watcher.id

        picked = await pick_next_pending_membership(test_session, custom_automation.id, ignore_retry_delay=True)
        assert picked is not None
        assert picked.social_account_id == replacement.id
        assert picked.priority == WATCHER_REPLACE_PRIORITY

    async def test_joined_actor_promoted_when_watcher_banned(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        watcher = await _add_account(test_session, custom_automation, username="wban", phone="+79991001013")
        actor = await _add_account(
            test_session,
            custom_automation,
            username="aban",
            phone="+79991001014",
            account_class=AccountClass.MID.value,
        )
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+promoteban1")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[watcher.id]
        )
        await queue_actor_for_chat(test_session, custom_automation.id, chat, actor)
        await _mark_joined(test_session, chat, watcher)
        await _mark_joined(test_session, chat, actor, purpose=MembershipPurpose.ACTOR.value)

        await retire_reader_and_replace(test_session, chat, watcher.id, error="kicked")
        await test_session.commit()

        actor_row = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == actor.id,
            )
        )
        assert actor_row.purpose == MembershipPurpose.WATCHER.value
        assert actor_row.join_status == ChatJoinStatus.JOINED.value

        reader = await get_reader_account(test_session, chat)
        assert reader is not None
        assert reader.id == actor.id

        pending_watchers = (
            await test_session.execute(
                select(func.count()).select_from(AccountChatMembership).where(
                    AccountChatMembership.chat_target_id == chat.id,
                    AccountChatMembership.purpose == MembershipPurpose.WATCHER.value,
                    AccountChatMembership.join_status == ChatJoinStatus.PENDING.value,
                )
            )
        ).scalar_one()
        assert pending_watchers == 0

    async def test_queue_actor_does_not_revive_chat_ban(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        account = await _add_account(test_session, custom_automation, username="noban", phone="+79991001015")
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+noreviveban")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[account.id]
        )
        await _mark_joined(test_session, chat, account)
        await retire_reader_and_replace(test_session, chat, account.id, error="banned")
        await test_session.commit()

        queued = await queue_actor_for_chat(test_session, custom_automation.id, chat, account)
        assert queued is None
        row = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == account.id,
            )
        )
        assert row.join_status == ChatJoinStatus.BANNED.value

    async def test_public_channel_stays_readable_after_reader_ban(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        banned = await _add_account(test_session, custom_automation, username="pubban", phone="+79991001016")
        other = await _add_account(test_session, custom_automation, username="pubok", phone="+79991001017")
        chat = await _add_chat(
            test_session,
            custom_automation,
            title="News",
            chat_type="channel",
            invite_link="https://t.me/failovernews",
            join_status=ChatJoinStatus.JOINED.value,
        )
        await retire_reader_and_replace(test_session, chat, banned.id, error="USER_BANNED_IN_CHANNEL")
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.join_status == ChatJoinStatus.JOINED.value
        assert await is_chat_watchable(test_session, chat) is True
        reader = await get_reader_account(test_session, chat)
        assert reader is not None
        assert reader.id == other.id

    async def test_dead_account_watchers_are_replaced(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        dead = await _add_account(test_session, custom_automation, username="deadw", phone="+79991001018")
        alive = await _add_account(test_session, custom_automation, username="alivew", phone="+79991001019")
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+deadwatch1")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[dead.id]
        )
        await _mark_joined(test_session, chat, dead)
        dead.is_active = False
        dead.is_banned = True
        await test_session.commit()

        queued = await replace_watchers_for_dead_account(test_session, dead.id)
        await test_session.commit()
        assert queued == 1
        replacement = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == alive.id,
            )
        )
        assert replacement is not None
        assert replacement.purpose == MembershipPurpose.WATCHER.value
        assert replacement.join_status == ChatJoinStatus.PENDING.value
        old = await test_session.scalar(
            select(AccountChatMembership).where(
                AccountChatMembership.chat_target_id == chat.id,
                AccountChatMembership.social_account_id == dead.id,
            )
        )
        assert old.purpose == MembershipPurpose.ACTOR.value
        assert old.join_status == ChatJoinStatus.ERROR.value

    async def test_stale_joined_group_is_not_listed_without_live_member(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats
        from app.services.custom.chat_monitoring_service import list_monitor_chats

        await _add_account(test_session, custom_automation, username="stale", phone="+79991001020")
        chat = await _add_chat(
            test_session,
            custom_automation,
            invite_link="https://t.me/+stalejoin12",
            join_status=ChatJoinStatus.JOINED.value,
        )
        watchable = await list_watchable_chats(test_session, custom_automation.id)
        monitor = await list_monitor_chats(test_session, custom_automation.id)
        assert chat.id not in {item.id for item in watchable}
        assert chat.id not in {item.id for item in monitor}

    async def test_public_channel_stays_on_watchable_list(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats

        chat = await _add_chat(
            test_session,
            custom_automation,
            title="News",
            chat_type="channel",
            invite_link="https://t.me/listablenews",
            join_status=ChatJoinStatus.JOINED.value,
        )
        watchable = await list_watchable_chats(test_session, custom_automation.id)
        assert chat.id in {item.id for item in watchable}

    async def test_banned_watcher_drops_group_from_monitor(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_monitoring_service import list_monitor_chats

        watcher = await _add_account(test_session, custom_automation, username="dropw", phone="+79991001021")
        await _add_account(test_session, custom_automation, username="dropn", phone="+79991001022")
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+dropwatch1")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[watcher.id]
        )
        await _mark_joined(test_session, chat, watcher)
        before = await list_monitor_chats(test_session, custom_automation.id)
        assert chat.id in {item.id for item in before}

        await retire_reader_and_replace(test_session, chat, watcher.id, error="kicked")
        await test_session.commit()
        after = await list_monitor_chats(test_session, custom_automation.id)
        assert chat.id not in {item.id for item in after}

    async def test_private_invite_is_not_public_because_of_title(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats

        chat = await _add_chat(
            test_session,
            custom_automation,
            title="News",
            chat_type="channel",
            invite_link="https://t.me/+privatenews12",
        )
        assert is_public_readable(chat) is False
        watchable = await list_watchable_chats(test_session, custom_automation.id)
        assert chat.id not in {item.id for item in watchable}

    async def test_title_username_channel_is_watchable_without_join(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats

        chat = await _add_chat(
            test_session,
            custom_automation,
            title="@titleonlynews",
            chat_type="channel",
            invite_link="",
        )
        assert is_public_readable(chat) is True
        watchable = await list_watchable_chats(test_session, custom_automation.id)
        assert chat.id in {item.id for item in watchable}

    async def test_channel_id_link_is_not_watchable_without_member(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats

        chat = await _add_chat(
            test_session,
            custom_automation,
            title="Private id",
            chat_type="channel",
            invite_link="https://t.me/c/1234567890/1",
        )
        assert is_public_readable(chat) is False
        watchable = await list_watchable_chats(test_session, custom_automation.id)
        assert chat.id not in {item.id for item in watchable}

    async def test_closed_comments_rotate_scan_cursor(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import list_watchable_chats
        from app.services.custom.neurocommenting_service import process_chat_target

        custom_automation.is_neurocommenting_enabled = True
        first = await _add_chat(
            test_session,
            custom_automation,
            title="Closed one",
            chat_type="channel",
            invite_link="https://t.me/closedonechan",
        )
        second = await _add_chat(
            test_session,
            custom_automation,
            title="Closed two",
            chat_type="channel",
            invite_link="https://t.me/closedtwochan",
        )
        first.comments_open = False
        second.comments_open = False
        await test_session.commit()

        listed = await list_watchable_chats(test_session, custom_automation.id, limit=1)
        assert listed[0].id == first.id
        result = await process_chat_target(test_session, custom_automation.id, listed[0])
        assert result["reason"] == "comments_closed"
        await test_session.refresh(first)
        assert first.last_scanned_at is not None

        listed_next = await list_watchable_chats(test_session, custom_automation.id, limit=1)
        assert listed_next[0].id == second.id

    async def test_chat_ban_fails_pending_action(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_membership_service import mark_membership_chat_banned

        account = await _add_account(
            test_session, custom_automation, username="pendban", phone="+79991001023"
        )
        chat = await _add_chat(test_session, custom_automation, invite_link="https://t.me/+pendbanhash1")
        await ensure_memberships_for_chat(
            test_session, custom_automation.id, chat, account_ids=[account.id]
        )
        await _mark_joined(test_session, chat, account)
        pending = await enqueue_pending_action(
            test_session,
            automation_id=custom_automation.id,
            chat_target=chat,
            account=account,
            action_type="neurocommenting",
            target_id=f"{chat.id}:77",
            payload={"post_id": 77},
        )
        assert pending is not None
        assert pending.status == PendingChatActionStatus.PENDING.value

        await mark_membership_chat_banned(test_session, chat, account.id, error="kicked")
        await test_session.commit()
        await test_session.refresh(pending)
        assert pending.status == PendingChatActionStatus.FAILED.value
        assert "kicked" in (pending.last_error or "")

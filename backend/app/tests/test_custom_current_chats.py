"""Current-chat toggle: extras are added, assigned chats stay with their owner."""
from types import SimpleNamespace

from app.services.custom.task_targets import WorkPool, extra_chat_owners


def test_extra_chats_skip_the_assigned_pool_and_pick_one_member():
    owners = extra_chat_owners(
        [7, 3],
        {7: {10, 11}, 3: {11, 12}},
        assigned={10},
    )
    assert owners == {11: 3, 12: 3}


def test_work_pool_lets_the_member_use_a_current_chat_only():
    pool = WorkPool(assigned={10}, extra_owner={11: 7})
    auto = SimpleNamespace(module_settings={"_unique_assign": {"neurocommenting": {"3": [10]}}})
    assert pool.allows(auto, "neurocommenting", 3, 10) is True
    assert pool.allows(auto, "neurocommenting", 7, 10) is False
    assert pool.allows(auto, "neurocommenting", 7, 11) is True
    assert pool.allows(auto, "neurocommenting", 3, 11) is False
    assert pool.chat_ids == {10, 11}

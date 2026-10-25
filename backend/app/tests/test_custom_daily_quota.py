"""Daily task quota stays inside the configured range and does not drift mid-day."""
from app.services.custom.daily_quota import quota_bounds, rolled_daily_actions
from app.services.custom.masslooking_service import like_roll_hits, story_peer_keys


def test_missing_minimum_keeps_the_existing_maximum():
    assert quota_bounds({"max_per_account": 15}, default_max=15) == (15, 15)
    assert quota_bounds({}, default_max=15) == (15, 15)


def test_minimum_cannot_exceed_maximum_and_zero_maximum_is_uncapped():
    assert quota_bounds({"min_per_account": 40, "max_per_account": 10}, default_max=15) == (10, 10)
    assert quota_bounds({"min_per_account": 0, "max_per_account": 8}, default_max=15) == (0, 8)
    assert quota_bounds({"max_per_account": 0}, default_max=0) is None


def test_roll_is_stable_for_the_day_and_stays_inside_the_range():
    first = rolled_daily_actions(17, "neurocommenting", 3, 10)
    again = rolled_daily_actions(17, "neurocommenting", 3, 10)
    other = rolled_daily_actions(18, "neurocommenting", 3, 10)
    assert first == again
    assert 3 <= first <= 10
    assert 3 <= other <= 10
    assert rolled_daily_actions(17, "masslooking", 4, 4) == 4


def test_looking_peers_are_users_and_split_keys_stay_unique():
    keys = story_peer_keys(["@anna", "https://t.me/bobmarket"], ["@anna", "4821"])
    assert keys == ["@anna", "@bobmarket", "id:4821"]
    assert like_roll_hits(0, 0.0) is False
    assert like_roll_hits(100, 0.99) is True
    assert like_roll_hits(30, 0.29) is True
    assert like_roll_hits(30, 0.30) is False

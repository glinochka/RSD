"""Unit tests for referral commission math and code normalization."""

import pytest

from app.services.referral import (
    MAX_PARTNER_PROMO_DISCOUNT_PERCENT,
    PARTNER_BASE_COMMISSION_PERCENT,
    compute_commission_kopecks,
    compute_partner_commission_percent,
    normalize_referral_code,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  abc12  ", "ABC12"),
        ("ref-code", "REFCODE"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_referral_code(raw, expected):
    assert normalize_referral_code(raw) == expected


@pytest.mark.parametrize(
    "discount,expected_rate",
    [
        (0, 50),
        (10, 40),
        (50, 0),
        (99, 0),
        (-5, 50),
    ],
)
def test_compute_partner_commission_percent(discount, expected_rate):
    assert compute_partner_commission_percent(discount) == expected_rate
    assert compute_partner_commission_percent(discount) <= PARTNER_BASE_COMMISSION_PERCENT


def test_max_partner_promo_discount_cap():
    assert compute_partner_commission_percent(MAX_PARTNER_PROMO_DISCOUNT_PERCENT) == 0


def test_compute_commission_kopecks():
    assert compute_commission_kopecks(gross_kopecks=10_000, commission_percent=50) == 5_000
    assert compute_commission_kopecks(gross_kopecks=10_000, commission_percent=40) == 4_000
    assert compute_commission_kopecks(gross_kopecks=0, commission_percent=50) == 0
    assert compute_commission_kopecks(gross_kopecks=1000, commission_percent=0) == 0


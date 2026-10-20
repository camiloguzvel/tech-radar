import pytest

from radar.domains.loader import load_hubs
from radar.resolve.geo import assign_hub, haversine_km

HUBS = load_hubs().hubs


def test_haversine_known_distance():
    # Ámsterdam – Eindhoven ≈ 110 km en línea recta
    assert haversine_km(52.3676, 4.9041, 51.4416, 5.4697) == pytest.approx(110, abs=6)


def test_tu_eindhoven_in_eindhoven():
    assert assign_hub(51.4486, 5.4907, "NL", HUBS) == ("eindhoven", "radius")


def test_country_filter_separates_shenzhen_and_hong_kong():
    # HKUST está a <40 km del centro de Shenzhen, pero su país es HK.
    assert assign_hub(22.3364, 114.2655, "HK", HUBS) == ("hong_kong", "country")
    assert assign_hub(22.5960, 113.9970, "CN", HUBS) == ("shenzhen", "radius")


def test_whole_country_hub_without_coordinates():
    assert assign_hub(None, None, "SG", HUBS) == ("singapore", "country")


def test_outside_any_hub():
    assert assign_hub(52.3676, 4.9041, "NL", HUBS) is None  # Ámsterdam
    assert assign_hub(51.4416, 5.4697, None, HUBS) is None


def test_tsukuba_belongs_to_tokyo():
    assert assign_hub(36.1110, 140.1004, "JP", HUBS) == ("tokyo", "radius")

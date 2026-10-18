"""Multi-monitor discovery and region-resolution tests."""

from handgesturemouse.core.screens import (
    DisplayRegion,
    Monitor,
    list_monitors,
    resolve_region,
    virtual_span,
)


def _monitors():
    return [
        Monitor(index=0, x=0, y=0, width=1920, height=1080, primary=True),
        Monitor(index=1, x=1920, y=0, width=1280, height=1024, primary=False),
    ]


def test_primary_region():
    region = resolve_region("primary", _monitors())
    assert (region.x, region.y, region.width, region.height) == (0, 0, 1920, 1080)


def test_secondary_region():
    region = resolve_region("secondary", _monitors())
    assert (region.x, region.y, region.width, region.height) == (1920, 0, 1280, 1024)


def test_span_covers_all_monitors():
    region = resolve_region("span", _monitors())
    assert (region.x, region.y, region.width, region.height) == (0, 0, 3200, 1080)


def test_virtual_span_uses_bounding_box():
    monitors = [
        Monitor(index=0, x=-1920, y=0, width=1920, height=1080, primary=False),
        Monitor(index=1, x=0, y=0, width=2560, height=1440, primary=True),
    ]
    region = virtual_span(monitors)
    assert (region.x, region.y, region.width, region.height) == (-1920, 0, 4480, 1440)


def test_index_selection_and_invalid_fallback():
    monitors = _monitors()
    region = resolve_region("1", monitors)
    assert region.x == 1920
    # Unknown selection falls back to the primary monitor.
    fallback = resolve_region("nonsense", monitors)
    assert (fallback.x, fallback.width) == (0, 1920)


def test_empty_monitor_list_is_safe():
    region = resolve_region("primary", [])
    assert region == DisplayRegion(0, 0, 0, 0)


def test_region_contains():
    region = DisplayRegion(100, 50, 200, 100)
    assert region.contains(150, 100) is True
    assert region.contains(300, 100) is False


def test_monitor_label_and_list_monitors():
    assert "Primary" in Monitor(0, 0, 0, 1920, 1080, True).label
    monitors = list_monitors()
    assert len(monitors) >= 1
    assert any(m.primary for m in monitors)

from datetime import datetime

import pytest

from webapp import create_app
from webapp.config import TestConfig
from webapp.extensions import db
from webapp.models import FitFile


@pytest.fixture
def client(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_DIR = tmp_path / "uploads"
        TILE_CACHE_DIR = tmp_path / "tiles"

    app = create_app(Cfg)
    with app.app_context():
        # Three rides with distinct distance / intensity / date. Metrics are
        # pre-set so the dashboard never needs to parse a real file.
        db.session.add_all([
            FitFile(original_filename="A.fit", stored_name="a.fit", size_bytes=1,
                    point_count=1, distance_m=5000, intensity=100,
                    started_at=datetime(2026, 1, 1)),
            FitFile(original_filename="B.fit", stored_name="b.fit", size_bytes=1,
                    point_count=1, distance_m=20000, intensity=10,
                    started_at=datetime(2026, 3, 1)),
            FitFile(original_filename="C.fit", stored_name="c.fit", size_bytes=1,
                    point_count=1, distance_m=10000, intensity=50,
                    started_at=datetime(2026, 2, 1)),
        ])
        db.session.commit()
    yield app.test_client()
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _order(client, sort):
    html = client.get(f"/?sort={sort}").get_data(as_text=True)
    # Return the ride names in the order they appear in the page.
    positions = sorted(("ABC"[i], html.index(f"{name}.fit"))
                       for i, name in enumerate("ABC"))
    return [name for name, _ in sorted(positions, key=lambda p: p[1])]


@pytest.mark.parametrize("sort,expected", [
    ("short_long", ["A", "C", "B"]),     # 5k, 10k, 20k
    ("long_short", ["B", "C", "A"]),
    ("most_intense", ["A", "C", "B"]),   # 100, 50, 10
    ("most_chill", ["B", "C", "A"]),
    ("latest", ["B", "C", "A"]),         # Mar, Feb, Jan
    ("earliest", ["A", "C", "B"]),
])
def test_sort_orderings(client, sort, expected):
    assert _order(client, sort) == expected


def test_default_sort_is_latest(client):
    assert _order(client, "bogus-falls-back") == ["B", "C", "A"]


def test_sort_links_render_with_active(client):
    html = client.get("/?sort=most_intense").get_data(as_text=True)
    assert "Most intense" in html and "Most chill" in html
    assert 'sort-link active' in html  # the active option is highlighted

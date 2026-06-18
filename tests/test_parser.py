import fit_route_map.parser as parser_mod
from fit_route_map.parser import SEMICIRCLE_TO_DEGREES, parse_fit


class _FakeRecord:
    def __init__(self, values):
        self._values = values

    def get_values(self):
        return self._values


class _FakeFitFile:
    """Stand-in for fitparse.FitFile that yields canned record messages."""

    records = []

    def __init__(self, path):
        self.path = path

    def get_messages(self, name):
        assert name == "record"
        return [_FakeRecord(v) for v in self.records]


def test_semicircle_conversion(monkeypatch):
    # 2**30 semicircles == 90 degrees; 0 semicircles == 0 degrees.
    _FakeFitFile.records = [
        {"position_lat": 2 ** 30, "position_long": 0, "timestamp": 1, "altitude": 12.0},
    ]
    monkeypatch.setattr(parser_mod, "FitFile", _FakeFitFile)

    points = parse_fit("ignored.fit")

    assert len(points) == 1
    assert points[0].lat == 90.0
    assert points[0].lon == 0.0
    assert points[0].altitude == 12.0
    assert points[0].timestamp == 1


def test_records_without_position_are_skipped(monkeypatch):
    _FakeFitFile.records = [
        {"position_lat": None, "position_long": None},  # no GPS lock yet
        {"position_lat": 0, "position_long": 2 ** 30},  # lon = 90
        {"position_lat": 10},  # missing longitude
    ]
    monkeypatch.setattr(parser_mod, "FitFile", _FakeFitFile)

    points = parse_fit("ignored.fit")

    assert len(points) == 1
    assert points[0].lon == 90.0


def test_enhanced_altitude_preferred(monkeypatch):
    _FakeFitFile.records = [
        {
            "position_lat": 0,
            "position_long": 0,
            "enhanced_altitude": 99.0,
            "altitude": 1.0,
        },
    ]
    monkeypatch.setattr(parser_mod, "FitFile", _FakeFitFile)

    points = parse_fit("ignored.fit")
    assert points[0].altitude == 99.0


def test_conversion_constant():
    assert SEMICIRCLE_TO_DEGREES * (2 ** 31) == 180.0

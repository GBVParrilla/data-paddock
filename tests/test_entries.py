from types import SimpleNamespace

from f1tracker.ingest.entries import build_entries


def _resolver():
    drivers = {}

    def get(key, number):
        if key not in drivers:
            drivers[key] = SimpleNamespace(id=len(drivers) + 1, number=number)
        return drivers[key]

    return drivers, (lambda r: get(r["Driver"]["driverId"], int(r["number"]))), (lambda d: get(d.get("name_acronym"), int(d["driver_number"])))


def test_a_promoted_driver_scores_for_his_new_team():
    """REVIEW #4: Lawson raced for Red Bull at Zandvoort; the entry list says so, whatever his usual seat."""
    drivers, by_jolpica, by_number = _resolver()
    jolpica = [
        {"Driver": {"driverId": "LAW"}, "number": "30", "Constructor": {"constructorId": "red_bull"}},
        {"Driver": {"driverId": "TSU"}, "number": "22", "Constructor": {"constructorId": "rb"}},
    ]
    openf1 = {
        "FP1": [{"driver_number": 30, "name_acronym": "LAW", "team_name": "Red Bull Racing"}, {"driver_number": 34, "name_acronym": "CRA", "team_name": "Racing Bulls"}],
        "R": [{"driver_number": 30, "name_acronym": "LAW", "team_name": "Red Bull Racing"}, {"driver_number": 22, "name_acronym": "TSU", "team_name": "Racing Bulls"}],
    }
    rows = {r["driver_id"]: r for r in build_entries(jolpica, openf1, driver_for_jolpica=by_jolpica, driver_for_number=by_number)}
    law, tsu, cra = drivers["LAW"].id, drivers["TSU"].id, drivers["CRA"].id
    assert rows[law]["team"] == "Red Bull Racing" and rows[law]["constructor_id"] == "red_bull" and not rows[law]["practice_only"]
    assert rows[tsu]["team"] == "Racing Bulls" and rows[tsu]["constructor_id"] == "rb"
    assert rows[cra]["practice_only"] and rows[cra]["constructor_id"] == "rb"


def test_display_names_fall_back_without_openf1():
    drivers, by_jolpica, by_number = _resolver()
    rows = build_entries([{"Driver": {"driverId": "HAD"}, "number": "6", "Constructor": {"constructorId": "red_bull"}}], {}, driver_for_jolpica=by_jolpica, driver_for_number=by_number)
    assert rows[0]["team"] == "Red Bull Racing"

from demo_fleet import DemoFleet


def test_nationwide_demo_fleet_spans_india():
    fleet = DemoFleet((19.0760, 72.8777), 20, nationwide=True)
    drivers = fleet.drivers()

    assert len(drivers) == 20
    assert max(driver["lat"] for driver in drivers) - min(
        driver["lat"] for driver in drivers
    ) > 20
    assert max(driver["lon"] for driver in drivers) - min(
        driver["lon"] for driver in drivers
    ) > 20
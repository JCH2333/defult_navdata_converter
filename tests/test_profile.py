from fenix_default_navdata.profile import DEFAULT_CYCLE, validate_cycle


def test_default_cycle_is_2608_r1():
    validate_cycle(DEFAULT_CYCLE)
    assert DEFAULT_CYCLE.begin == "20260806"

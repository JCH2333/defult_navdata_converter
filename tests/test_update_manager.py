from fenix_default_navdata.update_manager import _version


def test_semantic_version_order():
    assert _version("v0.2.0") > _version("0.1.9")

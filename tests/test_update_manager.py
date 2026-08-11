from fenix_default_navdata.update_manager import API_URL, REPOSITORY, _version


def test_semantic_version_order():
    assert _version("v0.2.0") > _version("0.1.9")


def test_update_repository_matches_public_github_repo():
    assert REPOSITORY == "JCH2333/defult_navdata_converter"
    assert API_URL == (
        "https://api.github.com/repos/"
        "JCH2333/defult_navdata_converter/releases"
    )

from fenix_default_navdata.iap_ocr_roles import extract_iap_ocr_role_evidence


def test_extract_iap_ocr_role_evidence_requires_explicit_role_and_close_position() -> None:
    evidence = extract_iap_ocr_role_evidence(
        [(
            1,
            "\n".join((
                "IAF[[10, 10, 30, 20]]",
                "FIX01[[12, 24, 42, 34]]",
                "FAF FIX02[[90, 90, 180, 102]]",
                "FAF/VIP FIX03[[90, 120, 210, 132]]",
                "MAPT[[10, 160, 40, 170]]",
                "FIX04[[300, 160, 340, 170]]",
            )),
        )],
        {"FIX01", "FIX02", "FIX03", "FIX04"},
    )

    assert [item.to_report() for item in evidence] == [
        {
            "page": 1,
            "ident": "FIX01",
            "role": "IAF",
            "relation": "vertical_stack",
        },
        {
            "page": 1,
            "ident": "FIX02",
            "role": "FAF",
            "relation": "same_ocr_item",
        },
    ]


def test_extract_iap_ocr_role_evidence_keeps_one_strongest_pair_per_page() -> None:
    evidence = extract_iap_ocr_role_evidence(
        [(
            1,
            "\n".join((
                "IF[[10, 10, 30, 20]]",
                "FIX01[[32, 10, 70, 20]]",
                "IF[[100, 100, 120, 110]]",
                "FIX01[[102, 114, 140, 124]]",
            )),
        )],
        {"FIX01"},
    )

    assert [item.to_report() for item in evidence] == [{
        "page": 1,
        "ident": "FIX01",
        "role": "IF",
        "relation": "same_row",
    }]

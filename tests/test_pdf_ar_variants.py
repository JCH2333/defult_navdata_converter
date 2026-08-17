from fenix_default_navdata.pdf_charts import extract_terminal_leg_evidence


def test_database_ar_approach_variants_keep_single_variant_labels_and_shared_sections():
    text = """
    RWY10 AR Z \u8fdb\u8fd1
    IF TL102 RNP1
    RWY10 AR Y \u8fdb\u8fd1
    IF TL102 RNP1
    RWY10 AR Z Y \u8fdb\u8fd1\u8fc7\u6e21 TL106
    IF TL106 RNP1
    RWY10 AR X \u8fdb\u8fd1
    IF TL552 RNP1
    """

    legs = extract_terminal_leg_evidence(text)

    assert [
        (leg.procedure_label, leg.procedure_kind, leg.transition, leg.fix_ident)
        for leg in legs
    ] == [
        ("R10-AR-Z", "\u8fdb\u8fd1", "", "TL102"),
        ("R10-AR-Y", "\u8fdb\u8fd1", "", "TL102"),
        ("R10", "\u8fdb\u8fd1\u8fc7\u6e21", "TL106", "TL106"),
        ("R10-AR-X", "\u8fdb\u8fd1", "", "TL552"),
    ]


def test_database_target_family_preserves_rnp_and_ils_transition_ownership():
    text = """
    RWY03 接 RNP 进近
    IF RNPA1 RNP1
    RWY03 接 ILS 进近
    IF ILSA1 RNP1
    """

    legs = extract_terminal_leg_evidence(text)

    assert [
        (
            leg.procedure_label,
            leg.procedure_kind,
            leg.approach_family,
            leg.fix_ident,
        )
        for leg in legs
    ] == [
        ("R03", "\u8fdb\u8fd1\u8fc7\u6e21", "RNP", "RNPA1"),
        ("I03", "\u8fdb\u8fd1\u8fc7\u6e21", "ILS", "ILSA1"),
    ]

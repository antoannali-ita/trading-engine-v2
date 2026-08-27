from trade_committee.input_resolver import split_queries


def test_split_queries_primary_comma():
    assert split_queries("TSM, NVDA, NVO") == ["TSM", "NVDA", "NVO"]


def test_split_queries_accepts_semicolon_and_newline():
    assert split_queries("TSM; NVIDIA\nNovo Nordisk") == ["TSM", "NVIDIA", "Novo Nordisk"]


def test_split_queries_deduplicates_case_insensitively():
    assert split_queries("TSM, tsm, Nvidia") == ["TSM", "Nvidia"]

from eval import headline


def test_committed_chart_matches_committed_table():
    expected = headline.render(headline.read_cells(headline.CELLS))
    assert headline.OUT.read_text() == expected


def test_render_draws_every_cell_with_its_value():
    keys = [(m, c) for m, _ in headline.MODELS for c, _, _ in headline.CONDITIONS]
    cells = {k: (0.1 * (i + 1), 0.1 * i, 0.1 * (i + 1)) for i, k in enumerate(keys)}
    svg = headline.render(cells)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<g><title>") == 9
    assert "90.0%" in svg and "10.0%" in svg
    assert "prefers-color-scheme: dark" in svg

from md_converter.optimizer import optimize, count_tokens, Mode


def test_compact_reduces_tokens():
    # Lots of blank lines — compact should remove them
    md = "\n\n\n".join(["Paragraph " + str(i) + ". " + "word " * 20 for i in range(10)])
    fidelity_out = optimize(md, mode=Mode.FIDELITY)
    compact_out = optimize(md, mode=Mode.COMPACT)
    assert count_tokens(compact_out) <= count_tokens(fidelity_out)


def test_fidelity_preserves_structure():
    md = "# Title\n\nParagraph one.\n\nParagraph two.\n"
    result = optimize(md, mode=Mode.FIDELITY)
    assert "# Title" in result
    assert "Paragraph one" in result
    assert "Paragraph two" in result


def test_compact_removes_redundant_whitespace():
    md = "Word.   Extra   spaces.  \n\n\n\nAnd gaps."
    result = optimize(md, mode=Mode.COMPACT)
    assert "   " not in result


def test_count_tokens_returns_int():
    n = count_tokens("Hello world, this is a test.")
    assert isinstance(n, int)
    assert n > 0


def test_fidelity_collapses_triple_blank_lines():
    md = "A\n\n\n\nB"
    result = optimize(md, mode=Mode.FIDELITY)
    assert "\n\n\n" not in result


def test_compact_removes_blank_between_list_items():
    md = "- Item one\n\n- Item two\n\n- Item three"
    result = optimize(md, mode=Mode.COMPACT)
    # After compact, list items should not have blank lines between them
    assert "- Item one\n- Item two" in result or "- Item two\n- Item three" in result


def test_normalize_line_endings():
    md = "Line one\r\nLine two\r\nLine three"
    result = optimize(md, mode=Mode.FIDELITY)
    assert "\r" not in result

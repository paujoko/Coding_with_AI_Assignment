from wings.domain.text import brief, short_list


def test_a_short_text_is_kept_and_put_on_one_line():
    assert brief("Three files.\n  Open point: dates.") == "Three files. Open point: dates."


def test_a_long_text_is_cut_at_a_sentence_end_within_the_limit():
    text = "First sentence here. Second sentence follows! " + "A third one that runs on and on " * 20 + "."
    assert brief(text, limit=60) == "First sentence here. Second sentence follows!"


def test_one_endless_sentence_is_cut_at_a_word_and_marked():
    out = brief("word " * 200, limit=42)
    assert out.endswith(" ...") and len(out) <= 46 and "  " not in out


def test_a_version_number_is_not_a_sentence_end():
    assert brief("Runs on Python 3.12 only and nothing else matters here at all. More.", limit=30) == "Runs on Python 3.12 only and ..."


def test_short_list_counts_the_rest_and_says_where_it_is():
    lines = [f"line {i}" for i in range(8)]
    assert short_list(lines, "see the report", limit=3) == ["line 0", "line 1", "line 2", "and 5 more (see the report)"]
    assert short_list(lines[:3], "see the report", limit=3) == lines[:3]

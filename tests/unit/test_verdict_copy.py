"""The reason vocabulary is policy — enforce its rules mechanically."""

from __future__ import annotations

from prooflens.engine.verdicts import BANDS, REASON_TEXT, Reason, most_severe

# Internal check names must NEVER leak into rep-facing copy.
_FORBIDDEN = ["laplacian", "dhash", "hamming", "fft", "moire", "bezel", "exif", "plausibility"]


def test_every_reason_has_text():
    assert set(REASON_TEXT) == set(Reason)


def test_reason_strings_are_short_and_plain():
    for reason, text in REASON_TEXT.items():
        assert len(text) <= 90, f"{reason} is {len(text)} chars (> 90): {text!r}"
        assert text[0].isupper(), f"{reason} should read like a sentence: {text!r}"
        low = text.lower()
        for term in _FORBIDDEN:
            assert term not in low, f"{reason} leaks internal term {term!r}: {text!r}"


def test_reason_copy_does_not_depend_on_colour():
    # Meaning must not be carried by a colour word alone (whole words only).
    import re

    for text in REASON_TEXT.values():
        words = set(re.findall(r"[a-z]+", text.lower()))
        for colour in ("red", "amber", "green", "yellow"):
            assert colour not in words, f"copy must not rely on colour: {text!r}"


def test_bands_are_the_three_expected():
    assert set(BANDS) == {"Clear", "Doubtful", "Suspect"}


def test_severity_precedence():
    # Fraud outranks quality outranks clear.
    assert most_severe([Reason.TOO_BLURRED, Reason.RECYCLED]) is Reason.RECYCLED
    assert most_severe([Reason.NO_CONTENT_ANALYSIS, Reason.TOO_BLURRED]) is Reason.TOO_BLURRED
    assert most_severe([]) is Reason.CLEAR


def test_every_reason_has_short_label():
    from prooflens.engine.verdicts import REASON_SHORT_LABEL, Reason
    assert set(REASON_SHORT_LABEL) == set(Reason)
    for reason, label in REASON_SHORT_LABEL.items():
        assert 0 < len(label) <= 32, f"{reason}: {label!r}"
        assert label[0].isupper(), f"{reason} short label should be title-ish: {label!r}"


def test_known_short_labels_match_spec():
    from prooflens.engine.verdicts import REASON_SHORT_LABEL, Reason
    assert REASON_SHORT_LABEL[Reason.RECYCLED] == "Recycled image"
    assert REASON_SHORT_LABEL[Reason.SCREEN_RECAPTURE] == "Photo of a screen"
    assert REASON_SHORT_LABEL[Reason.DESIGNED_GRAPHIC] == "Designed graphic"
    assert REASON_SHORT_LABEL[Reason.NO_PEOPLE_OR_IRRELEVANT] == "No people in scene"
    assert REASON_SHORT_LABEL[Reason.TOO_BLURRED] == "Too blurred"
    assert REASON_SHORT_LABEL[Reason.NO_CONTENT_ANALYSIS] == "Scored without content check"
    assert REASON_SHORT_LABEL[Reason.CLEAR] == "Clear"

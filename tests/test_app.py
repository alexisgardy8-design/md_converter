"""Frontend tests for app.py using Streamlit's AppTest framework."""
import pytest

try:
    from streamlit.testing.v1 import AppTest
    _STREAMLIT_TESTING = True
except ImportError:
    _STREAMLIT_TESTING = False


@pytest.fixture
def app():
    if not _STREAMLIT_TESTING:
        pytest.skip("streamlit.testing.v1 not available (streamlit < 1.18)")
    at = AppTest.from_file("app.py", default_timeout=10)
    at.run()
    return at


def test_app_renders_without_error(app):
    """App must start without exceptions."""
    assert not app.exception


def test_slider_present_with_correct_range(app):
    """A slider for cards-per-PDF with range 5–50 must exist."""
    sliders = app.slider
    keys = [s.key for s in sliders]
    assert "_tc_slider" in keys, f"Expected '_tc_slider' in {keys}"
    tc_slider = next(s for s in sliders if s.key == "_tc_slider")
    assert tc_slider.min == 5
    assert tc_slider.max == 50


def test_number_input_present_with_correct_range(app):
    """A number input for cards-per-PDF with range 5–50 must exist."""
    inputs = app.number_input
    keys = [i.key for i in inputs]
    assert "_tc_input" in keys, f"Expected '_tc_input' in {keys}"
    tc_input = next(i for i in inputs if i.key == "_tc_input")
    assert tc_input.min == 5
    assert tc_input.max == 50


def test_slider_and_input_share_initial_value(app):
    """Slider and number input must start with the same value."""
    tc_slider = next(s for s in app.slider if s.key == "_tc_slider")
    tc_input = next(i for i in app.number_input if i.key == "_tc_input")
    assert tc_slider.value == tc_input.value


def test_slider_updates_state(app):
    """Moving the slider must update session state 'total_cards'."""
    tc_slider = next(s for s in app.slider if s.key == "_tc_slider")
    tc_slider.set_value(35).run()
    assert app.session_state["total_cards"] == 35


def test_number_input_updates_state(app):
    """Editing the number input must update session state 'total_cards'."""
    tc_input = next(i for i in app.number_input if i.key == "_tc_input")
    tc_input.set_value(42).run()
    assert app.session_state["total_cards"] == 42


def test_help_text_present(app):
    """Help text 'Nombre total de cartes générées pour chaque PDF' must be visible."""
    all_text = " ".join(c.value for c in app.caption)
    assert "Nombre total de cartes" in all_text or "chaque PDF" in all_text

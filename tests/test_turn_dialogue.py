"""이전 턴 대화 블록 포맷."""

from app.domain.langgraph.utils.turn_dialogue import format_previous_turn_dialogue


def test_format_previous_turn_dialogue_empty():
    out = format_previous_turn_dialogue([])
    assert "첫 번째 턴" in out


def test_format_previous_turn_dialogue_includes_pairs():
    out = format_previous_turn_dialogue([(1, "USER 한 줄", "AI 로드맵")])
    assert "[이전 턴 1] USER" in out
    assert "USER 한 줄" in out
    assert "AI 로드맵" in out
    assert "해석" in out

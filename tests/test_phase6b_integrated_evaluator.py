"""
Phase 6B: Integrated Evaluator 테스트

[테스트 범위]
1. TurnAnalysis 모델 생성 테스트
2. Spec Extractor 확장 기능 테스트
3. Integrated Evaluator 점수 계산 테스트
4. 전체 플로우 통합 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# ===== 테스트 대상 모듈 임포트 =====
from app.domain.langgraph.states import (
    TurnAnalysis,
    SessionAnalysis,
    IntegratedEvaluationResult,
    MissingSpecDetail,
)
from app.domain.langgraph.nodes.eval.spec_extractor import (
    calculate_clarity_score,
    has_structure,
    has_examples,
    has_specific_values,
    references_previous_turn,
    generate_turn_summary,
    create_turn_analysis,
)
from app.domain.langgraph.nodes.eval.n5_integrated_evaluator import (
    calculate_expression_score,
    calculate_first_prompt_score,
    calculate_follow_up_score,
    calculate_efficiency_score,
    generate_analysis_text,
    generate_suggestions,
    WEIGHTS,
)


# ===== TurnAnalysis 모델 테스트 =====

class TestTurnAnalysisModel:
    """TurnAnalysis Pydantic 모델 테스트"""
    
    def test_turn_analysis_creation(self):
        """기본 TurnAnalysis 생성 테스트"""
        analysis = TurnAnalysis(
            turn=1,
            is_first_prompt=True,
            spec_completeness=75.0,
            specified_specs=["DP 상태 정의", "점화식"],
            missing_specs=[
                MissingSpecDetail(
                    category="기저조건",
                    importance="HIGH",
                    related_component="BASE_CASE"
                )
            ],
            ambiguous_specs=[],
            clarity_score=60.0,
            has_structure=True,
            has_examples=False,
            has_specific_values=True,
            spec_recovery_count=0,
            references_previous=False,
            recovered_specs=[],
            summary="DP 상태 정의와 점화식 명시, 기저조건 누락"
        )
        
        assert analysis.turn == 1
        assert analysis.is_first_prompt == True
        assert analysis.spec_completeness == 75.0
        assert len(analysis.specified_specs) == 2
        assert len(analysis.missing_specs) == 1
        assert analysis.missing_specs[0].category == "기저조건"
    
    def test_turn_analysis_expression_score(self):
        """표현 품질 점수 계산 테스트"""
        # 모든 지표가 좋은 경우
        analysis = TurnAnalysis(
            turn=1,
            is_first_prompt=True,
            spec_completeness=80.0,
            clarity_score=70.0,
            has_structure=True,
            has_examples=True,
            has_specific_values=True,
            summary="테스트"
        )
        
        # expression_score = clarity * 0.5 + structure(30) + examples(35) + values(35)
        expected = min(100.0, 70.0 * 0.5 + 30 + 35 + 35)  # 135 -> 100
        assert analysis.expression_score == 100.0
    
    def test_missing_spec_detail(self):
        """MissingSpecDetail 모델 테스트"""
        detail = MissingSpecDetail(
            category="비트마스킹",
            importance="HIGH",
            related_component="BIT_OPERATION"
        )
        
        assert detail.category == "비트마스킹"
        assert detail.importance == "HIGH"
        assert detail.related_component == "BIT_OPERATION"


# ===== Spec Extractor 확장 기능 테스트 =====

class TestSpecExtractorExtensions:
    """Spec Extractor 확장 함수 테스트"""
    
    def test_calculate_clarity_score_high(self):
        """명확한 프롬프트의 명확성 점수"""
        prompt = "DP를 사용해서 점화식을 구현하고 싶어요. 시간복잡도는 O(N^2)로 해주세요."
        score = calculate_clarity_score(prompt)
        
        # DP(5) + 점화식(10) + 시간복잡도(10) + 기본(30) + 길이 보너스(10)
        assert score >= 50
    
    def test_calculate_clarity_score_low(self):
        """모호한 프롬프트의 명확성 점수"""
        prompt = "그냥 대충 해줘"
        score = calculate_clarity_score(prompt)
        
        # 기본(30) - 그냥(-10) - 대충(-10) = 10
        assert score <= 30
    
    def test_has_structure_with_markdown(self):
        """마크다운 구조 감지"""
        prompt = """
        # 요구사항
        1. DP 사용
        2. 점화식 구현
        """
        assert has_structure(prompt) == True
    
    def test_has_structure_with_xml(self):
        """XML 태그 구조 감지"""
        prompt = "<requirements>DP 사용</requirements>"
        assert has_structure(prompt) == True
    
    def test_has_structure_with_list(self):
        """번호 리스트 구조 감지"""
        prompt = """
        1. DP 사용
        2. 점화식 구현
        """
        assert has_structure(prompt) == True
    
    def test_has_structure_plain_text(self):
        """구조 없는 평문"""
        prompt = "DP를 사용해서 점화식을 구현해주세요"
        assert has_structure(prompt) == False
    
    def test_has_examples_with_io(self):
        """입출력 예시 감지"""
        prompt = "입력: 5, 출력: 10"
        assert has_examples(prompt) == True
    
    def test_has_examples_with_edge_case(self):
        """엣지 케이스 언급 감지"""
        prompt = "엣지 케이스로 빈 배열도 처리해주세요"
        assert has_examples(prompt) == True
    
    def test_has_examples_none(self):
        """예시 없음"""
        prompt = "DP를 사용해주세요"
        assert has_examples(prompt) == False
    
    def test_has_specific_values_with_constraint(self):
        """제약 조건 감지"""
        prompt = "N <= 1000 인 경우를 처리해주세요"
        assert has_specific_values(prompt) == True
    
    def test_has_specific_values_with_complexity(self):
        """시간복잡도 감지"""
        prompt = "O(N^2)로 구현해주세요"
        assert has_specific_values(prompt) == True
    
    def test_has_specific_values_none(self):
        """구체적 값 없음"""
        prompt = "DP를 사용해주세요"
        assert has_specific_values(prompt) == False
    
    def test_references_previous_turn_yes(self):
        """이전 턴 참조 감지"""
        prompt = "아까 말씀하신 방법에서 기저조건을 추가해주세요"
        assert references_previous_turn(prompt) == True
    
    def test_references_previous_turn_no(self):
        """이전 턴 참조 없음"""
        prompt = "DP를 사용해주세요"
        assert references_previous_turn(prompt) == False
    
    def test_generate_turn_summary(self):
        """턴 요약 생성"""
        spec_result = {
            "specified_requirements": ["DP 상태 정의", "점화식"],
            "missing_requirements": [
                {"category": "기저조건", "importance": "HIGH"},
                {"category": "메모이제이션", "importance": "MEDIUM"},
            ],
            "prompt_quality_score": 65.0,
        }
        
        summary = generate_turn_summary("테스트 프롬프트", spec_result)
        
        assert "[양호]" in summary
        assert "명시:" in summary
        assert "기저조건" in summary


# ===== Integrated Evaluator 점수 계산 테스트 =====

class TestIntegratedEvaluatorScoring:
    """Integrated Evaluator 점수 계산 테스트"""
    
    def test_calculate_expression_score(self):
        """표현 품질 점수 계산"""
        turn_analysis = {
            "clarity_score": 60.0,
            "has_structure": True,
            "has_examples": True,
            "has_specific_values": False,
        }
        
        # 60 * 0.5 + 20 + 20 + 0 = 70
        score = calculate_expression_score(turn_analysis)
        assert score == 70.0
    
    def test_calculate_first_prompt_score(self):
        """첫 프롬프트 점수 계산"""
        turn_analysis = {
            "spec_completeness": 80.0,
            "clarity_score": 70.0,
            "has_structure": True,
            "has_examples": True,
            "has_specific_values": True,
            "specified_specs": ["DP"],
            "missing_specs": [],
        }
        
        result = calculate_first_prompt_score(turn_analysis)
        
        assert "score" in result
        assert "spec_completeness" in result
        assert "expression_quality" in result
        assert result["spec_completeness"] == 80.0
        assert 0 <= result["score"] <= 100
    
    def test_calculate_follow_up_score_single_turn(self):
        """1턴 완료 시 후속 턴 점수"""
        turn_analyses = [
            {"turn": 1, "is_first_prompt": True, "missing_specs": []}
        ]
        
        result = calculate_follow_up_score(turn_analyses)
        
        # 후속 턴 없으면 만점
        assert result["score"] == 100.0
    
    def test_calculate_follow_up_score_with_recovery(self):
        """Spec 회복 시 후속 턴 점수"""
        turn_analyses = [
            {
                "turn": 1,
                "is_first_prompt": True,
                "missing_specs": [
                    {"category": "기저조건", "importance": "HIGH"}
                ],
            },
            {
                "turn": 2,
                "is_first_prompt": False,
                "references_previous": True,
                "spec_recovery_count": 1,
            },
        ]
        
        result = calculate_follow_up_score(turn_analyses)
        
        assert result["details"]["follow_up_turns"] == 1
        assert result["details"]["total_recovered_specs"] == 1
        assert result["spec_recovery"] == 100.0  # 1/1 = 100%
    
    def test_calculate_efficiency_score_one_turn(self):
        """1턴 완료 효율성 점수"""
        turn_analyses = [{"turn": 1}]
        
        result = calculate_efficiency_score(turn_analyses)
        
        assert result["turn_efficiency"] == 100  # 1턴 = 만점
        assert result["recovery_speed"] == 100.0
    
    def test_calculate_efficiency_score_five_turns(self):
        """5턴 소요 효율성 점수"""
        turn_analyses = [
            {"turn": i, "missing_specs": [{"category": "test"}] if i == 1 else [], "spec_recovery_count": 0}
            for i in range(1, 6)
        ]
        
        result = calculate_efficiency_score(turn_analyses)
        
        assert result["turn_efficiency"] == 50  # 5턴 = 50점
        assert result["details"]["total_turns"] == 5
    
    def test_weights_sum(self):
        """가중치 합계 검증"""
        total = (
            WEIGHTS["first_prompt"]["total"] +
            WEIGHTS["follow_up"]["total"] +
            WEIGHTS["efficiency"]["total"]
        )
        
        assert total == 1.0
    
    def test_generate_analysis_text(self):
        """분석 텍스트 생성"""
        first_prompt_result = {
            "score": 80.0,
            "spec_completeness": 85.0,
            "expression_quality": 75.0,
        }
        follow_up_result = {
            "score": 90.0,
            "spec_recovery": 100.0,
            "details": {"follow_up_turns": 1},
        }
        efficiency_result = {
            "score": 90.0,
            "details": {"total_turns": 2},
        }
        
        analysis = generate_analysis_text(
            first_prompt_result,
            follow_up_result,
            efficiency_result,
            85.0,
        )
        
        assert "85.0점" in analysis
        assert "Spec 완전성: 85%" in analysis
    
    def test_generate_suggestions(self):
        """개선 제안 생성"""
        first_prompt_result = {
            "score": 50.0,
            "details": {
                "missing_specs": [{"category": "기저조건", "importance": "HIGH"}],
                "has_structure": False,
                "has_examples": False,
                "has_specific_values": False,
            },
        }
        follow_up_result = {
            "context_quality": 40.0,
        }
        
        suggestions = generate_suggestions(first_prompt_result, follow_up_result)
        
        assert len(suggestions) > 0
        assert any("기저조건" in s for s in suggestions)


# ===== 통합 테스트 =====

class TestIntegratedEvaluatorIntegration:
    """통합 평가 전체 플로우 테스트"""
    
    def test_create_turn_analysis_first_turn(self):
        """첫 턴 TurnAnalysis 생성"""
        state = {
            "current_turn": 1,
            "spec_result": None,
        }
        spec_result = {
            "specified_requirements": ["DP 상태 정의"],
            "missing_requirements": [
                {"category": "기저조건", "importance": "HIGH", "related_component": "BASE_CASE"}
            ],
            "ambiguous_requirements": [],
            "prompt_quality_score": 65.0,
        }
        user_prompt = "DP를 사용해서 TSP를 풀고 싶어요. O(N^2 * 2^N) 시간복잡도로요."
        
        turn_analysis = create_turn_analysis(state, spec_result, user_prompt)
        
        assert turn_analysis["turn"] == 1
        assert turn_analysis["is_first_prompt"] == True
        assert turn_analysis["spec_completeness"] == 65.0
        assert turn_analysis["spec_recovery_count"] == 0
        assert turn_analysis["has_specific_values"] == True  # O(N^2 * 2^N) 포함
    
    def test_full_evaluation_flow(self):
        """전체 평가 플로우 테스트"""
        # 턴 분석 데이터 준비
        turn_analyses = [
            {
                "turn": 1,
                "is_first_prompt": True,
                "spec_completeness": 60.0,
                "clarity_score": 50.0,
                "has_structure": False,
                "has_examples": False,
                "has_specific_values": True,
                "specified_specs": ["DP"],
                "missing_specs": [
                    {"category": "기저조건", "importance": "HIGH"},
                    {"category": "점화식", "importance": "HIGH"},
                ],
                "spec_recovery_count": 0,
                "references_previous": False,
            },
            {
                "turn": 2,
                "is_first_prompt": False,
                "spec_completeness": 80.0,
                "clarity_score": 70.0,
                "has_structure": True,
                "has_examples": True,
                "has_specific_values": True,
                "specified_specs": ["DP", "기저조건"],
                "missing_specs": [
                    {"category": "점화식", "importance": "HIGH"},
                ],
                "spec_recovery_count": 1,
                "references_previous": True,
            },
        ]
        
        # 각 구성 요소 점수 계산
        first_prompt = calculate_first_prompt_score(turn_analyses[0])
        follow_up = calculate_follow_up_score(turn_analyses)
        efficiency = calculate_efficiency_score(turn_analyses)
        
        # 통합 점수 계산
        integrated_score = (
            first_prompt["score"] * WEIGHTS["first_prompt"]["total"] +
            follow_up["score"] * WEIGHTS["follow_up"]["total"] +
            efficiency["score"] * WEIGHTS["efficiency"]["total"]
        )
        
        # 검증
        assert 0 <= integrated_score <= 100
        assert first_prompt["spec_completeness"] == 60.0
        assert follow_up["details"]["total_recovered_specs"] == 1
        assert efficiency["details"]["total_turns"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

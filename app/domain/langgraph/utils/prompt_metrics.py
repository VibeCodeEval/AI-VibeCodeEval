"""
프롬프트 품질 측정을 위한 정량적 메트릭 유틸리티
LLM 평가와 함께 사용하여 평가의 객관성과 일관성 향상
"""
import re
from typing import Dict, Any, List, Optional
from collections import Counter


def count_keywords(text: str, keywords: List[str]) -> int:
    """키워드 개수 계산"""
    text_lower = text.lower()
    found_keywords = [kw for kw in keywords if kw.lower() in text_lower]
    return len(found_keywords)


def count_sentences(text: str) -> int:
    """문장 개수 계산"""
    # 간단한 문장 분리 (마침표, 물음표, 느낌표 기준)
    sentences = re.split(r'[.!?]\s+', text)
    return len([s for s in sentences if s.strip()])


def count_words(text: str) -> int:
    """단어 개수 계산"""
    words = re.findall(r'\b\w+\b', text)
    return len(words)


def has_xml_tags(text: str) -> bool:
    """XML 태그 사용 여부"""
    xml_pattern = r'<[^>]+>'
    return bool(re.search(xml_pattern, text))


def count_xml_tags(text: str) -> int:
    """XML 태그 개수"""
    xml_pattern = r'<[^>]+>'
    return len(re.findall(xml_pattern, text))


def has_code_blocks(text: str) -> bool:
    """코드 블록 사용 여부"""
    code_pattern = r'```[\s\S]*?```'
    return bool(re.search(code_pattern, text))


def count_code_blocks(text: str) -> int:
    """코드 블록 개수"""
    code_pattern = r'```[\s\S]*?```'
    return len(re.findall(code_pattern, text))


def has_examples(text: str) -> bool:
    """예시 포함 여부 (입력/출력, 예시 키워드 등)"""
    example_keywords = [
        '예시', '예', '입력', '출력', '예를 들어', '예를 들면',
        'example', 'input', 'output', 'for example', 'e.g.'
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in example_keywords)


def count_examples(text: str) -> int:
    """예시 개수 (입력/출력 쌍 또는 예시 키워드 기준)"""
    # 입력/출력 패턴 찾기
    input_pattern = r'입력[:\s]*[^\n]+'
    output_pattern = r'출력[:\s]*[^\n]+'
    input_matches = len(re.findall(input_pattern, text, re.IGNORECASE))
    output_matches = len(re.findall(output_pattern, text, re.IGNORECASE))
    
    # 예시 키워드 찾기
    example_keywords = ['예시', '예', '예를 들어', '예를 들면', 'example', 'e.g.']
    example_count = sum(1 for kw in example_keywords if kw.lower() in text.lower())
    
    # 입력/출력 쌍과 예시 키워드 중 더 큰 값 반환
    return max(input_matches, output_matches, example_count)


def has_constraints(text: str) -> bool:
    """제약 조건 명시 여부"""
    constraint_keywords = [
        '제약', '제약조건', '제약 조건', '조건', '제한', '제한사항',
        'constraint', 'limit', 'requirement', 'condition',
        '시간 복잡도', '공간 복잡도', 'time complexity', 'space complexity',
        'O(', 'O(n', 'O(log'
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in constraint_keywords)


def count_constraints(text: str) -> int:
    """제약 조건 개수"""
    constraint_keywords = [
        '제약', '제약조건', '제약 조건', '조건', '제한', '제한사항',
        'constraint', 'limit', 'requirement', 'condition',
        '시간 복잡도', '공간 복잡도', 'time complexity', 'space complexity'
    ]
    text_lower = text.lower()
    return sum(1 for kw in constraint_keywords if kw in text_lower)


def has_context_reference(text: str) -> bool:
    """이전 대화 참조 여부"""
    context_keywords = [
        '이전', '앞서', '앞에서', '위에서', '지금까지', '방금',
        '제안해주신', '작성해주신', '말씀하신', '알려주신',
        'previous', 'earlier', 'above', 'mentioned', 'said'
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in context_keywords)


def count_context_references(text: str) -> int:
    """이전 대화 참조 개수"""
    context_keywords = [
        '이전', '앞서', '앞에서', '위에서', '지금까지', '방금',
        '제안해주신', '작성해주신', '말씀하신', '알려주신',
        'previous', 'earlier', 'above', 'mentioned', 'said'
    ]
    text_lower = text.lower()
    return sum(1 for kw in context_keywords if kw in text_lower)


def has_technical_terms(text: str, problem_algorithms: Optional[List[str]] = None) -> int:
    """기술 용어 사용 개수"""
    # 기본 기술 용어
    technical_terms = [
        '알고리즘', '자료구조', '복잡도', '시간복잡도', '공간복잡도',
        '알고리즘', 'algorithm', 'data structure', 'complexity',
        'DP', '동적계획법', 'dynamic programming',
        '그래프', '트리', 'graph', 'tree',
        '비트마스킹', 'bitmask', 'bitmasking',
        '재귀', 'recursion', 'recursive',
        '반복문', 'iteration', 'iterative',
        '정렬', 'sort', 'sorting',
        '탐색', 'search', 'searching',
        '해시', 'hash', 'hashing'
    ]
    
    # 문제별 알고리즘 추가
    if problem_algorithms:
        technical_terms.extend(problem_algorithms)
    
    text_lower = text.lower()
    found_terms = [term for term in technical_terms if term.lower() in text_lower]
    return len(found_terms)


def has_specific_values(text: str) -> bool:
    """구체적 숫자/값 포함 여부"""
    # 숫자 패턴 (정수, 소수, 복잡도 표기 등)
    number_patterns = [
        r'\b\d+\b',  # 정수
        r'\b\d+\.\d+\b',  # 소수
        r'O\([^)]+\)',  # 복잡도 표기 (O(n), O(n^2) 등)
        r'\b\d+\s*초',  # 시간 단위
        r'\b\d+\s*MB',  # 메모리 단위
    ]
    
    for pattern in number_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def count_specific_values(text: str) -> int:
    """구체적 숫자/값 개수"""
    number_patterns = [
        r'\b\d+\b',  # 정수
        r'\b\d+\.\d+\b',  # 소수
        r'O\([^)]+\)',  # 복잡도 표기
    ]
    
    count = 0
    for pattern in number_patterns:
        count += len(re.findall(pattern, text, re.IGNORECASE))
    
    return count


def has_structured_format(text: str) -> bool:
    """구조화된 형식 사용 여부 (리스트, 번호 매기기 등)"""
    # 리스트 패턴 (번호, 불릿, 대시 등)
    list_patterns = [
        r'^\d+[\.\)]\s',  # 번호 매기기
        r'^[-*+]\s',  # 불릿 포인트
        r'^\s*[-*+]\s',  # 들여쓰기 불릿
    ]
    
    lines = text.split('\n')
    for line in lines:
        for pattern in list_patterns:
            if re.match(pattern, line):
                return True
    
    return False


def count_structured_elements(text: str) -> int:
    """구조화된 요소 개수 (리스트 항목, 번호 매기기 등)"""
    list_patterns = [
        r'^\d+[\.\)]\s',  # 번호 매기기
        r'^[-*+]\s',  # 불릿 포인트
    ]
    
    lines = text.split('\n')
    count = 0
    for line in lines:
        for pattern in list_patterns:
            if re.match(pattern, line):
                count += 1
                break
    
    return count


def calculate_clarity_metrics(text: str) -> Dict[str, Any]:
    """명확성 메트릭 계산"""
    word_count = count_words(text)
    sentence_count = count_sentences(text)
    avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
    
    # 명확성 지표
    # - 적절한 길이: 너무 짧으면 모호, 너무 길면 복잡
    # - 문장당 단어 수: 적절한 복잡도
    # - 구체적 값 포함: 숫자, 복잡도 등
    
    has_specific = has_specific_values(text)
    specific_count = count_specific_values(text)
    
    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_words_per_sentence": round(avg_words_per_sentence, 2),
        "has_specific_values": has_specific,
        "specific_value_count": specific_count,
        "clarity_score_base": _calculate_clarity_base_score(word_count, sentence_count, has_specific)
    }


def calculate_examples_metrics(text: str) -> Dict[str, Any]:
    """예시 메트릭 계산"""
    has_ex = has_examples(text)
    example_count = count_examples(text)
    
    return {
        "has_examples": has_ex,
        "example_count": example_count,
        "examples_score_base": _calculate_examples_base_score(has_ex, example_count)
    }


def calculate_rules_metrics(text: str) -> Dict[str, Any]:
    """규칙 메트릭 계산"""
    has_xml = has_xml_tags(text)
    xml_count = count_xml_tags(text)
    has_const = has_constraints(text)
    constraint_count = count_constraints(text)
    has_structured = has_structured_format(text)
    structured_count = count_structured_elements(text)
    
    return {
        "has_xml_tags": has_xml,
        "xml_tag_count": xml_count,
        "has_constraints": has_const,
        "constraint_count": constraint_count,
        "has_structured_format": has_structured,
        "structured_element_count": structured_count,
        "rules_score_base": _calculate_rules_base_score(has_xml, xml_count, has_const, constraint_count, has_structured)
    }


def calculate_context_metrics(text: str) -> Dict[str, Any]:
    """문맥 메트릭 계산"""
    has_context = has_context_reference(text)
    context_count = count_context_references(text)
    
    return {
        "has_context_reference": has_context,
        "context_reference_count": context_count,
        "context_score_base": _calculate_context_base_score(has_context, context_count)
    }


def calculate_problem_relevance_metrics(text: str, problem_algorithms: Optional[List[str]] = None) -> Dict[str, Any]:
    """문제 적절성 메트릭 계산"""
    technical_term_count = has_technical_terms(text, problem_algorithms)
    
    return {
        "technical_term_count": technical_term_count,
        "problem_relevance_score_base": _calculate_problem_relevance_base_score(technical_term_count, problem_algorithms)
    }


def calculate_all_metrics(text: str, problem_algorithms: Optional[List[str]] = None) -> Dict[str, Any]:
    """모든 메트릭 계산"""
    return {
        "clarity": calculate_clarity_metrics(text),
        "examples": calculate_examples_metrics(text),
        "rules": calculate_rules_metrics(text),
        "context": calculate_context_metrics(text),
        "problem_relevance": calculate_problem_relevance_metrics(text, problem_algorithms),
        "text_length": len(text),
        "word_count": count_words(text),
        "sentence_count": count_sentences(text),
        "has_code_blocks": has_code_blocks(text),
        "code_block_count": count_code_blocks(text),
    }


# 점수 계산 헬퍼 함수들

def _calculate_clarity_base_score(word_count: int, sentence_count: int, has_specific: bool) -> float:
    """명확성 기본 점수 계산 (0-100)"""
    score = 0.0
    
    # 적절한 길이 (20-200 단어: 좋음, 10-20 또는 200-300: 보통, 그 외: 나쁨)
    if 20 <= word_count <= 200:
        score += 40
    elif 10 <= word_count < 20 or 200 < word_count <= 300:
        score += 25
    elif word_count < 10:
        score += 10  # 너무 짧음
    else:
        score += 15  # 너무 김
    
    # 적절한 문장 수 (2-10 문장: 좋음)
    if 2 <= sentence_count <= 10:
        score += 30
    elif sentence_count == 1:
        score += 15  # 너무 짧음
    else:
        score += 20  # 너무 김
    
    # 구체적 값 포함
    if has_specific:
        score += 30
    else:
        score += 0
    
    return min(score, 100.0)


def _calculate_examples_base_score(has_examples: bool, example_count: int) -> float:
    """예시 기본 점수 계산 (0-100)"""
    if not has_examples:
        return 0.0
    
    # 예시 개수에 따른 점수
    if example_count >= 2:
        return 100.0
    elif example_count == 1:
        return 70.0
    else:
        return 30.0


def _calculate_rules_base_score(has_xml: bool, xml_count: int, has_constraints: bool, constraint_count: int, has_structured: bool) -> float:
    """규칙 기본 점수 계산 (0-100)"""
    score = 0.0
    
    # XML 태그 사용
    if has_xml:
        score += 30
        if xml_count >= 2:
            score += 10
    
    # 제약 조건 명시
    if has_constraints:
        score += 40
        if constraint_count >= 2:
            score += 10
    
    # 구조화된 형식
    if has_structured:
        score += 20
    
    return min(score, 100.0)


def _calculate_context_base_score(has_context: bool, context_count: int) -> float:
    """문맥 기본 점수 계산 (0-100)"""
    if not has_context:
        return 0.0
    
    # 참조 개수에 따른 점수
    if context_count >= 2:
        return 100.0
    elif context_count == 1:
        return 70.0
    else:
        return 30.0


def _calculate_problem_relevance_base_score(technical_term_count: int, problem_algorithms: Optional[List[str]] = None) -> float:
    """문제 적절성 기본 점수 계산 (0-100)"""
    if technical_term_count == 0:
        return 0.0
    
    # 기술 용어 개수에 따른 점수
    if technical_term_count >= 3:
        return 100.0
    elif technical_term_count == 2:
        return 80.0
    elif technical_term_count == 1:
        return 60.0
    else:
        return 30.0



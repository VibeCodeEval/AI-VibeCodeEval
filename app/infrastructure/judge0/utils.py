"""
Judge0 유틸리티 함수
코드 정리 및 형식 변환
"""
import re
from typing import Optional


def clean_code(code: str) -> str:
    """
    제출 코드 정리
    
    제거 항목:
    - 마크다운 코드 블록 (```python ... ```, ``` ... ```)
    - 불필요한 공백
    - 특수 문자 (필요시)
    
    변환 항목:
    - 이스케이프된 줄바꿈 문자 (`\\n`)를 실제 줄바꿈으로 변환
    
    Args:
        code: 원본 코드
        
    Returns:
        정리된 코드
    """
    if not code:
        return ""
    
    cleaned = code.strip()
    
    # 이스케이프된 줄바꿈 문자를 실제 줄바꿈으로 변환
    # JSON에서 `\n`이 문자열로 들어온 경우 처리
    # `\\n` -> `\n` (실제 줄바꿈)
    # 주의: 실제 줄바꿈이 없고 이스케이프된 줄바꿈만 있는 경우만 변환
    if "\\n" in cleaned:
        # 실제 줄바꿈이 있는지 확인
        has_actual_newline = "\n" in cleaned
        if not has_actual_newline:
            # 실제 줄바꿈이 없고 `\n` 문자열만 있는 경우 변환
            # 예: "import sys\\ndef func" -> "import sys\ndef func"
            cleaned = cleaned.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    
    # 마크다운 코드 블록 제거
    # ```python ... ``` 형식
    pattern1 = r'^```(?:python|py)?\s*\n(.*?)\n```\s*$'
    match1 = re.match(pattern1, cleaned, re.DOTALL)
    if match1:
        cleaned = match1.group(1)
    
    # ``` ... ``` 형식 (위 패턴에 매치되지 않은 경우)
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.split("\n")
        if len(lines) >= 3:
            # 첫 줄 (```python 또는 ```)과 마지막 줄 (```) 제거
            cleaned = "\n".join(lines[1:-1])
    
    # 앞뒤 공백 제거
    cleaned = cleaned.strip()
    
    return cleaned


def extract_language_from_string(lang_str: str) -> str:
    """
    언어 문자열에서 기본 언어 추출
    
    예:
    - "python3.11" -> "python"
    - "python3" -> "python"
    - "java" -> "java"
    - "cpp" -> "cpp"
    
    Args:
        lang_str: 언어 문자열
        
    Returns:
        기본 언어 이름
    """
    if not lang_str:
        return "python"
    
    lang_lower = lang_str.lower().strip()
    
    # Python 변형들
    if lang_lower.startswith("python"):
        return "python"
    
    # 다른 언어들
    language_map = {
        "java": "java",
        "cpp": "cpp",
        "c++": "cpp",
        "c": "c",
        "javascript": "javascript",
        "nodejs": "javascript",
        "js": "javascript",
        "go": "go",
        "rust": "rust",
    }
    
    return language_map.get(lang_lower, "python")


def validate_code_format(code: str) -> tuple[bool, Optional[str]]:
    """
    코드 형식 검증
    
    Args:
        code: 검증할 코드
        
    Returns:
        (유효 여부, 오류 메시지)
    """
    if not code:
        return False, "코드가 비어있습니다"
    
    if len(code.strip()) == 0:
        return False, "코드가 공백만 있습니다"
    
    # 마크다운 코드 블록만 있는 경우 경고
    if code.strip().startswith("```") and code.strip().endswith("```"):
        return True, "마크다운 코드 블록이 포함되어 있습니다. 정리 후 사용하세요."
    
    return True, None



"""
프롬프트 YAML 로더 유틸리티

[목적]
- YAML 파일에서 프롬프트 템플릿을 로드
- 변수 치환을 통한 동적 프롬프트 생성
- 프롬프트 버전 관리 및 유지보수성 향상

[사용법]
```python
from app.domain.langgraph.prompts import load_prompt, render_prompt

# 단순 로드
prompt = load_prompt("intent_analyzer")

# 변수 치환과 함께 로드
prompt = render_prompt("writer_normal", status="SAFE", guide_strategy="LOGIC_HINT")
```
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# 프롬프트 파일 기본 경로
PROMPTS_DIR = Path(__file__).parent


class PromptNotFoundError(Exception):
    """프롬프트 파일을 찾을 수 없을 때 발생하는 예외"""

    pass


class PromptRenderError(Exception):
    """프롬프트 렌더링 중 오류가 발생했을 때 발생하는 예외"""

    pass


@lru_cache(maxsize=32)
def _load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    YAML 파일을 로드하고 캐싱합니다.

    Args:
        file_path: YAML 파일 경로

    Returns:
        Dict[str, Any]: 파싱된 YAML 내용

    Raises:
        PromptNotFoundError: 파일을 찾을 수 없는 경우
    """
    path = Path(file_path)
    if not path.exists():
        raise PromptNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            logger.debug(f"프롬프트 파일 로드 완료: {file_path}")
            return content
    except yaml.YAMLError as e:
        raise PromptRenderError(f"YAML 파싱 오류: {file_path} - {str(e)}")


def load_prompt(name: str, section: Optional[str] = None) -> Dict[str, Any]:
    """
    프롬프트 YAML 파일을 로드합니다.

    Args:
        name: 프롬프트 이름 (확장자 제외, 예: "intent_analyzer")
        section: 특정 섹션만 로드할 경우 섹션 이름

    Returns:
        Dict[str, Any]: 프롬프트 데이터

    Raises:
        PromptNotFoundError: 프롬프트 파일을 찾을 수 없는 경우

    Examples:
        >>> data = load_prompt("intent_analyzer")
        >>> print(data["template"])
    """
    # 하위 디렉토리 지원 (예: "eval_criteria/generation")
    if "/" in name:
        file_path = PROMPTS_DIR / f"{name}.yaml"
    else:
        file_path = PROMPTS_DIR / f"{name}.yaml"

    content = _load_yaml_file(str(file_path))

    if section and section in content:
        return content[section]

    return content


def render_prompt(name: str, section: Optional[str] = None, **variables) -> str:
    """
    프롬프트 템플릿을 로드하고 변수를 치환합니다.

    Args:
        name: 프롬프트 이름 (확장자 제외)
        section: 특정 섹션만 로드할 경우 섹션 이름
        **variables: 템플릿에 치환할 변수들

    Returns:
        str: 렌더링된 프롬프트 문자열

    Raises:
        PromptNotFoundError: 프롬프트 파일을 찾을 수 없는 경우
        PromptRenderError: 렌더링 중 오류가 발생한 경우

    Examples:
        >>> prompt = render_prompt(
        ...     "intent_analyzer",
        ...     problem_title="외판원 순회",
        ...     algorithms="DP, 비트마스킹"
        ... )
    """
    data = load_prompt(name, section)

    # template 필드 확인
    template_str = data.get("template", "")
    if not template_str:
        raise PromptRenderError(f"프롬프트 '{name}'에 template 필드가 없습니다.")

    try:
        # Python의 string.Template을 사용한 변수 치환
        # $variable 또는 ${variable} 형식 지원
        template = Template(template_str)

        # safe_substitute를 사용하여 누락된 변수는 그대로 유지
        rendered = template.safe_substitute(**variables)

        logger.debug(
            f"프롬프트 렌더링 완료: {name}, 변수: {list(variables.keys())}, 결과 길이: {len(rendered)}"
        )
        return rendered
    except Exception as e:
        raise PromptRenderError(f"프롬프트 렌더링 오류: {name} - {str(e)}")


def get_prompt_template(name: str) -> str:
    """
    프롬프트의 원본 템플릿 문자열을 반환합니다.

    Args:
        name: 프롬프트 이름

    Returns:
        str: 원본 템플릿 문자열
    """
    data = load_prompt(name)
    return data.get("template", "")


def get_prompt_variables(name: str) -> list:
    """
    프롬프트에 정의된 변수 목록을 반환합니다.

    Args:
        name: 프롬프트 이름

    Returns:
        list: 변수 이름 목록
    """
    data = load_prompt(name)
    return data.get("variables", [])


def get_prompt_metadata(name: str) -> Dict[str, Any]:
    """
    프롬프트의 메타데이터를 반환합니다.

    Args:
        name: 프롬프트 이름

    Returns:
        Dict[str, Any]: 메타데이터 (version, name, description 등)
    """
    data = load_prompt(name)
    return {
        "version": data.get("version", "1.0"),
        "name": data.get("name", name),
        "description": data.get("description", ""),
        "variables": data.get("variables", []),
    }


def clear_cache():
    """프롬프트 캐시를 초기화합니다."""
    _load_yaml_file.cache_clear()
    logger.info("프롬프트 캐시 초기화 완료")


# 편의 함수들
__all__ = [
    "load_prompt",
    "render_prompt",
    "get_prompt_template",
    "get_prompt_variables",
    "get_prompt_metadata",
    "clear_cache",
    "PromptNotFoundError",
    "PromptRenderError",
    "PROMPTS_DIR",
]

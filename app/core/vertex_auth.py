"""
Vertex AI용 서비스 계정 로딩.

- GOOGLE_SERVICE_ACCOUNT_JSON: .env에 JSON 문자열(한 줄 등)로 넣는 방식
- GOOGLE_SERVICE_ACCOUNT_JSON_PATH: 프로젝트 루트 기준 상대 경로 또는 절대 경로의 *.json 파일
- 둘 다 비어 있으면 credentials=None → google.auth 기본 자격 증명(ADC) 사용
  (예: GOOGLE_APPLICATION_CREDENTIALS, gcloud auth application-default login, GCE 메타데이터)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

# app/core/vertex_auth.py → 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# SA JSON을 코드에서 직접 로드할 때 scope 미지정 시 invalid_scope 발생 (genai/Vertex).
# GOOGLE_APPLICATION_CREDENTIALS(ADC)는 런타임이 scope를 붙이지만, from_service_account_info는 명시 필요.
VERTEX_OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
)


def resolve_vertex_project_id(settings: Optional["Settings"] = None) -> Optional[str]:
    """
    Vertex `project` 인자.
    1) .env 의 GOOGLE_PROJECT_ID
    2) 없으면 서비스 계정 JSON(path 또는 문자열)의 project_id
    """
    from app.core.config import settings as default_settings

    s = settings or default_settings
    explicit = (s.GOOGLE_PROJECT_ID or "").strip()
    if explicit:
        return explicit
    info = _load_service_account_dict(s)
    if isinstance(info, dict):
        pid = info.get("project_id")
        if isinstance(pid, str) and pid.strip():
            return pid.strip()
    return None


def load_vertex_credentials(settings: Optional["Settings"] = None) -> Any:
    """
    Vertex `ChatGoogleGenerativeAI(..., credentials=...)`에 넘길 Credentials.
    서비스 계정 정보가 없으면 None (ADC 사용).
    """
    from google.oauth2 import service_account

    from app.core.config import settings as default_settings

    s = settings or default_settings
    info = _load_service_account_dict(s)
    if info is None:
        return None
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=VERTEX_OAUTH_SCOPES,
    )


def _load_service_account_dict(s: "Settings") -> Optional[dict]:
    raw = (s.GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("GOOGLE_SERVICE_ACCOUNT_JSON 파싱 실패")
            raise

    path_str = (s.GOOGLE_SERVICE_ACCOUNT_JSON_PATH or "").strip()
    if not path_str:
        return None

    path = Path(path_str)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    if not path.is_file():
        logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON_PATH 파일 없음: %s", path)
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)

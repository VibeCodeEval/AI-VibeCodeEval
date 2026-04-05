#!/usr/bin/env python3
"""
배치로 Worker `POST /api/session/submit`을 여러 번 호출합니다.

JWT 관리 (Core / Spring)
------------------------
- 시험 생성·시험 시작·참가 등은 보통 Core 백엔드에서 JWT로 보호됩니다.
- 이 Worker(FastAPI)의 submit/chat 라우트는 현재 코드베이스 기준으로 JWT 미적용입니다.
- 배치 실행 전에 Core에서 필요한 행(시험·참가자·제출 ID 등)을 준비한 뒤,
  여기서는 **Core용 JWT**만 선택적으로 써서 `globalCorePrelude` / `corePrelude` HTTP 호출을 수행할 수 있습니다.

토큰 주입 우선순위:
  1) `--core-token` CLI
  2) `--core-token-file` 파일 내용(한 줄)
  3) 환경변수: 시나리오의 `coreJwtEnv`(기본 `VIBECODE_CORE_JWT`) 또는 `CORE_JWT`

토큰은 `Bearer ` 접두사가 있으면 그대로, 없으면 `Bearer `를 붙여 전송합니다.
만료 시 Core에서 재로그인·재발급 후 환경변수를 갱신하고 스크립트를 다시 실행하면 됩니다.

제약
----
- DB에 `exam_participants`·`submission` 등이 이미 있어야 submit이 성공합니다.
- 동일 (examId, participantId)에 대한 제출 제약이 있으면 시나리오마다 다른 participant/submission을 쓰세요.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


def _normalize_bearer(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip()
    if not t:
        return None
    if t.lower().startswith("bearer "):
        return t
    return f"Bearer {t}"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_core_token(args: argparse.Namespace, doc: dict[str, Any]) -> str | None:
    if args.core_token:
        return _normalize_bearer(args.core_token)
    if args.core_token_file:
        raw = Path(args.core_token_file).read_text(encoding="utf-8").strip()
        return _normalize_bearer(raw)
    env_name = doc.get("coreJwtEnv") or "VIBECODE_CORE_JWT"
    for key in (env_name, "VIBECODE_CORE_JWT", "CORE_JWT"):
        v = os.environ.get(key)
        if v:
            return _normalize_bearer(v)
    return None


def _read_final_code(scenario_dir: Path, submit: dict[str, Any]) -> str:
    if "finalCode" in submit and submit["finalCode"] is not None:
        return str(submit["finalCode"])
    f = submit.get("finalCodeFile")
    if not f:
        raise ValueError("submit에 finalCode 또는 finalCodeFile이 필요합니다.")
    p = Path(f)
    if not p.is_absolute():
        p = scenario_dir / p
    return p.read_text(encoding="utf-8")


def _build_submit_body(scenario_dir: Path, submit: dict[str, Any]) -> dict[str, Any]:
    body = {
        "examId": submit["examId"],
        "participantId": submit["participantId"],
        "problemId": submit["problemId"],
        "specId": submit["specId"],
        "language": submit["language"],
        "submissionId": submit["submissionId"],
        "finalCode": _read_final_code(scenario_dir, submit),
    }
    return body


def _run_core_step(
    client: httpx.Client,
    core_base: str,
    auth: str | None,
    step: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    method = step.get("method", "GET").upper()
    path = step["path"]
    url = path if path.startswith("http://") or path.startswith("https://") else f"{core_base.rstrip('/')}/{path.lstrip('/')}"
    headers: dict[str, str] = {}
    if auth:
        headers["Authorization"] = auth
    json_body = step.get("json")
    if dry_run:
        print(f"  [DRY-RUN] CORE {method} {url} json={json_body!r}")
        return
    resp = client.request(method, url, headers=headers, json=json_body, timeout=120.0)
    print(f"  CORE {method} {url} -> {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:2000])
        resp.raise_for_status()


def _run_submit(
    client: httpx.Client,
    worker_base: str,
    body: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    url = f"{worker_base.rstrip('/')}/api/session/submit"
    if dry_run:
        print(f"  [DRY-RUN] WORKER POST {url} keys={list(body.keys())}")
        return
    resp = client.post(url, json=body, timeout=600.0)
    print(f"  WORKER POST {url} -> {resp.status_code}")
    try:
        data = resp.json()
        print(f"  body: {json.dumps(data, ensure_ascii=False)[:1500]}")
    except Exception:
        print(f"  raw: {resp.text[:1500]}")
    resp.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="배치 submit 시나리오 실행")
    parser.add_argument(
        "scenario_file",
        nargs="?",
        default="scripts/batch_eval_scenarios.example.json",
        help="시나리오 JSON 경로",
    )
    parser.add_argument("--worker-url", default=None, help="Worker 베이스 URL (JSON settings보다 우선)")
    parser.add_argument("--core-url", default=None, help="Core 베이스 URL (JSON settings보다 우선)")
    parser.add_argument("--core-token", default=None, help="Core JWT (Bearer 생략 가능)")
    parser.add_argument("--core-token-file", default=None, help="JWT 한 줄을 담은 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="HTTP 호출 없이 출력만")
    parser.add_argument("--continue-on-error", action="store_true", help="한 시나리오 실패 후에도 계속")
    args = parser.parse_args()

    scenario_path = Path(args.scenario_file).resolve()
    if not scenario_path.is_file():
        print(f"시나리오 파일 없음: {scenario_path}", file=sys.stderr)
        return 2

    doc = _load_json(scenario_path)
    settings = doc.get("settings") or {}
    worker_base = (args.worker_url or settings.get("workerBaseUrl") or "http://127.0.0.1:8000").rstrip("/")
    core_base = (args.core_url or settings.get("coreBaseUrl") or "").rstrip("/")
    scenario_dir = scenario_path.parent

    global_prelude = list(doc.get("globalCorePrelude") or [])
    scenarios = doc.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        print("scenarios 배열이 비어 있습니다.", file=sys.stderr)
        return 2

    auth = _resolve_core_token(args, doc)
    if global_prelude or any((s.get("corePrelude") or []) for s in scenarios):
        if not core_base:
            print(
                "Core prelude가 있는데 coreBaseUrl이 없습니다. settings.coreBaseUrl 또는 --core-url 을 지정하세요.",
                file=sys.stderr,
            )
            return 2
        if not auth and not args.dry_run:
            print(
                "경고: Core prelude는 JWT가 필요할 수 있습니다. "
                "VIBECODE_CORE_JWT 또는 --core-token 을 설정하세요.",
                file=sys.stderr,
            )

    exit_code = 0
    with httpx.Client() as client:
        for step in global_prelude:
            try:
                _run_core_step(client, core_base, auth, step, dry_run=args.dry_run)
            except Exception as e:
                print(f"globalCorePrelude 실패: {e}", file=sys.stderr)
                exit_code = 1
                if not args.continue_on_error:
                    return exit_code

        for sc in scenarios:
            name = sc.get("name", "(unnamed)")
            print(f"\n=== 시나리오: {name} ===")
            try:
                for step in sc.get("corePrelude") or []:
                    _run_core_step(client, core_base, auth, step, dry_run=args.dry_run)
                submit = sc.get("submit")
                if not submit:
                    raise ValueError("submit 블록이 없습니다.")
                body = _build_submit_body(scenario_dir, submit)
                _run_submit(client, worker_base, body, dry_run=args.dry_run)
            except Exception as e:
                print(f"실패: {e}", file=sys.stderr)
                exit_code = 1
                if not args.continue_on_error:
                    return exit_code

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""
v2.1 파인튜닝 데이터 생성 스크립트 (Seed & Mutate + Fast-Track).

- 3개 Seed Code (A, C, F) 기반으로 프롬프트만 변형(Mutation)하여 5등급(A,B,C,D,F) 100건 고속 생성.
- asyncio.gather + Semaphore(10)으로 병렬 처리, Gemini Flash로 mock reasoning 생성.
- Holistic Evaluator 미실행 → generate_mock_reasoning()으로 가상 metrics·reasoning 생성.

핵심 라이브러리: asyncio, json, random, tqdm, langchain_google_genai (GoogleGenerativeAI)
출력: data/v21_finetuning_dataset.jsonl (기본)

사용법:
  uv run python scripts/generate_synthetic_v21_data.py
  uv run python scripts/generate_synthetic_v21_data.py -o data/v21_finetuning_dataset.jsonl --per-grade 20
  uv run python scripts/generate_synthetic_v21_data.py --no-llm  # LLM 없이 템플릿만
"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# -----------------------------------------------------------------------------
# SEED_CODES: A, C, F 3가지 Anchor.
# - v1_code: Phase 1 체크포인트 (출력 필드명은 context로 매핑)
# - v2_code: Phase 2 반영 후 코드 (또는 F의 경우 실패 코드)
# -----------------------------------------------------------------------------
SEED_CODES: dict[str, dict[str, str]] = {
    # -------------------------------------------------------------------------
    # [SEED A] Senior Anchor
    # - 특징: 완벽한 전략 패턴, OCP 준수(GateManager 수정 없음), 낮은 복잡도.
    # - v2 변화: SecurityRule 클래스 추가 및 주입, LuggageRule 내부 로직만 변경.
    # -------------------------------------------------------------------------
    "A": {
        "v1_code": """
class BaseRule:
    def check(self, passenger, context):
        raise NotImplementedError

class PassportRule(BaseRule):
    def check(self, passenger, context):
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"
        return None

class FlightStatusRule(BaseRule):
    def check(self, passenger, context):
        if passenger.flight_status != "BOARDING":
            return "REJECT" if passenger.flight_status != "DELAYED" else "WAIT"
        return None

class LuggageRule(BaseRule):
    def check(self, passenger, context):
        limit = 30 if passenger.seat_class == "BUSINESS" else 20
        if passenger.luggage_kg > limit:
            return "CHARGE_FEE"
        return None

class GateManager:
    def __init__(self, rules):
        self.rules = rules

    def process(self, passenger, context):
        for rule in self.rules:
            result = rule.check(passenger, context)
            if result:
                return result
        return "PASS"
""",
        "v2_code": """
class BaseRule:
    def check(self, passenger, context):
        raise NotImplementedError

class PassportRule(BaseRule):
    def check(self, passenger, context):
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"
        return None

class FlightStatusRule(BaseRule):
    def check(self, passenger, context):
        if passenger.flight_status != "BOARDING":
            return "REJECT" if passenger.flight_status != "DELAYED" else "WAIT"
        return None

# [Change 1] 상태(Tracker)를 주입받아 처리 (OCP 준수)
class LuggageRule(BaseRule):
    def __init__(self, overcharge_tracker=None):
        self.overcharge_tracker = overcharge_tracker or {}

    def check(self, passenger, context):
        limit = 30 if passenger.seat_class == "BUSINESS" else 20

        # 누적 과금 3회 이상 시 페널티 적용
        if self.overcharge_tracker.get(passenger.flight_id, 0) >= 3:
            limit -= 5

        if passenger.luggage_kg > limit:
            # 카운트 증가
            current = self.overcharge_tracker.get(passenger.flight_id, 0)
            self.overcharge_tracker[passenger.flight_id] = current + 1
            return "CHARGE_FEE"
        return None

# [Change 2] 새로운 요구사항을 별도 클래스로 분리 (Strategy Pattern)
class SecurityRule(BaseRule):
    def check(self, passenger, context):
        if context.threat_level == "HIGH":
            return "SECURITY_CHECK"
        return None

class GateManager:
    def __init__(self, rules):
        self.rules = rules

    # GateManager 로직 수정 없음 (인터페이스만 사용)
    def process(self, passenger, context):
        for rule in self.rules:
            result = rule.check(passenger, context)
            if result:
                return result
        return "PASS"

# 실행 예시 (외부에서 주입)
# tracker = {}
# rules = [SecurityRule(), PassportRule(), FlightStatusRule(), LuggageRule(tracker)]
# manager = GateManager(rules)
"""
    },

    # -------------------------------------------------------------------------
    # [SEED C] Junior Anchor
    # - 특징: 기능은 동작하지만 if/else 남발, 하드코딩, 높은 결합도.
    # - v2 변화: Manager 내부에 if문 추가, 전역 변수 사용 등 구조적 문제 발생.
    # -------------------------------------------------------------------------
    "C": {
        "v1_code": """
class GateManager:
    def process(self, passenger, context):
        # 규칙들이 분리되지 않고 Manager 안에 뭉쳐있음 (높은 복잡도)

        # 1. 여권 검사
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"

        # 2. 항공편 검사
        if passenger.flight_status != "BOARDING":
            if passenger.flight_status == "DELAYED":
                return "WAIT"
            else:
                return "REJECT"

        # 3. 수하물 검사
        limit = 20
        if passenger.seat_class == "BUSINESS":
            limit = 30

        if passenger.luggage_kg > limit:
            return "CHARGE_FEE"

        return "PASS"
""",
        "v2_code": """
# 전역 변수 사용 (Bad Practice)
overcharge_count = {}

class GateManager:
    def process(self, passenger, context):
        # [Change 1] 하드코딩된 보안 규칙 추가 (OCP 위반)
        # 클래스 분리 없이 if문으로 끼워넣음
        if context.threat_level == "HIGH":
            return "SECURITY_CHECK"

        # 1. 여권 검사
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"

        # 2. 항공편 검사
        if passenger.flight_status != "BOARDING":
            if passenger.flight_status == "DELAYED":
                return "WAIT"
            else:
                return "REJECT"

        # 3. 수하물 검사 (복잡도 증가)
        limit = 20
        if passenger.seat_class == "BUSINESS":
            limit = 30

        # [Change 2] 비즈니스 로직이 메인 함수에 섞임
        flight_id = passenger.flight_id
        if flight_id in overcharge_count and overcharge_count[flight_id] >= 3:
            limit = limit - 5

        if passenger.luggage_kg > limit:
            if flight_id not in overcharge_count:
                overcharge_count[flight_id] = 0
            overcharge_count[flight_id] += 1
            return "CHARGE_FEE"

        return "PASS"
"""
    },

    # -------------------------------------------------------------------------
    # [SEED F] Failure Anchor
    # - 특징: 요구사항 오해 (Critical Logic Error).
    # - v2 변화: HIGH일 때 SECURITY_CHECK가 아니라 REJECT를 반환 (오답).
    # -------------------------------------------------------------------------
    "F": {
        "v1_code": """
class BaseRule:
    def check(self, passenger, context): raise NotImplementedError

class PassportRule(BaseRule):
    def check(self, passenger, context):
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"
        return None

class FlightStatusRule(BaseRule):
    def check(self, passenger, context):
        if passenger.flight_status != "BOARDING":
            return "REJECT" if passenger.flight_status != "DELAYED" else "WAIT"
        return None

class LuggageRule(BaseRule):
    def check(self, passenger, context):
        limit = 30 if passenger.seat_class == "BUSINESS" else 20
        if passenger.luggage_kg > limit:
            return "CHARGE_FEE"
        return None

class GateManager:
    def __init__(self, rules):
        self.rules = rules
    def process(self, passenger, context):
        for rule in self.rules:
            result = rule.check(passenger, context)
            if result: return result
        return "PASS"
""",
        "v2_code": """
class BaseRule:
    def check(self, passenger, context): raise NotImplementedError

class PassportRule(BaseRule):
    def check(self, passenger, context):
        if passenger.passport_expiry < context.reference_date:
            return "REJECT"
        return None

class FlightStatusRule(BaseRule):
    def check(self, passenger, context):
        if passenger.flight_status != "BOARDING":
            return "REJECT" if passenger.flight_status != "DELAYED" else "WAIT"
        return None

class LuggageRule(BaseRule):
    def __init__(self, tracker=None):
        self.tracker = tracker or {}
    def check(self, passenger, context):
        limit = 30 if passenger.seat_class == "BUSINESS" else 20
        # 로직 생략 또는 불완전 구현
        if passenger.luggage_kg > limit:
            return "CHARGE_FEE"
        return None

# [Critical Error] 요구사항 오해: HIGH -> REJECT (정답은 SECURITY_CHECK)
class SecurityRule(BaseRule):
    def check(self, passenger, context):
        if context.threat_level == "HIGH":
            return "REJECT"  # <--- 여기가 틀림 (F등급 사유)
        return None

class GateManager:
    def __init__(self, rules):
        self.rules = rules
    def process(self, passenger, context):
        for rule in self.rules:
            result = rule.check(passenger, context)
            if result: return result
        return "PASS"
"""
    }
}

# 등급 → 사용할 Seed 키 (Code는 SEED_CODES[seed_key] 사용)
GRADE_SEED_MAP = {
    "A": "A",
    "B": "A",
    "C": "C",
    "D": "C",
    "F": "F",
}

# -----------------------------------------------------------------------------
# PERSONAS: 등급별 적용할 페르소나 (프롬프트 생성 시 랜덤 적용)
# (이름, 설명, 적용 등급)
# -----------------------------------------------------------------------------
PERSONAS: list[tuple[str, str, list[str]]] = [
    ("Architect", "OCP, 전략 패턴 등 기술 용어 사용", ["A"]),
    ("Urgent PM", "설명 없이 기능만 빨리 추가해", ["B"]),
    ("Newbie", "어떻게 하는지 모르겠는데 보안 규칙 좀 넣어줘", ["C", "D"]),
    ("Minimalist", "SecurityRule 추가. 끝.", ["B"]),
    ("Vague/Typos", "모호한 지시, 오타 포함", ["D"]),
    ("Misunderstanding", "요구사항 오해: HIGH면 REJECT 시켜", ["F"]),
]

# WizardLM 스타일: 프롬프트 복잡도 강화 옵션 (랜덤 적용)
EVOLUTIONS: list[str] = [
    "제약 조건 추가: 시간 복잡도 O(n) 이하로 유지해줘.",
    "추론 요구: 왜 그렇게 설계했는지 한 줄로 설명해줘.",
    "입력 복잡도: 리스트·중첩 구조도 고려한 검사 로직으로.",
    "도메인 유지: 스마트 게이트 2026 스펙 그대로 준수.",
]

# 등급별 매핑 (Target Grade → Seed Code, Persona/Style, Evaluation Mock)
# Evaluation Logic: A ΔCC≈-8% AST=True, B 점수 A와 비슷하나 clarity 낮음, C ΔCC≈+20% AST=False, D clarity/relevance 낮음, F is_correct=False
GRADE_METRICS_TEMPLATE: dict[str, dict[str, Any]] = {
    "A": {"delta_cc_pct": -8.0, "ast_pattern_matched": True, "ast_applicable": True, "has_v1": True, "junior_grade": False, "clarity": 92, "problem_relevance": 95, "rules": 90, "examples": 88, "context": 90, "is_correct": True},
    "B": {"delta_cc_pct": 22.0, "ast_pattern_matched": True, "ast_applicable": True, "has_v1": True, "junior_grade": False, "clarity": 72, "problem_relevance": 82, "rules": 70, "examples": 68, "context": 75, "is_correct": True},
    "C": {"delta_cc_pct": 45.0, "ast_pattern_matched": False, "ast_applicable": True, "has_v1": True, "junior_grade": True, "clarity": 58, "problem_relevance": 55, "rules": 50, "examples": 48, "context": 52, "is_correct": True},
    "D": {"delta_cc_pct": 62.0, "ast_pattern_matched": False, "ast_applicable": True, "has_v1": True, "junior_grade": True, "clarity": 40, "problem_relevance": 38, "rules": 32, "examples": 28, "context": 35, "is_correct": True},
    "F": {"delta_cc_pct": 90.0, "ast_pattern_matched": False, "ast_applicable": False, "has_v1": False, "junior_grade": True, "clarity": 25, "problem_relevance": 20, "rules": 15, "examples": 10, "context": 20, "is_correct": False},
}

# Fallback용 evaluation_log (LLM 실패 시)
GRADE_EVALUATION_LOG: dict[str, str] = {
    "A": "[명확성 92] OCP·전략 패턴 등 아키텍처 용어 사용. ΔCC ≈ -8%, AST=True. A등급.",
    "B": "코드는 A급이나 지시가 불친절해 clarity 감점. B등급.",
    "C": "기능 중심 지시. ΔCC ≈ +20%, AST=False. C등급.",
    "D": "지시문 모호·오타. clarity·relevance 낮음. D등급.",
    "F": "요구사항 오해(REJECT 지시). is_correct=False. F등급.",
}

# LLM 없을 때 사용할 등급별 instruction 템플릿 (List[str]: Phase1, SAVE, Phase2...)
# 등급당 20종 이상 되도록 여러 변형 포함 (100건 생성 시 같은 지시문 반복 방지)
GRADE_INSTRUCTION_TEMPLATES: dict[str, list[list[str]]] = {
    "A": [
        ["공항 게이트 보안·수하물 과금 로직을 구현해줘. 여권 만료일, 항공편 상태, 좌석별 수하물 허용량을 검사하고, 규칙은 인터페이스로 분리해서 확장 가능하게 만들어줘.", "SAVE", "threat_level이 HIGH일 때는 기존 규칙보다 우선해서 전부 SECURITY_CHECK로 보내도록, BaseRule을 상속한 SecurityRule을 추가해줘. GateManager는 기존 전략 패턴을 유지해줘.", "누적 과금 3명 나온 항공편은 4번째 승객부터 허용 무게 -5kg 적용해줘."],
        ["여권·항공편·수하물 규칙으로 게이트 통과 여부를 판단하는 로직을 만들어줘. 규칙은 인터페이스로 분리하고, GateManager가 전략 패턴으로 규칙을 실행하도록 해줘.", "SAVE", "2차 요구: threat_level HIGH면 SECURITY_CHECK로 보내는 SecurityRule을 BaseRule 상속으로 추가해줘. GateManager.process()는 수정하지 말고 rules만 주입해서 써줘.", "같은 항공편에서 수하물 과금이 3명 나오면 4번째부터 허용 무게 -5kg 적용해줘."],
        ["스마트 게이트 로직 구현해줘. 여권 만료, 항공편 상태, 좌석별 수하물 한도를 검사하고, 각 규칙은 인터페이스로 분리해 확장 가능하게 만들어줘.", "SAVE", "변경 요구: threat_level이 HIGH일 때 기존 규칙보다 우선해 SECURITY_CHECK를 반환하는 SecurityRule을 BaseRule 상속해 추가하고, GateManager는 기존 전략 패턴 유지해줘.", "누적 과금 3명 초과한 항공편은 4번째 승객부터 허용 무게 5kg 감소 적용해줘."],
        ["게이트에서 여권 만료일·항공편 상태·수하물 무게를 검사하는 규칙을 구현해줘. 규칙은 공통 인터페이스로 분리하고, GateManager가 규칙 리스트를 순회하는 전략 패턴으로 동작하게 해줘.", "SAVE", "추가 요구: HIGH 위협 수준일 때 SECURITY_CHECK를 반환하는 SecurityRule을 BaseRule 상속으로 넣고, GateManager의 process() 코드는 건드리지 말고 rules에 SecurityRule을 최우선으로 주입해줘.", "한 항공편에서 과금이 3번 나오면 그 다음 승객부터 허용 무게 -5kg 해줘."],
        ["공항 게이트 보안·수하물 검사 로직을 구현해줘. 여권, 항공편, 수하물 규칙을 각각 클래스로 분리하고 인터페이스로 통일해서, GateManager가 규칙만 바꿔 끼워 넣을 수 있게 해줘.", "SAVE", "요구 변경: threat_level HIGH 시 전부 SECURITY_CHECK 처리하려면 BaseRule을 상속한 SecurityRule을 추가하고, GateManager는 기존처럼 rules 순서만 유지해줘.", "과금 3명 나온 항공편은 4번째부터 허용 무게 5kg 줄여줘."],
        ["여권/항공편/수하물 검사 규칙을 인터페이스 기반으로 분리하고, GateManager가 전략 패턴으로 규칙을 실행하도록 구현해줘.", "SAVE", "2차: threat_level이 HIGH일 때 SECURITY_CHECK를 반환하는 SecurityRule을 BaseRule 상속으로 추가하고, GateManager.process()는 그대로 두고 rules 리스트에 SecurityRule을 맨 앞에 넣어줘.", "동일 항공편에서 수하물 과금이 3명 발생하면 4번째부터 허용 무게 -5kg 적용해줘."],
        ["게이트 통과 판단 로직을 OCP 준수해서 만들어줘. 여권·항공편·수하물 규칙을 각각 Rule 인터페이스로 분리하고, GateManager는 주입받은 rules만 순회해줘.", "SAVE", "HIGH 위협 시 SECURITY_CHECK 반환하는 SecurityRule을 BaseRule 상속으로 추가해줘. GateManager 코드 수정 없이 rules만 조합해서 써줘.", "항공편별 누적 과금 3회 넘으면 그 다음부터 허용 무게 -5kg 적용해줘."],
        ["공항 게이트 Phase1·Phase2 요구사항 반영해줘. Phase1은 여권/항공편/수하물 규칙으로 통과 여부, Phase2는 threat HIGH면 SECURITY_CHECK, 과금 3명 나온 편은 4번째부터 -5kg.", "SAVE", "BaseRule 상속 SecurityRule 추가하고 GateManager 전략 패턴 유지해줘. process() 수정 없이 rules 주입만으로 동작하게.", "누적 과금 3명 초과 항공편 4번째 승객부터 허용 무게 5kg 감소해줘."],
        ["규칙을 인터페이스로 분리한 게이트 검사 시스템 구현해줘. PassportRule, FlightStatusRule, LuggageRule, GateManager 전략 패턴으로.", "SAVE", "SecurityRule(BaseRule 상속) 추가해서 threat_level HIGH일 때 SECURITY_CHECK 반환하게 해줘. GateManager는 기존 process() 그대로.", "같은 flight_id에서 과금 3번 나오면 4번째부터 limit -5kg 적용해줘."],
        ["전략 패턴으로 게이트 규칙 구현해줘. 각 규칙은 BaseRule 상속, GateManager가 rules 순회. 여권 만료·항공편 상태·수하물 한도 검사.", "SAVE", "SecurityRule 추가: context.threat_level == HIGH이면 SECURITY_CHECK. GateManager 수정 없이 rules에 SecurityRule 맨 앞으로 넣어줘.", "과금 3명 나온 항공편 4번째부터 허용 무게 5kg 줄여줘."],
    ],
    "B": [
        ["게이트에서 여권 만료, 항공편 상태, 수하물 검사하는 거 구현해줘. 규칙은 나눠서 넣을 수 있게 해줘.", "SAVE", "threat_level이 HIGH면 모든 승객 SECURITY_CHECK로 보내게 해줘. BaseRule 상속하는 SecurityRule 추가하고, GateManager는 기존처럼 rules 순서대로만 돌려줘.", "같은 항공편에서 과금 3명 나오면 그 다음부터 허용 무게 5kg 깎아줘."],
        ["그냥 이거 고쳐서 되게 해줘. 규칙 나눠서 넣을 수 있게만 해줘.", "SAVE", "HIGH일 때 전원 SECURITY_CHECK 보내게 해줘. 과금 3명 나온 항공편은 그 다음부터 허용 5kg 깎아줘."],
        ["게이트 검사 로직 구현해줘. 여권 만료, 항공편, 수하물 무게 검사하고, 규칙은 따로 클래스로 나눠서 확장 가능하게 해줘.", "SAVE", "HIGH일 때 전원 SECURITY_CHECK 보내게 SecurityRule 추가해줘. BaseRule 상속하고, GateManager는 rules 그대로 순서만 돌려줘.", "과금 3명 나온 항공편은 그 다음부터 허용 5kg 깎아줘."],
        ["공항 게이트에서 여권/항공편/수하물 검사하는 거 만들어줘. 규칙은 나눠서 넣을 수 있게만 해줘.", "SAVE", "threat_level HIGH면 다 SECURITY_CHECK로 보내게 해줘. SecurityRule 추가하고 BaseRule 상속, GateManager는 기존처럼 rules만 돌려줘.", "같은 편에서 3명 과금 나오면 다음부터 허용 무게 5kg 줄여줘."],
        ["여권·항공편·수하물 검사하는 게이트 로직 구현해줘. 규칙은 분리해서 넣을 수 있게 해줘.", "SAVE", "위협 수준 HIGH면 전부 SECURITY_CHECK로 보내도록 SecurityRule을 BaseRule 상속해서 추가해줘. GateManager는 rules 순서대로만 실행해줘.", "한 항공편에서 과금 3번 나오면 그다음부터 허용 무게 5kg 감소해줘."],
        ["게이트에서 여권 만료, 항공편 상태, 수하물 검사 구현해줘. 규칙은 나눠서 조합할 수 있게 해줘.", "SAVE", "HIGH면 모두 SECURITY_CHECK 처리하는 SecurityRule 추가해줘. BaseRule 상속, GateManager는 기존 rules 순서 유지해줘.", "3명 과금 나온 항공편은 4번째부터 허용 5kg 깎아줘."],
        ["공항 게이트 여권/항공편/수하물 검사 로직 만들어줘. 규칙은 분리해서 확장 가능하게 해줘.", "SAVE", "threat_level HIGH일 때 전원 SECURITY_CHECK로 보내게 SecurityRule(BaseRule 상속) 추가하고, GateManager는 rules만 순서대로 돌려줘.", "같은 항공편 과금 3명이면 다음부터 허용 무게 -5kg 해줘."],
        ["빨리 기능만 추가해줘. 규칙 나눠서 넣을 수 있게.", "SAVE", "HIGH면 SECURITY_CHECK 보내게 해줘. 과금 3명 나온 편 다음부터 5kg 깎아줘."],
        ["설명 생략하고 구현만 해줘. 게이트 규칙 나눠서.", "SAVE", "SecurityRule 추가해서 HIGH일 때 SECURITY_CHECK. GateManager rules 순서만 유지.", "과금 3명 나온 항공편 4번째부터 -5kg."],
        ["기능만 넣어줘. 규칙 분리, HIGH면 SECURITY_CHECK, 3명 과금 나오면 5kg 감소.", "SAVE", "BaseRule 상속 SecurityRule, GateManager 기존처럼.", "같은 편 3명 과금 다음부터 5kg 깎아줘."],
    ],
    "C": [
        ["공항 게이트 로직 만들어줘. 여권이랑 항공편, 수하물 보고 통과/거절 해줘.", "SAVE", "보안이 HIGH일 때는 다 SECURITY_CHECK로 보내주고, 과금 3번 나온 편은 4번째 사람부터 5kg 빼서 적용해줘. 기존 코드 구조 유지하면서만 넣어줘."],
        ["게이트에서 여권, 항공편, 수하물 검사하는 거 구현해줘.", "SAVE", "위험도 HIGH일 때 전부 SECURITY_CHECK로 보내주고, 3명 과금 나온 편은 4번째 사람부터 5kg 빼서 적용해줘. 기존 구조 유지해줘."],
        ["여권·항공편·수하물 검사하는 게이트 코드 만들어줘.", "SAVE", "보안이 높을 때는 SECURITY_CHECK로 보내고, 과금 많이 나온 편은 4번째부터 5kg 줄여줘. 기존 코드 구조 유지하면서 넣어줘."],
        ["게이트 통과/거절 로직 만들어줘. 여권, 항공편 상태, 수하물 봐줘.", "SAVE", "HIGH일 때 다 SECURITY_CHECK, 과금 3번 나온 편은 그 다음부터 5kg 빼줘. 구조만 유지해서 넣어줘."],
        ["공항 게이트 여권/항공편/수하물 검사 로직 짜줘.", "SAVE", "보안 HIGH면 전부 SECURITY_CHECK로 보내고, 3명 과금 나온 항공편은 4번째부터 허용 5kg 빼줘. 기존 구조 유지해줘."],
        ["게이트 로직 만들어줘. 여권이랑 항공편 수하물 검사.", "SAVE", "위험도 높으면 SECURITY_CHECK로 보내고 과금 3번 나온 편 4번째부터 5kg 빼줘. 기존 구조 유지해줘."],
        ["어떻게 하는지 모르겠는데 게이트 검사 로직 좀 넣어줘. 여권 항공편 수하물.", "SAVE", "보안 HIGH면 SECURITY_CHECK로 보내주고, 과금 많이 나온 편은 4번째부터 5kg 줄여줘."],
        ["보안 규칙 넣는 거 도와줘. 게이트에서 여권 수하물 검사하는 거.", "SAVE", "HIGH일 때 SECURITY_CHECK 보내게 하고, 3명 과금 나온 편 다음부터 5kg 빼줘."],
        ["기능만 되게 해줘. 여권 항공편 수하물 검사, HIGH면 SECURITY_CHECK, 과금 3명 나오면 5kg 감소.", "SAVE", "기존 구조 유지하면서만 넣어줘."],
        ["게이트 검사하는 거 구현해줘. 통과 거절 로직.", "SAVE", "보안 HIGH, 과금 3명 나온 편 4번째부터 5kg 빼줘. 구조 유지해줘."],
    ],
    "D": [
        ["게이트 검사하는 코드 짜줘. 여권, 수하물이랑 관련된 거.", "SAVE", "위험도 높으면 전부 보안 검사로 보내고, 수하물 과금 많이 나온 편은 허용 무게 줄여줘. 기존 거 수정해서 넣어줘."],
        ["보안 좀 강화해봐. 기존 거 수정해서 넣어줘.", "SAVE", "위험 높으면 보안검사로, 과금 많이 나온 편은 무게 줄여줘."],
        ["게이트 검사 코드 만들어줘. 여권이랑 수하물.", "SAVE", "위험도 높으면 전부 보안 검사로, 수하물 과금 많이 나온 편은 허용 무게 줄여줘. 기존 코드 수정해서 넣어줘."],
        ["게이트에서 여권, 수하물 검사하는 거 해줘.", "SAVE", "위험도 높으면 전부 보안 검사로, 수하물 과금 많이 나온 편은 허용 무게 줄여줘. 기존 코드 수정해서 넣어줘."],
        ["게이트 검사 로직 만들어줘. 여권, 수하물.", "SAVE", "높은 위험도면 보안 검사로 보내고, 과금 많이 난 편은 허용 무게 줄여줘. 기존 거 수정해서 넣어줘."],
        ["여권·수하물 검사하는 게이트 코드 해줘.", "SAVE", "위험 높으면 다 보안 검사로, 수하물 과금 많은 편은 무게 제한 줄여줘. 기존 거 고쳐서 넣어줘."],
        ["보안 강화해줘. 기존 거 고쳐서.", "SAVE", "위험 높으면 보안검사로, 과금 많은 편 무게 줄여줘."],
        ["게이트 검사해주는 코드 짜줘. 여권이랑 수하물.", "SAVE", "위험도 높으면 보안 검사로 보내고, 과금 많이 나온 편 허용 무게 줄여줘. 기존 거 수정해서 넣어줘."],
        ["수하물이랑 여권 검사 로직 넣어줘.", "SAVE", "위험 높으면 보안검사, 과금 많으면 무게 줄여줘. 기존 거 수정."],
        ["기존 거 수정해서 보안이랑 과금 규칙 넣어줘.", "SAVE", "위험 높으면 보안 검사로, 과금 많이 나온 편 무게 줄여줘."],
    ],
    "F": [
        ["공항 게이트에서 여권이랑 수하물만 체크하는 거 해줘.", "SAVE", "threat_level HIGH면 그냥 REJECT로 돌려줘. 수하물 많이 나온 항공편은 다음부터 5kg 줄여줘."],
        ["게이트에서 여권, 수하물 체크해줘.", "SAVE", "HIGH면 그냥 거절(REJECT) 시켜. 과금 많이 나온 항공편은 다음부터 무게 5키로 줄여줘."],
        ["여권·수하물만 검사하는 게이트 로직 해줘.", "SAVE", "threat_level HIGH일 때는 REJECT 반환해줘. 수하물 과금 많은 편은 그 다음부터 5kg 제한 줄여줘."],
        ["공항 게이트 여권 수하물만 봐줘.", "SAVE", "HIGH면 그냥 REJECT. 수하물 많이 나온 편 다음부터 5키로 줄여줘."],
        ["게이트 여권이랑 수하물 체크해줘.", "SAVE", "위협 HIGH면 REJECT로 돌려달라. 과금 3번 나온 편은 다음부터 무게 5kg 줄여줘."],
        ["여권 수하물만 체크하는 거 해줘.", "SAVE", "HIGH면 REJECT로 보내줘. 수하물 많이 나온 편 다음부터 5kg 줄여줘."],
        ["게이트에서 여권 수하물만 검사해줘.", "SAVE", "threat_level HIGH면 거절(REJECT) 시켜줘. 과금 3명 나온 편 5kg 줄여줘."],
        ["여권이랑 수하물만 봐주는 게이트 로직.", "SAVE", "HIGH 위협이면 REJECT 반환해줘. 과금 많이 나온 항공편 다음부터 5키로 줄여줘."],
        ["체크해줘 여권 수하물. HIGH면 REJECT.", "SAVE", "과금 많이 나온 편 다음부터 5kg 줄여줘."],
        ["게이트 여권 수하물만. HIGH면 그냥 REJECT 시켜.", "SAVE", "수하물 과금 많은 편 다음부터 무게 5kg 줄여줘."],
    ],
}

# 같은 템플릿이라도 문장 끝에 붙여서 20종 다양화 (variant_index 0..19가 서로 다르게)
INSTRUCTION_SUFFIXES: list[str] = ["", " 부탁해.", " 확인 부탁드려.", " 가능하면 빨리.", " 기존 구조 유지해줘.", " 테스트 통과하게 해줘.", " 한번만 검토해줘.", " 요구사항 그대로 반영해줘.", " 스펙 맞춰줘.", " 잘 부탁해."]


def get_seed_for_grade(grade: str) -> tuple[str, str]:
    """등급에 해당하는 context(v1_code), v2_code 반환."""
    key = GRADE_SEED_MAP[grade]
    seed = SEED_CODES.get(key, {})
    context = (seed.get("v1_code") or seed.get("context") or "").strip()
    v2_code = (seed.get("v2_code") or "").strip()
    if not context and not v2_code:
        context = f"[SEED_{key}_CONTEXT_미설정]"
        v2_code = f"[SEED_{key}_V2_CODE_미설정]"
    return context, v2_code


def get_personas_for_grade(grade: str) -> list[tuple[str, str]]:
    """해당 등급에 적용 가능한 (이름, 설명) 페르소나 목록."""
    return [(name, desc) for name, desc, grades in PERSONAS if grade in grades]


def get_instruction_template_fallback(grade: str, variant_index: int) -> list[str]:
    """LLM 없을 때 등급별 instruction 템플릿 중 하나 반환. variant_index별로 (템플릿, suffix) 조합으로 20종 이상 다양화."""
    templates = GRADE_INSTRUCTION_TEMPLATES.get(grade, GRADE_INSTRUCTION_TEMPLATES["C"])
    n_t = len(templates)
    template_idx = variant_index % n_t
    suffix_idx = (variant_index // n_t) % len(INSTRUCTION_SUFFIXES)
    base = list(templates[template_idx])
    suffix = INSTRUCTION_SUFFIXES[suffix_idx]
    if suffix and base:
        base[0] = (base[0].rstrip(". ") + suffix).strip()
    return base


def _get_llm_flash():
    """Gemini Flash 모델 (빠른 reasoning 생성용)."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.core.config import settings
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return None
    model = getattr(settings, "DEFAULT_LLM_MODEL", "gemini-2.5-flash")
    if "flash" not in model.lower():
        model = "gemini-2.5-flash"
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.3,
        max_output_tokens=512,
    )


async def generate_mock_reasoning(grade: str, instruction: list[str], sem: asyncio.Semaphore) -> tuple[dict[str, Any], str]:
    """Fast-Track: 가상 metrics + Gemini Flash로 LLM이 작성한 듯한 평가 사유(reasoning) 생성."""
    metrics = dict(GRADE_METRICS_TEMPLATE.get(grade, GRADE_METRICS_TEMPLATE["C"]))
    llm = _get_llm_flash()
    if not llm:
        return metrics, GRADE_EVALUATION_LOG.get(grade, "")

    instruction_preview = " | ".join(instruction[:3])[:200] if instruction else ""
    prompt = (
        f"다음 사용자 지시문(스마트 게이트 2026)에 대한 평가 사유를 1~2문장으로만 작성해줘. "
        f"등급: {grade}. 지시문 요약: {instruction_preview}\n"
        "출력은 설명 텍스트만, JSON이나 불릿 없이."
    )

    async with sem:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
            text = (resp.content if hasattr(resp, "content") else str(resp)).strip()
            if text:
                return metrics, text
        except Exception:
            pass
    return metrics, GRADE_EVALUATION_LOG.get(grade, "")


async def generate_instruction_for_grade(grade: str, variant_index: int, sem: asyncio.Semaphore, use_llm: bool) -> list[str]:
    """등급+페르소나에 맞는 instruction (List[str]) 1건 생성. EVOLUTIONS 랜덤 적용 가능."""
    personas = get_personas_for_grade(grade)
    if not personas:
        return get_instruction_template_fallback(grade, variant_index)
    name, desc = random.choice(personas)
    evolution = random.choice(EVOLUTIONS) if EVOLUTIONS and random.random() < 0.3 else ""

    if not use_llm:
        return get_instruction_template_fallback(grade, variant_index)

    llm = _get_llm_flash()
    if not llm:
        return get_instruction_template_fallback(grade, variant_index)

    system = (
        f"당신은 v2.1 코딩 시험 지시문 생성기입니다. 페르소나: {name} — {desc}. "
        "스마트 게이트 2026 문제 기준으로, 사용자가 AI 코딩 도우미에게 할 말을 여러 턴으로 작성해줘. "
        "반드시 JSON 배열 한 줄만 출력. 예: [\"Phase1 요청\", \"SAVE\", \"Phase2 요청1\", \"Phase2 요청2\"]"
    )
    user = "한 줄 JSON 배열만 출력해줘."
    if evolution:
        user = f"마지막 턴에 다음 요구를 자연스럽게 포함해줘: {evolution}\n{user}"

    async with sem:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: llm.invoke(system + "\n\n" + user))
            text = resp.content if hasattr(resp, "content") else str(resp)
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                arr = json.loads(text[start:end])
                if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
                    return [str(x) for x in arr]
        except Exception:
            pass
    return get_instruction_template_fallback(grade, variant_index)


async def generate_data_entry(grade: str, variant_index: int, sem: asyncio.Semaphore, use_llm: bool) -> dict[str, Any]:
    """한 건의 파인튜닝 데이터 생성: Seed Code + 프롬프트 변형 + Fast-Track mock metrics/reasoning."""
    instruction = await generate_instruction_for_grade(grade, variant_index, sem, use_llm)
    context, v2_code = get_seed_for_grade(grade)
    metrics, evaluation_log = await generate_mock_reasoning(grade, instruction, sem)
    return {
        "instruction": instruction,
        "context": context,
        "v2_code": v2_code,
        "metrics": metrics,
        "label": grade,
        "evaluation_log": evaluation_log,
    }


async def run_async_batch(per_grade: int, use_llm: bool, sem_limit: int = 10) -> list[dict[str, Any]]:
    """등급별 per_grade건씩 총 5*per_grade건을 Semaphore로 동시성 제어하며 생성."""
    sem = asyncio.Semaphore(sem_limit)
    grades = ["A", "B", "C", "D", "F"]
    task_specs = [(g, i) for g in grades for i in range(per_grade)]
    total = len(task_specs)

    async def one_with_progress(g: str, i: int):
        rec = await generate_data_entry(g, i, sem, use_llm)
        pbar.update(1)
        return rec

    pbar = tqdm(total=total, desc="생성 중", unit="건")
    tasks = [one_with_progress(g, i) for g, i in task_specs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    pbar.close()

    out = []
    for k, r in enumerate(results):
        if isinstance(r, Exception):
            g, i = task_specs[k]
            out.append(await generate_data_entry(g, i, sem, use_llm=False))
            tqdm.write(f"[WARN] 1건 실패 후 템플릿 폴백: {r}")
        else:
            out.append(r)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="v2.1 파인튜닝 데이터 생성 (Seed & Mutate, Fast-Track)")
    parser.add_argument("-o", "--output", default="data/v21_finetuning_dataset.jsonl", help="출력 JSONL 경로 (기본: data/v21_finetuning_dataset.jsonl)")
    parser.add_argument("--per-grade", type=int, default=20, help="등급당 생성 건수 (기본 20 → 총 100건)")
    parser.add_argument("--no-llm", action="store_true", help="LLM 호출 없이 템플릿만 사용")
    parser.add_argument("--semaphore", type=int, default=10, help="동시 API 호출 수 (기본 10)")
    args = parser.parse_args()

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    use_llm = not args.no_llm
    if use_llm:
        try:
            from app.core.config import settings
            if not getattr(settings, "GEMINI_API_KEY", None):
                use_llm = False
                print("[WARN] GEMINI_API_KEY 없음. --no-llm 모드로 진행합니다.")
        except Exception:
            use_llm = False
            print("[WARN] 설정 로드 실패. 템플릿 폴백으로 진행합니다.")

    records = asyncio.run(run_async_batch(args.per_grade, use_llm, args.semaphore))

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[INFO] 총 {len(records)}건 저장: {out_path}")


if __name__ == "__main__":
    main()

"""
Schneider Electric Innovation Sprint - Problem Statement 1
Deterministic Safety Guardrail Filter

Non-Negotiable Rules 1 & 2:
1. The LLM NEVER outputs a final answer directly to the user. Every LLM response
   passes through a deterministic Guardrail Filter first. If the Guardrail Filter
   rejects it, the user sees a rejection message or the last-known-good fallback —
   never a raw, unchecked model output.
2. The LLM NEVER invents a tag ID, alarm ID, or SOP reference. It may only
   reference IDs that exist in the Machine Context / SOP knowledge base. The
   Guardrail Filter must check every reference against these stores and strip/
   reject anything that doesn't match.
"""

import re
import json
import os
from typing import Dict, Any, List, Set, Tuple

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

class SafetyGuardrailFilter:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.valid_tags: Set[str] = set()
        self.valid_alarms: Set[str] = set()
        self.valid_sops: Set[str] = set()
        self.restricted_actions: Set[str] = set()
        self.restricted_phrases: List[str] = []
        self._load_reference_stores()

    def _load_reference_stores(self):
        # 1. Machine Context (Tags & Alarms)
        mc_file = os.path.join(self.data_dir, "machine_context.json")
        if os.path.exists(mc_file):
            with open(mc_file, "r") as f:
                mc = json.load(f)
            for t in mc.get("tags", []):
                self.valid_tags.add(t["id"])
                if t.get("raw_address"):
                    self.valid_tags.add(t["raw_address"])
            for a in mc.get("alarms", []):
                self.valid_alarms.add(a["id"])

        # Also add cascade alarms from synthetic log if any
        log_file = os.path.join(self.data_dir, "synthetic_logs.json")
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                logs = json.load(f)
            for e in logs:
                if e.get("event_id", "").startswith("ALM-"):
                    self.valid_alarms.add(e["event_id"])
                if e.get("tag_id"):
                    self.valid_tags.add(e["tag_id"])

        # 2. SOPs (SOP IDs & Restricted Actions)
        sop_file = os.path.join(self.data_dir, "sops.json")
        if os.path.exists(sop_file):
            with open(sop_file, "r") as f:
                sops = json.load(f)
            for s in sops:
                self.valid_sops.add(s["sop_id"])
                for ra in s.get("restricted_actions", []):
                    clean_ra = ra.strip().lower()
                    self.restricted_actions.add(clean_ra)
                    # Generate natural language variants
                    spaced_ra = clean_ra.replace("_", " ")
                    self.restricted_phrases.append(spaced_ra)

        # Mandatory plant safety prohibited phrases
        extra_restricted = [
            "override cooling interlock",
            "cooling interlock override",
            "cooling_interlock_override",
            "bypass cooling interlock",
            "override the cooling interlock",
            "bypass interlock",
            "disable interlock",
            "jumper safety",
            "bypass thermal fuse",
            "defeat thermal overload",
            "override relief valve"
        ]
        for r in extra_restricted:
            self.restricted_actions.add(r.lower())
            self.restricted_phrases.append(r.lower())

    def check_restricted_action(self, text: str) -> Tuple[bool, str]:
        """
        Scans text for forbidden / restricted operator actions.
        Returns: (is_prohibited, matched_violation)
        """
        text_lower = text.lower()
        
        # Exact token match
        for ra in self.restricted_actions:
            if ra in text_lower:
                return True, ra

        # Phrase match
        for phrase in self.restricted_phrases:
            if phrase in text_lower:
                return True, phrase

        # Regex heuristic for override/bypass intent
        dangerous_patterns = [
            r"override\s+(?:the\s+)?(?:cooling|safety|thermal|interlock)",
            r"bypass\s+(?:the\s+)?(?:cooling|interlock|safety|relief)",
            r"disable\s+(?:the\s+)?(?:interlock|safety|cooling\s+interlock)"
        ]
        for pat in dangerous_patterns:
            m = re.search(pat, text_lower)
            if m:
                return True, m.group(0)

        return False, ""

    def validate_entities(self, text: str) -> Tuple[bool, List[str], str]:
        """
        Scans text for tag IDs, alarm IDs, and SOP IDs.
        Asserts that EVERY referenced identifier exists in the verified database.
        Returns: (passed, list_of_hallucinations, sanitized_text)
        """
        hallucinations = []
        sanitized_text = text

        # Regex for candidate tags / raw addresses
        # Matches: Tank101_Level_PV, %MW100, %MF200, CV201_Motor_Current, etc.
        tag_candidates = re.findall(r"(?:%[A-Z0-9.]+)|(?:[A-Za-z0-9]+_[A-Za-z0-9_]+)", text)
        for cand in set(tag_candidates):
            # Ignore common non-tag words that happen to have underscores or markdown
            if cand in ["http://", "opc.tcp://", "json_format", "step_num", "error_code"]:
                continue
            # If cand looks like an industrial tag (e.g. contains Tank, CV, Motor, Level, Temp, Press, Flow, Valve, Cmd, PV, SP, MW, MF, QX, IX)
            if any(k in cand for k in ["Tank", "CV", "Motor", "Level", "Temp", "Press", "Flow", "Valve", "Cmd", "PV", "SP", "%", "Alarm", "PE1", "VFD"]):
                if cand not in self.valid_tags:
                    hallucinations.append(f"Tag:{cand}")
                    sanitized_text = sanitized_text.replace(cand, f"[INVALID_TAG_REMOVED:{cand}]")

        # Regex for candidate alarms (ALM-...)
        alarm_candidates = re.findall(r"ALM-[A-Z0-9-]+", text)
        for cand in set(alarm_candidates):
            if cand not in self.valid_alarms:
                hallucinations.append(f"Alarm:{cand}")
                sanitized_text = sanitized_text.replace(cand, f"[INVALID_ALARM_REMOVED:{cand}]")

        # Regex for candidate SOPs (SOP-...)
        sop_candidates = re.findall(r"SOP-[A-Z0-9-]+", text)
        for cand in set(sop_candidates):
            if cand not in self.valid_sops:
                hallucinations.append(f"SOP:{cand}")
                sanitized_text = sanitized_text.replace(cand, f"[INVALID_SOP_REMOVED:{cand}]")

        passed = (len(hallucinations) == 0)
        return passed, hallucinations, sanitized_text

    def filter_response(self, raw_llm_text: str, fallback_message: str = "") -> Dict[str, Any]:
        """
        Deterministic Master Gate:
        Evaluates raw LLM text against Safety & Hallucination Rules.
        """
        # 1. Safety Gate: Restricted Actions Check
        is_restricted, violation = self.check_restricted_action(raw_llm_text)
        if is_restricted:
            return {
                "status": "BLOCKED_SAFETY_VIOLATION",
                "is_safe": False,
                "passed_guardrail": False,
                "violation_detected": violation,
                "confidence_score": 0.0,
                "user_message": (
                    f"[CRITICAL SAFETY INTERLOCK] The action '{violation}' is explicitly prohibited by plant Standard Operating Procedures. "
                    "Bypassing or overriding safety interlocks creates severe equipment damage and personnel hazard. "
                    "ACTION REJECTED. Escalate immediately to Level-3 Shift Safety Supervisor."
                ),
                "action_recommendation": "ESCALATE_TO_SUPERVISOR",
                "source_citations": []
            }

        # 2. Accuracy Gate: Hallucination Check
        passed_entities, hallucinations, sanitized = self.validate_entities(raw_llm_text)
        if not passed_entities:
            return {
                "status": "REJECTED_HALLUCINATION",
                "is_safe": True,
                "passed_guardrail": False,
                "hallucinations_detected": hallucinations,
                "confidence_score": 0.15,
                "user_message": (
                    f"[GUARDRAIL REJECTION] Model output contained unverified industrial identifier(s): {', '.join(hallucinations)}. "
                    "In strict zero-hallucination mode, unverified tag/alarm citations are stripped to protect plant operations."
                ),
                "sanitized_output": sanitized if sanitized else fallback_message,
                "action_recommendation": "USE_FALLBACK_PROCEDURE",
                "source_citations": []
            }

        # 3. Passed all checks
        return {
            "status": "PASSED",
            "is_safe": True,
            "passed_guardrail": True,
            "confidence_score": 0.95,
            "user_message": raw_llm_text,
            "sanitized_output": raw_llm_text,
            "action_recommendation": "PROCEED_WITH_VERIFIED_SOP",
            "source_citations": [sop for sop in self.valid_sops if sop in raw_llm_text]
        }

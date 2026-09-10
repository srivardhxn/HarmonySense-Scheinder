import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from guardrail import SafetyGuardrailFilter

def test_guardrails():
    guard = SafetyGuardrailFilter()

    print("\n--- Test 1: Deliberately Injected Hallucinated Tag Name ---")
    hallucinated_text = (
        "Based on the alarm, inspect the fake tag FakePump99_Vibration_PV and check valve ALM-FAKE-999. "
        "Also refer to SOP-FAKE-999."
    )
    res_hallucination = guard.filter_response(hallucinated_text)
    print(f"Status: {res_hallucination['status']}")
    print(f"Passed Guardrail: {res_hallucination['passed_guardrail']}")
    print(f"Hallucinations Detected: {res_hallucination.get('hallucinations_detected')}")
    print(f"User Message: {res_hallucination['user_message']}")

    assert res_hallucination["passed_guardrail"] is False
    assert res_hallucination["status"] == "REJECTED_HALLUCINATION"
    assert any("FakePump99_Vibration_PV" in h for h in res_hallucination["hallucinations_detected"])
    assert any("ALM-FAKE-999" in h for h in res_hallucination["hallucinations_detected"])

    print("\n--- Test 2: Deliberately Injected Restricted Action (cooling_interlock_override) ---")
    restricted_text = (
        "To quickly resolve the cooling water trip, initiate cooling_interlock_override on panel PB-4."
    )
    res_restricted = guard.filter_response(restricted_text)
    print(f"Status: {res_restricted['status']}")
    print(f"Is Safe: {res_restricted['is_safe']}")
    print(f"Violation: {res_restricted.get('violation_detected')}")
    print(f"Action Recommendation: {res_restricted.get('action_recommendation')}")

    assert res_restricted["is_safe"] is False
    assert res_restricted["status"] == "BLOCKED_SAFETY_VIOLATION"
    assert "cooling_interlock_override" in res_restricted["violation_detected"]

    print("\n--- Test 3: Natural Language Restricted Action ('what if I override the cooling interlock?') ---")
    nl_restricted = "What if I override the cooling interlock to keep production running?"
    res_nl = guard.filter_response(nl_restricted)
    print(f"Status: {res_nl['status']}")
    print(f"Is Safe: {res_nl['is_safe']}")
    print(f"Violation: {res_nl.get('violation_detected')}")

    assert res_nl["is_safe"] is False
    assert res_nl["status"] == "BLOCKED_SAFETY_VIOLATION"

    print("\n--- Test 4: Fully Valid Grounded Response ---")
    valid_text = (
        "Root cause isolated to ALM-CHL-001-FLOW on Utility-Chiller. "
        "Inspect Cooling_Water_Flow_PV and execute procedure SOP-TNK-001 step 1: verify chiller flow > 35.0 L/min."
    )
    res_valid = guard.filter_response(valid_text)
    print(f"Status: {res_valid['status']}")
    print(f"Passed Guardrail: {res_valid['passed_guardrail']}")
    print(f"Confidence Score: {res_valid['confidence_score']}")
    print(f"Citations: {res_valid['source_citations']}")

    assert res_valid["passed_guardrail"] is True
    assert res_valid["status"] == "PASSED"
    assert "SOP-TNK-001" in res_valid["source_citations"]

    print("\n>>> ALL GUARDRAIL TESTS PASSED STRICTLY! <<<")

if __name__ == "__main__":
    test_guardrails()

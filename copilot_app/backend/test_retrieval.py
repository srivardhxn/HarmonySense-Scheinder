import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from retrieval import SOPRetrievalEngine

def test_retrieval():
    engine = SOPRetrievalEngine()

    print("\n--- Test 1: Verified Alarm Retrieval (ALM-CHL-001-FLOW) ---")
    res1 = engine.retrieve_sop_for_cluster("ALM-CHL-001-FLOW", "Cooling_Water_Flow_PV")
    print(f"Matched: {res1['matched']}")
    print(f"SOP ID: {res1.get('sop_id')}")
    print(f"Title: {res1.get('sop_title')}")
    print(f"Confidence: {res1.get('confidence_score')} ({res1.get('confidence_level')})")
    print(f"Steps Retrieved: {len(res1.get('steps', []))}")
    print(f"Restricted Actions: {res1.get('restricted_actions')}")

    assert res1["matched"] is True
    assert res1["sop_id"] == "SOP-TNK-001"
    assert res1["confidence_level"] == "high"
    assert len(res1["steps"]) > 0
    assert "cooling_interlock_override" in res1["restricted_actions"]

    print("\n--- Test 2: Ambiguous Tag Query (%MW100) ---")
    tag_res = engine.lookup_tag_confidence("%MW100")
    print(f"Tag Match: {tag_res['match_found']}")
    print(f"Confidence Level: {tag_res['confidence_level']}")
    print(f"Confidence Score: {tag_res['confidence_score']}")
    print(f"Message: {tag_res['message']}")

    assert tag_res["match_found"] is True
    assert tag_res["confidence_level"] == "low"
    assert tag_res["confidence_score"] < 0.5

    # Also test retrieve_sop_for_cluster with %MW100
    res2 = engine.retrieve_sop_for_cluster("ALM-UNKNOWN", "%MW100")
    print(f"Cluster Retrieval for %MW100 Matched: {res2['matched']}")
    print(f"Cluster Confidence Level: {res2['confidence_level']}")
    print(f"Reason: {res2['reason']}")

    assert res2["matched"] is False
    assert res2["confidence_level"] == "low"
    assert "Ambiguous" in res2["reason"] or "low" in res2["reason"].lower()

    print("\n--- Test 3: Completely Non-Existent Fake Tag ---")
    fake_res = engine.lookup_tag_confidence("Fake_Unknown_Tag_999")
    print(f"Fake Tag Match: {fake_res['match_found']}")
    assert fake_res["match_found"] is False

    print("\n>>> ALL RETRIEVAL UNIT TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_retrieval()

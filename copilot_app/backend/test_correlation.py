import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from correlation import AlarmCorrelationEngine, PROTECTED_ASSETS

def test_alarm_storm_correlation():
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_logs.json"))
    with open(data_path, "r") as f:
        events = json.load(f)

    # Filter out only alarms from the 10:14 storm
    storm_alarms = [
        e for e in events 
        if e.get("type") == "ALARM" and "10:14:2" in e["timestamp"]
    ]

    print(f"[TEST 1] Total raw alarms during storm window: {len(storm_alarms)}")
    assert len(storm_alarms) >= 30, f"Expected 30+ raw alarms, found {len(storm_alarms)}"

    engine = AlarmCorrelationEngine(burst_window_seconds=3.0)
    
    # 1. Test correlation scoped explicitly to the 4 protected subsystems
    clusters = engine.correlate_events(storm_alarms, allowed_assets=PROTECTED_ASSETS)

    print(f"[TEST 1] Collapsed {len(storm_alarms)} raw alarms into {len(clusters)} cluster(s) with PROTECTED_ASSETS scoping!")
    for idx, c in enumerate(clusters):
        cd = c.to_dict()
        print(f"  Cluster {idx+1}: ID={cd['cluster_id']} Root={cd['root_trigger_alarm_id']} ({cd['root_tag']}) "
              f"PrimaryAsset={cd['primary_asset']} TotalAlarms={cd['total_alarms_count']} "
              f"SuppressedCascades={cd['suppressed_cascading_count']}")

    assert 1 <= len(clusters) <= 4, f"Expected 1 to 4 clusters, got {len(clusters)}"
    primary_cluster = clusters[0].to_dict()
    assert primary_cluster["root_trigger_alarm_id"] == "ALM-CHL-001-FLOW", (
        f"Expected root cause ALM-CHL-001-FLOW, got {primary_cluster['root_trigger_alarm_id']}"
    )
    assert primary_cluster["primary_asset"] == "Utility-Chiller"
    assert primary_cluster["total_alarms_count"] >= 10

    # 2. Test Subsystem 5 (Primary-Heat-Exchanger) isolation (Question 2 verification)
    sub5_alarm = {
        "event_id": "ALM-HX-101-CAVIT",
        "timestamp": "2026-09-10T10:14:19.800Z",
        "type": "ALARM",
        "priority": "CRITICAL",
        "source": "Primary-Heat-Exchanger",
        "tag_id": "HX_Pump101_Vibration_PV",
        "condition": "HIGH_HIGH_CAVITATION",
        "message": "Primary Chiller Pump P-101 Cavitation & Suction Strainer Starvation (Root Failure)",
        "status": "UNACKNOWLEDGED"
    }

    # Isolated correlation for Subsystem 5
    sub5_clusters = engine.correlate_events([sub5_alarm], allowed_assets={"Primary-Heat-Exchanger"})
    print(f"\n[TEST 2] Subsystem 5 Isolated Correlation: {len(sub5_clusters)} cluster(s) generated without crash.")
    assert len(sub5_clusters) == 1
    assert sub5_clusters[0].primary_asset == "Primary-Heat-Exchanger"
    assert sub5_clusters[0].root_trigger_alarm_id == "ALM-HX-101-CAVIT"

    # Leakage test: Subsystem 5 alarm passed into protected asset scope must yield 0 clusters
    leaked = engine.correlate_events([sub5_alarm], allowed_assets=PROTECTED_ASSETS)
    print(f"[TEST 3] Subsystem 5 Zero-Leakage Test: {len(leaked)} clusters produced when scoped to PROTECTED_ASSETS.")
    assert len(leaked) == 0, "Subsystem 5 alarm leaked into protected subsystems!"

    print("\n>>> ALL CORRELATION UNIT TESTS PASSED SUCCESSFULLY! ZERO LEAKAGE CONFIRMED. <<<")

if __name__ == "__main__":
    test_alarm_storm_correlation()

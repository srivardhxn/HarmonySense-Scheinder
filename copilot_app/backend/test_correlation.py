import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from correlation import AlarmCorrelationEngine

def test_alarm_storm_correlation():
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_logs.json"))
    with open(data_path, "r") as f:
        events = json.load(f)

    # Filter out only alarms from the 10:14 storm
    storm_alarms = [
        e for e in events 
        if e.get("type") == "ALARM" and "10:14:2" in e["timestamp"]
    ]

    print(f"[TEST] Total raw alarms during storm window: {len(storm_alarms)}")
    assert len(storm_alarms) >= 30, f"Expected 30+ raw alarms, found {len(storm_alarms)}"

    engine = AlarmCorrelationEngine(burst_window_seconds=3.0)
    clusters = engine.correlate_events(storm_alarms)

    print(f"[TEST] Collapsed {len(storm_alarms)} raw alarms into {len(clusters)} cluster(s)!")
    for idx, c in enumerate(clusters):
        cd = c.to_dict()
        print(f"  Cluster {idx+1}: ID={cd['cluster_id']} Root={cd['root_trigger_alarm_id']} ({cd['root_tag']}) "
              f"PrimaryAsset={cd['primary_asset']} TotalAlarms={cd['total_alarms_count']} "
              f"SuppressedCascades={cd['suppressed_cascading_count']}")

    # Assertions
    assert 1 <= len(clusters) <= 3, f"Expected 1 to 3 clusters, got {len(clusters)}"
    primary_cluster = clusters[0].to_dict()
    assert primary_cluster["root_trigger_alarm_id"] == "ALM-CHL-001-FLOW", (
        f"Expected root cause ALM-CHL-001-FLOW, got {primary_cluster['root_trigger_alarm_id']}"
    )
    assert primary_cluster["primary_asset"] == "Utility-Chiller"
    assert primary_cluster["total_alarms_count"] >= 30

    print("\n>>> ALL CORRELATION UNIT TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_alarm_storm_correlation()

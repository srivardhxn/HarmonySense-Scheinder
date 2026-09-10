"""
Schneider Electric Innovation Sprint - Problem Statement 1
Deterministic Rule-Based Alarm Correlation Engine (ISA-18.2 First-Out & ISA-95 Hierarchy)

Non-Negotiable Rule 3:
Alarm correlation (grouping alarms into clusters) is RULE-BASED CODE, not the LLM.
The LLM only receives already-clustered events, never a raw flood.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
import uuid

# The 4 Protected Industrial Subsystems:
# 1. Buffer Vessel Tank 101: Tank-101
# 2. Chiller Cooling Circuit: Utility-Chiller
# 3. Infeed Conveyor Line 201: Conveyor-201, VFD-Inverter
# 4. Plant Utilities & Raw Register: Safety-Grid, Line-01, Plant-Utilities, PLC-Internal
PROTECTED_ASSETS = {
    "Utility-Chiller",
    "Tank-101",
    "Conveyor-201",
    "VFD-Inverter",
    "Safety-Grid",
    "Line-01",
    "Plant-Utilities",
    "PLC-Internal"
}

# ISA-95 Equipment Subsystem Boundaries
# Each physical equipment module groups its own internal cascading sensor alarms:
# - Utility-Chiller: Flow, supply valve, secondary return, chiller bypass
# - Tank-101: Temperature, headspace pressure, ultrasonic level, agitator speed
# - Conveyor-201: Optical jam PE1, belt slip, motor current, mechanical drag
# - VFD-Inverter: Altivar inverter IGBT overcurrent, DC bus voltage, thermal fault
# - Safety-Grid: Master dual-channel E-Stop relay, pneumatic safety dump valve
# - Primary-Heat-Exchanger: 5th subsystem isolated from 4 protected subsystems
ASSET_TOPOLOGY = {
    "Primary-Heat-Exchanger": [],
    "Utility-Chiller": ["Tank-101", "Conveyor-201", "VFD-Inverter", "Safety-Grid", "Line-01"],
    "Tank-101": ["Conveyor-201", "VFD-Inverter", "Safety-Grid", "Line-01"],
    "Conveyor-201": ["VFD-Inverter", "Safety-Grid", "Line-01"],
    "VFD-Inverter": ["Safety-Grid", "Line-01"],
    "Safety-Grid": ["Line-01"],
    "Line-01": []
}

def parse_iso_ts(ts_str: str) -> datetime:
    # Clean ISO format
    ts_clean = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(ts_clean)

class AlarmCluster:
    def __init__(self, cluster_id: str, root_event: Dict[str, Any]):
        self.cluster_id = cluster_id
        self.start_time = root_event["timestamp"]
        self.end_time = root_event["timestamp"]
        self.primary_asset = root_event.get("source", "Unknown")
        self.root_trigger = root_event
        self.root_trigger_alarm_id = root_event.get("event_id")
        self.root_tag = root_event.get("tag_id")
        self.severity = root_event.get("priority", "HIGH")
        self.cascading_alarms: List[Dict[str, Any]] = []
        self.affected_assets = {self.primary_asset}
        self.status = root_event.get("status", "ACTIVE")

    def add_cascade(self, event: Dict[str, Any]):
        self.cascading_alarms.append(event)
        self.end_time = event["timestamp"]
        self.affected_assets.add(event.get("source", "Unknown"))
        # Elevate severity if cascade has critical
        if event.get("priority") == "CRITICAL":
            self.severity = "CRITICAL"

    @property
    def total_alarms_count(self) -> int:
        return 1 + len(self.cascading_alarms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "primary_asset": self.primary_asset,
            "affected_assets": sorted(list(self.affected_assets)),
            "root_trigger_alarm_id": self.root_trigger_alarm_id,
            "root_tag": self.root_tag,
            "root_message": self.root_trigger.get("message", ""),
            "severity": self.severity,
            "total_alarms_count": self.total_alarms_count,
            "suppressed_cascading_count": len(self.cascading_alarms),
            "cascading_alarm_ids": [a.get("event_id") for a in self.cascading_alarms],
            "status": self.status,
            "summary_title": f"[{self.severity}] {self.primary_asset} First-Out Trip: {self.root_trigger_alarm_id} ({self.total_alarms_count} alarms collapsed)"
        }

class AlarmCorrelationEngine:
    def __init__(self, burst_window_seconds: float = 3.5):
        """
        burst_window_seconds: Sliding burst window for grouping cascading symptoms.
        Standard ISA-18.2 recommends 2.0 to 5.0 seconds for physical plant trips.
        """
        self.burst_window = timedelta(seconds=burst_window_seconds)

    def correlate_events(
        self, 
        raw_events: List[Dict[str, Any]], 
        allowed_assets: Optional[Set[str]] = None
    ) -> List[AlarmCluster]:
        """
        Groups raw alarm events into clusters using First-Out time sorting and asset topological coupling.
        If allowed_assets is provided, strictly scopes correlation to those assets only,
        preventing foreign or un-scoped subsystem alarms from leaking into clusters.
        Non-alarm events (PROCESS, OPERATOR_ACTION) are ignored by the alarm correlator.
        """
        # Filter for active alarms only, scoped by allowed_assets if specified
        alarm_events = [
            e for e in raw_events 
            if e.get("type") == "ALARM" and (allowed_assets is None or e.get("source") in allowed_assets)
        ]
        if not alarm_events:
            return []

        # Ensure strict chronological sorting by timestamp (t0 first)
        sorted_alarms = sorted(alarm_events, key=lambda x: parse_iso_ts(x["timestamp"]))

        clusters: List[AlarmCluster] = []

        for alarm in sorted_alarms:
            alarm_ts = parse_iso_ts(alarm["timestamp"])
            alarm_source = alarm.get("source", "Unknown")

            matched_cluster: Optional[AlarmCluster] = None

            # Check if this alarm belongs to any existing open cluster
            for cluster in clusters:
                cluster_end_ts = parse_iso_ts(cluster.end_time)
                time_delta = alarm_ts - cluster_end_ts

                # Must be within sliding burst window
                if time_delta <= self.burst_window:
                    # Must have topological asset coupling or shared line
                    if (alarm_source == cluster.primary_asset or 
                        alarm_source in cluster.affected_assets or
                        alarm_source in ASSET_TOPOLOGY.get(cluster.primary_asset, []) or
                        any(alarm_source in ASSET_TOPOLOGY.get(a, []) for a in cluster.affected_assets)):
                        matched_cluster = cluster
                        break

            if matched_cluster:
                matched_cluster.add_cascade(alarm)
            else:
                # Initiate a new cluster with First-Out root trigger at t0
                new_id = f"CLU-{str(uuid.uuid4())[:8].upper()}"
                clusters.append(AlarmCluster(new_id, alarm))

        return clusters

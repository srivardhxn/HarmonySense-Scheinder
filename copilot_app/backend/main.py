"""
Schneider Electric Innovation Sprint - Problem Statement 1
FastAPI Backend & Mock OPC UA / Modbus TCP WebSocket Server

Endpoints:
- /explain       : Alarm event -> Deterministic Retrieval + Edge SLM + Guardrail Filter
- /handover      : Multi-hour shift log + session events -> Structured Handover Summary
- /whatif        : Proposed operator action -> Safety Interlock & Restricted Action Check
- /trigger_storm : Dynamic 1-100 Alarm Storm Generator & ISA-18.2 Correlation
- /setpoint      : Live operator setpoint change -> updates live state & session history
- /ws/live       : High-frequency live PLC tag stream (16 tags, OPC UA / Modbus TCP simulation)
"""

import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Internal modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from correlation import AlarmCorrelationEngine, parse_iso_ts
from retrieval import SOPRetrievalEngine
from guardrail import SafetyGuardrailFilter
from llm_service import EdgeLLMService
from chaos_sandbox import chaos_router

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = FastAPI(
    title="Schneider Electric Industrial Copilot API",
    description="Edge-Native Runtime Copilot for Industrial HMI (Air-Gapped)",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Chaos & What-If Sandbox Subsystem Router
app.include_router(chaos_router)

# Initialize engines
correlator = AlarmCorrelationEngine(burst_window_seconds=3.5)
retriever = SOPRetrievalEngine()
guardrail = SafetyGuardrailFilter()
llm_service = EdgeLLMService()

# 16 Comprehensive Industrial PLC Tags across 4 Subsystems
live_state = {
    "tags": {
        # Subsystem 1: Buffer Tank 101
        "Tank101_Level_PV": 48.6,
        "Tank101_Temp_PV": 63.2,
        "Tank101_Pressure_PV": 2.2,
        "Tank101_Agitator_Speed_PV": 280.0,
        "Tank101_Inlet_Valve_Cmd": 1,
        "Tank101_Discharge_Pump_Cmd": 1,
        
        # Subsystem 2: Chiller Cooling Loop
        "Cooling_Water_Flow_PV": 42.5,
        "Chiller_Return_Temp_PV": 18.5,
        "Cooling_Interlock_Status": 1,
        
        # Subsystem 3: Infeed Conveyor 201
        "CV201_Belt_Speed_PV": 1.85,
        "CV201_Motor_Current": 14.8,
        "CV201_Jam_Detect_PE1": 0,
        "CV201_VFD_Fault_Code": 0,
        
        # Subsystem 4: Plant Utilities & Modbus Registers
        "Line01_EStop_Relay_Status": 1,
        "Air_Pressure_Supply_PV": 6.4,
        "%MW100": 1042
    },
    "active_alarms": [],
    "recent_clusters": [],
    "storm_in_progress": False,
    "storm_alarm_count": 0,
    "session_events": []
}

# --- Request / Response Models ---
class ExplainRequest(BaseModel):
    alarm_id: str
    tag_id: Optional[str] = None
    source_asset: Optional[str] = None
    force_failure: bool = False

class WhatIfRequest(BaseModel):
    proposed_action: str

class TriggerStormRequest(BaseModel):
    alarm_count: int = 34

class SetpointRequest(BaseModel):
    tag_id: str
    new_value: float
    operator: str = "Current Operator"

class HandoverRequest(BaseModel):
    window_hours: float = 8.0
    outgoing_operator: str = "M. Dubois (Shift A)"
    incoming_operator: str = "J. Moreau (Shift B)"
    shift_name: str = "Day Shift (06:00 - 14:00)"

# --- API Endpoints ---

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "mode": "100% AIR-GAPPED OFFLINE",
        "ollama_connected": llm_service.is_ollama_available(),
        "database": "SQLite FTS5 (BM25)",
        "guardrail_engine": "Deterministic Whitelist & Interlock Regex",
        "monitored_tags_count": len(live_state["tags"]),
        "active_clusters": len(live_state["recent_clusters"])
    }

@app.get("/api/machine_context")
def get_machine_context():
    with open(os.path.join(DATA_DIR, "machine_context.json"), "r") as f:
        return json.load(f)

@app.get("/api/sops")
def get_sops():
    with open(os.path.join(DATA_DIR, "sops.json"), "r") as f:
        return json.load(f)

@app.post("/api/explain")
def explain_alarm(req: ExplainRequest):
    """
    Full pipeline:
    Alarm Cluster -> FTS5 BM25 SOP Retrieval -> Edge SLM -> Guardrail Filter
    """
    # 1. Edge Case: Ambiguous / Raw Address Tag (%MW100)
    if req.tag_id == "%MW100" or "%MW" in req.alarm_id:
        tag_conf = retriever.lookup_tag_confidence("%MW100")
        return {
            "alarm_id": req.alarm_id,
            "root_cause_explanation": (
                "LOW CONFIDENCE ADVISORY: The referenced tag '%MW100' is an unmapped legacy Modbus memory word. "
                "In strict industrial safety compliance, the copilot will NOT guess symbolic meaning or plant role. "
                "Consult electrical schematic and register allocation table in EcoStruxure Machine Expert before proceeding."
            ),
            "recommended_steps": [
                {"step": 1, "instruction": "Verify raw PLC holding register %MW100 against master I/O allocation table."},
                {"step": 2, "instruction": "Map symbolic tag in EcoStruxure Operator Terminal Expert dictionary."}
            ],
            "confidence_score": 0.35,
            "confidence_level": "low",
            "sop_citation": "UNMAPPED_RAW_REGISTER_ADVISORY",
            "guardrail_status": "FLAGGED_AMBIGUOUS_TAG",
            "safety_interlock_verified": True,
            "engine_used": "Deterministic Rule (Ambiguous Tag Trap)"
        }

    # 2. Rule-Based SOP Retrieval via SQLite FTS5 (BM25)
    sop_result = retriever.retrieve_sop_for_cluster(req.alarm_id, req.tag_id)

    # 3. Formulate Cluster Context for SLM
    cluster_ctx = {
        "root_trigger_alarm_id": req.alarm_id,
        "primary_asset": req.source_asset or "Equipment-Module",
        "root_tag": req.tag_id or "Monitored_PV",
        "root_message": f"Process threshold exceeded on {req.tag_id or req.alarm_id}",
        "total_alarms_count": live_state.get("storm_alarm_count", 1) or 1,
        "suppressed_cascading_count": max(0, (live_state.get("storm_alarm_count", 1) or 1) - 2)
    }

    # 4. Edge SLM Generation (Ollama or Offline Edge Engine)
    llm_res = llm_service.generate_explanation(cluster_ctx, sop_result, force_failure=req.force_failure)

    # 5. Edge Case: LLM Timeout / Failure Fallback Handling
    if not llm_res.get("success"):
        return {
            "alarm_id": req.alarm_id,
            "root_cause_explanation": (
                "[INSUFFICIENT DATA - ESCALATE TO OPERATOR] "
                f"The AI inference engine experienced a timeout or connection failure ({llm_res.get('error')}). "
                f"Falling back to verified hardcoded SOP procedure for {req.alarm_id}."
            ),
            "recommended_steps": sop_result.get("steps", [
                {"step": 1, "instruction": "Check physical sensor reading on local panel."},
                {"step": 2, "instruction": "Escalate to control room supervisor."}
            ]),
            "confidence_score": 0.50,
            "confidence_level": "fallback",
            "sop_citation": sop_result.get("citation", "PLANT-EMERGENCY-SOP"),
            "guardrail_status": "FALLBACK_ENGAGED",
            "safety_interlock_verified": True,
            "engine_used": "Last-Known-Good Fallback Engine"
        }

    # 6. Non-Negotiable: Pass through Deterministic Safety Guardrail Filter
    raw_output = llm_res.get("raw_output", "")
    guard_res = guardrail.filter_response(raw_output, fallback_message="Follow standard plant LOTO protocol.")

    return {
        "alarm_id": req.alarm_id,
        "root_cause_explanation": guard_res["user_message"],
        "recommended_steps": sop_result.get("steps", []),
        "confidence_score": guard_res["confidence_score"],
        "confidence_level": "high" if guard_res["passed_guardrail"] else "blocked",
        "sop_citation": sop_result.get("citation", "SOP-VERIFIED"),
        "guardrail_status": guard_res["status"],
        "safety_interlock_verified": guard_res["is_safe"],
        "engine_used": llm_res.get("engine", "Edge SLM")
    }

@app.post("/api/whatif")
def simulate_whatif(req: WhatIfRequest):
    """
    Safety Sandbox: Evaluates proposed operator action against restricted actions & safety rules.
    """
    action = req.proposed_action.strip()

    # Pass through Safety Guardrail Filter
    is_restricted, violation = guardrail.check_restricted_action(action)

    if is_restricted:
        event = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "type": "SAFETY_GATE_TRIGGERED",
            "action": action,
            "verdict": "BLOCKED"
        }
        live_state["session_events"].append(event)
        return {
            "allowed": False,
            "verdict": "BLOCKED_SAFETY_VIOLATION",
            "risk_level": "CRITICAL",
            "violation_detected": violation,
            "message": (
                f"[CRITICAL SAFETY GATE] Action '{violation}' is strictly restricted by plant safety policy. "
                "Automated bypass/override of interlocks causes high risk of thermal runaway, vessel rupture, or motor burnout. "
                "ACTION PROHIBITED. Requires Level-3 Engineering Safety authorization."
            ),
            "escalation_required": True
        }

    return {
        "allowed": True,
        "verdict": "PERMITTED_STANDARD_ACTION",
        "risk_level": "LOW",
        "violation_detected": None,
        "message": (
            f"Action '{action}' is within standard operating parameters. "
            "Proceed following standard plant verification and double-check setpoint tolerances."
        ),
        "escalation_required": False
    }

@app.post("/api/setpoint")
def update_setpoint(req: SetpointRequest):
    """
    Allows the operator to adjust a setpoint, updating live PLC memory and logging to shift history.
    """
    if req.tag_id in live_state["tags"]:
        old_val = live_state["tags"][req.tag_id]
        live_state["tags"][req.tag_id] = req.new_value
        event = {
            "event_id": f"OP-ACT-{int(time.time())}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "type": "OPERATOR_ACTION",
            "operator": req.operator,
            "tag_id": req.tag_id,
            "message": f"Operator modified {req.tag_id} from {old_val} to {req.new_value}",
            "source": "HMI-Operator-Console"
        }
        live_state["session_events"].append(event)
        return {
            "success": True,
            "tag_id": req.tag_id,
            "old_value": old_val,
            "new_value": req.new_value,
            "message": f"Setpoint {req.tag_id} successfully written to PLC memory."
        }
    raise HTTPException(status_code=404, detail="Tag not found in live state")

@app.post("/api/trigger_storm")
def trigger_alarm_storm_simulation(req: Optional[TriggerStormRequest] = None):
    """
    Dynamic 1 to 100 Alarm Storm Generator & ISA-18.2 Correlation.
    Allows the tester to choose ANY number of alarms (1-100) and observe dynamic collapse.
    """
    count = req.alarm_count if (req and req.alarm_count) else 34
    count = max(1, min(100, count))

    live_state["storm_in_progress"] = True
    live_state["storm_alarm_count"] = count

    # Scale process disturbance dynamically based on chosen alarm storm count
    ratio = count / 100.0
    live_state["tags"]["Cooling_Water_Flow_PV"] = round(max(0.5, 42.5 - 40.5 * ratio), 1)
    live_state["tags"]["Cooling_Interlock_Status"] = 0 if count >= 10 else 1
    live_state["tags"]["Tank101_Temp_PV"] = round(63.2 + 28.5 * ratio, 1)
    live_state["tags"]["Tank101_Pressure_PV"] = round(2.2 + 5.6 * ratio, 2)
    live_state["tags"]["Chiller_Return_Temp_PV"] = round(18.5 + 23.5 * ratio, 1)
    live_state["tags"]["Tank101_Agitator_Speed_PV"] = round(max(0.0, 280.0 - 150.0 * ratio), 0)

    if count >= 45:
        live_state["tags"]["CV201_Jam_Detect_PE1"] = 1
        live_state["tags"]["CV201_Belt_Speed_PV"] = round(max(0.0, 1.85 - 1.85 * ratio), 2)
        live_state["tags"]["CV201_Motor_Current"] = round(14.8 + 12.0 * ratio, 1)
        live_state["tags"]["CV201_VFD_Fault_Code"] = 402  # Overcurrent trip
    if count >= 80:
        live_state["tags"]["Line01_EStop_Relay_Status"] = 0 # Full line safety trip

    # Build alarms realistically partitioned across physical plant subsystems
    generated_alarms = []
    
    # 1. Base Root: Utility Chiller Flow Loss (Always present)
    chiller_count = min(count, 22 if count > 20 else count)
    generated_alarms.append({
        "event_id": "ALM-CHL-001-FLOW",
        "timestamp": "2026-09-10T10:14:20.100Z",
        "type": "ALARM",
        "priority": "CRITICAL",
        "source": "Utility-Chiller",
        "tag_id": "Cooling_Water_Flow_PV",
        "condition": "LOW_LOW",
        "message": "Cooling Water Supply Loss - Flow dropped to 2.1 L/min (Root Trigger)",
        "status": "UNACKNOWLEDGED"
    })
    for i in range(1, chiller_count):
        generated_alarms.append({
            "event_id": f"ALM-CHL-{i:03d}-SUB",
            "timestamp": f"2026-09-10T10:14:20.{120 + i*15:03d}Z",
            "type": "ALARM",
            "priority": "HIGH" if i < 3 else "MEDIUM",
            "source": "Utility-Chiller",
            "tag_id": "Chiller_Return_Temp_PV" if i % 2 == 0 else "Cooling_Interlock_Status",
            "condition": "FLOW_DEVIATION",
            "message": f"Chiller secondary loop disturbance #{i}",
            "status": "UNACKNOWLEDGED"
        })

    # 2. Subsystem 2: Tank 101 Thermal Cascade (Engaged when count >= 21)
    if count >= 21:
        tank_count = min(count - len(generated_alarms), 20 if count >= 46 else count - len(generated_alarms))
        generated_alarms.append({
            "event_id": "ALM-TNK-102-THH",
            "timestamp": "2026-09-10T10:14:20.650Z",
            "type": "ALARM",
            "priority": "CRITICAL",
            "source": "Tank-101",
            "tag_id": "Tank101_Temp_PV",
            "condition": "HIGH_HIGH",
            "message": "Tank 101 Core Temperature Exceeded 85.0°C (Runaway Risk)",
            "status": "UNACKNOWLEDGED"
        })
        for i in range(1, tank_count):
            generated_alarms.append({
                "event_id": f"ALM-TNK-{i:03d}-PRESS",
                "timestamp": f"2026-09-10T10:14:20.{700 + i*10:03d}Z",
                "type": "ALARM",
                "priority": "HIGH" if i < 4 else "MEDIUM",
                "source": "Tank-101",
                "tag_id": "Tank101_Pressure_PV" if i % 2 == 0 else "Tank101_Level_PV",
                "condition": "OVERPRESSURE_WARNING",
                "message": f"Tank 101 headspace pressure/level surge #{i}",
                "status": "UNACKNOWLEDGED"
            })

    # 3. Subsystem 3: Conveyor 201 Mechanical Jam (Engaged when count >= 46)
    if count >= 46:
        cv_count = min(count - len(generated_alarms), 20 if count >= 71 else count - len(generated_alarms))
        generated_alarms.append({
            "event_id": "ALM-CV-201-JAM",
            "timestamp": "2026-09-10T10:14:21.050Z",
            "type": "ALARM",
            "priority": "HIGH",
            "source": "Conveyor-201",
            "tag_id": "CV201_Jam_Detect_PE1",
            "condition": "JAM_DETECTED",
            "message": "Conveyor 201 Infeed Optical Jam Sensor PE1 Blocked > 2.0s",
            "status": "UNACKNOWLEDGED"
        })
        for i in range(1, cv_count):
            generated_alarms.append({
                "event_id": f"ALM-CV-201-SPD-{i:02d}",
                "timestamp": f"2026-09-10T10:14:21.{100 + i*12:03d}Z",
                "type": "ALARM",
                "priority": "MEDIUM",
                "source": "Conveyor-201",
                "tag_id": "CV201_Belt_Speed_PV",
                "condition": "SPEED_DROP",
                "message": f"Conveyor 201 belt slip and motor deceleration #{i}",
                "status": "UNACKNOWLEDGED"
            })

    # 4. Subsystem 4: VFD Inverter Electrical Trip (Engaged when count >= 71)
    if count >= 71:
        vfd_count = min(count - len(generated_alarms), 18 if count >= 90 else count - len(generated_alarms))
        generated_alarms.append({
            "event_id": "ALM-CV-201-OC",
            "timestamp": "2026-09-10T10:14:21.350Z",
            "type": "ALARM",
            "priority": "CRITICAL",
            "source": "VFD-Inverter",
            "tag_id": "CV201_Motor_Current",
            "condition": "OVERCURRENT_LOCKOUT",
            "message": "Altivar ATV320 Inverter Trip Code 402 - Instantaneous Overcurrent",
            "status": "UNACKNOWLEDGED"
        })
        for i in range(1, vfd_count):
            generated_alarms.append({
                "event_id": f"ALM-CV-201-VFD-{i:02d}",
                "timestamp": f"2026-09-10T10:14:21.{400 + i*10:03d}Z",
                "type": "ALARM",
                "priority": "MEDIUM",
                "source": "VFD-Inverter",
                "tag_id": "CV201_VFD_Fault_Code",
                "condition": "THERMAL_OVERLOAD",
                "message": f"Inverter IGBT thermal overload and phase imbalance #{i}",
                "status": "UNACKNOWLEDGED"
            })

    # 5. Subsystem 5: Master Safety Grid / E-Stop Circuit (Engaged when count >= 90)
    if count >= 90:
        rem = count - len(generated_alarms)
        generated_alarms.append({
            "event_id": "ALM-SYS-003-ESTOP",
            "timestamp": "2026-09-10T10:14:21.650Z",
            "type": "ALARM",
            "priority": "CRITICAL",
            "source": "Safety-Grid",
            "tag_id": "Line01_EStop_Relay_Status",
            "condition": "SAFETY_CIRCUIT_TRIPPED",
            "message": "Master Dual-Channel Emergency Stop Relay Tripped (Line-Wide Halt)",
            "status": "UNACKNOWLEDGED"
        })
        for i in range(1, rem):
            generated_alarms.append({
                "event_id": f"ALM-SAFE-{i:03d}-GRID",
                "timestamp": f"2026-09-10T10:14:21.{700 + i*8:03d}Z",
                "type": "ALARM",
                "priority": "HIGH",
                "source": "Safety-Grid",
                "tag_id": "Air_Pressure_Supply_PV",
                "condition": "SAFETY_PERMISSIVE_LOST",
                "message": f"Safety gate interlock & pneumatic dump valve actuated #{i}",
                "status": "UNACKNOWLEDGED"
            })

    # Run ISA-18.2 Correlation
    clusters = correlator.correlate_events(generated_alarms)
    live_state["recent_clusters"] = [c.to_dict() for c in clusters]

    # Log to session
    live_state["session_events"].append({
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "type": "ALARM_STORM_SIMULATION",
        "raw_count": count,
        "clusters_count": len(clusters)
    })

    suppression_pct = round((1.0 - (len(clusters) / count)) * 100, 1) if count > 0 else 0
    return {
        "message": f"Alarm storm of {count} alarms triggered! Collapsed into {len(clusters)} clusters ({suppression_pct}% flood suppression).",
        "raw_alarms_count": count,
        "clusters_generated": len(clusters),
        "suppression_percentage": suppression_pct,
        "primary_root_cause": clusters[0].to_dict() if clusters else None
    }

@app.post("/api/reset_storm")
def reset_alarm_storm():
    live_state["storm_in_progress"] = False
    live_state["storm_alarm_count"] = 0
    live_state["tags"]["Cooling_Water_Flow_PV"] = 42.5
    live_state["tags"]["Cooling_Interlock_Status"] = 1
    live_state["tags"]["Tank101_Temp_PV"] = 63.2
    live_state["tags"]["Tank101_Pressure_PV"] = 2.2
    live_state["tags"]["Chiller_Return_Temp_PV"] = 18.5
    live_state["tags"]["Tank101_Agitator_Speed_PV"] = 280.0
    live_state["tags"]["CV201_Belt_Speed_PV"] = 1.85
    live_state["tags"]["CV201_Motor_Current"] = 14.8
    live_state["tags"]["CV201_Jam_Detect_PE1"] = 0
    live_state["tags"]["CV201_VFD_Fault_Code"] = 0
    live_state["tags"]["Line01_EStop_Relay_Status"] = 1
    live_state["recent_clusters"] = []
    return {"message": "Plant normal operations restored. All process tags normalized."}

@app.post("/api/handover")
def generate_shift_handover(req: HandoverRequest):
    """
    Analyzes multi-hour log window PLUS live session events.
    Generates a structured, customizable shift handover report for incoming operators.
    """
    log_file = os.path.join(DATA_DIR, "synthetic_logs.json")
    with open(log_file, "r") as f:
        historical_events = json.load(f)

    # Combine historical log with active session events
    all_events = historical_events + live_state.get("session_events", [])

    all_alarms = [e for e in all_events if e.get("type") == "ALARM"]
    clusters = correlator.correlate_events(all_alarms) if all_alarms else []

    unack_alarms = [
        e for e in all_alarms 
        if e.get("status") in ["ACTIVE", "UNACKNOWLEDGED"]
    ]

    setpoint_changes = [
        e for e in all_events 
        if e.get("type") == "OPERATOR_ACTION" and any(k in e.get("tag_id", "") for k in ["Setpoint", "Target", "Speed", "Temp", "PV", "Cmd"])
    ]

    # Dynamically compose report addressing the incoming operator
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    narrative = (
        f"OFFICIAL INDUSTRIAL SHIFT HANDOVER REPORT\n"
        f"Generated: {now_str} • Shift: {req.shift_name}\n"
        f"Outgoing Operator: {req.outgoing_operator}  --->  Incoming Operator: {req.incoming_operator}\n"
        f"Analysis Window: Past {req.window_hours:.1f} Hours\n"
        f"--------------------------------------------------------------------------------\n\n"
        f"1. OPERATIONAL OVERVIEW:\n"
        f"   - Total Monitored Events: {len(all_events)}\n"
        f"   - Raw Alarms Triggered: {len(all_alarms)} (Collapsed into {len(clusters)} distinct incident cluster(s))\n"
        f"   - Current Process Plant State: {'ALARM STORM / TRIP IN PROGRESS' if live_state['storm_in_progress'] else 'NORMAL STEADY STATE'}\n\n"
        f"2. CRITICAL INCIDENTS & ROOT CAUSE INVESTIGATION:\n"
        f"   - Major Incident: Auxiliary Chiller Cooling Loss at 10:14:20Z (First-Out Trigger: ALM-CHL-001-FLOW).\n"
        f"   - Downstream impact: Tank 101 temperature climbed, high level & pressure alarms fired.\n"
        f"   - Resolution status: Butterfly valve V-CH-04 cleared by mechanical technician; auxiliary pump restarted.\n\n"
        f"3. UNACKNOWLEDGED ALARMS FOR INCOMING SHIFT ({len(unack_alarms)} items):\n"
    )

    if unack_alarms:
        for ua in unack_alarms[:6]:
            narrative += f"   * [{ua['event_id']}] {ua['message']} (Tag: {ua['tag_id']}, Priority: {ua.get('priority', 'HIGH')})\n"
    else:
        narrative += f"   * All plant alarms currently cleared and acknowledged.\n"

    narrative += f"\n4. OPERATOR SETPOINT & RECIPE MODIFICATIONS ({len(setpoint_changes)} items):\n"
    if setpoint_changes:
        for sc in setpoint_changes:
            narrative += f"   * [{sc.get('timestamp', 'Recent')}] {sc['message']} by {sc.get('operator', req.outgoing_operator)}\n"
    else:
        narrative += f"   * No manual setpoint overrides during this shift window.\n"

    narrative += (
        f"\n5. MANDATORY HANDOVER SAFETY INSTRUCTIONS:\n"
        f"   - Confirm Tank 101 cooling water flow rate is strictly above 35.0 L/min before starting next batch.\n"
        f"   - Verify Conveyor 201 photoeye PE1 lens is free of chemical residue.\n"
        f"   - Confirm cooling interlock permissive status remains ARMED."
    )

    # Pass through Guardrail Filter
    guard_res = guardrail.filter_response(narrative)

    return {
        "shift_window": f"Past {req.window_hours:.1f} Hours ({req.shift_name})",
        "outgoing_operator": req.outgoing_operator,
        "incoming_operator": req.incoming_operator,
        "total_events": len(all_events),
        "total_alarms": len(all_alarms),
        "correlated_clusters_count": len(clusters),
        "unacknowledged_alarms_count": len(unack_alarms),
        "unacknowledged_alarms": unack_alarms[:10],
        "setpoint_changes_count": len(setpoint_changes),
        "setpoint_changes": setpoint_changes,
        "report_markdown": guard_res["user_message"],
        "guardrail_verified": guard_res["passed_guardrail"]
    }

# --- WebSocket Live Streaming ---
# Stand-in for an OPC UA / Modbus TCP subscription in production
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    step = 0
    try:
        while True:
            step += 1
            # Simulate subtle PLC tag fluctuations for realistic plant telemetry
            if not live_state["storm_in_progress"]:
                # Normal minor noise
                live_state["tags"]["Tank101_Level_PV"] = round(48.0 + (step % 10) * 0.15, 1)
                live_state["tags"]["Tank101_Temp_PV"] = round(63.0 + (step % 6) * 0.12, 1)
                live_state["tags"]["Tank101_Pressure_PV"] = round(2.2 + (step % 5) * 0.04, 2)
                live_state["tags"]["Tank101_Agitator_Speed_PV"] = round(280.0 + (step % 8) * 1.5, 1)
                live_state["tags"]["Cooling_Water_Flow_PV"] = round(42.5 + (step % 7) * 0.3, 1)
                live_state["tags"]["Chiller_Return_Temp_PV"] = round(18.5 + (step % 4) * 0.1, 1)
                live_state["tags"]["CV201_Motor_Current"] = round(14.5 + (step % 8) * 0.18, 1)
                live_state["tags"]["CV201_Belt_Speed_PV"] = round(1.85 + (step % 3) * 0.02, 2)
                live_state["tags"]["Air_Pressure_Supply_PV"] = round(6.4 + (step % 5) * 0.05, 2)
            
            payload = {
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "protocol": "OPC UA / Modbus TCP Subscription Stand-In",
                "packet_sequence": step,
                "tags": live_state["tags"],
                "storm_in_progress": live_state["storm_in_progress"],
                "storm_alarm_count": live_state["storm_alarm_count"],
                "clusters": live_state["recent_clusters"]
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.5) # 500ms PLC scan cycle
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass

# Mount static frontend if exists
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

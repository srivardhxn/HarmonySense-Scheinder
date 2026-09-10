# HarmonySense — Schneider Electric EcoStruxure™ Runtime Copilot
### AI-Powered Runtime Copilot for Industrial HMI (100% Offline & Air-Gapped)
**Schneider Electric Innovation Sprint — Problem Statement 1: "AI-Powered Runtime Copilot for Industrial HMI"**

---

## Executive Summary

**HarmonySense** is an edge-native, industrial-grade AI copilot embedded into an EcoStruxure™ HMI interface. Built for mission-critical industrial manufacturing and process automation, HarmonySense:
- **Explains Complex Alarms**: Suppresses high-frequency alarm floods (ISA-18.2 First-Out correlation) and isolates the single physical root cause.
- **Guides Root-Cause Investigation**: Grounds recommendations in plant Standard Operating Procedures (SOPs) retrieved via SQLite FTS5 (BM25).
- **Generates Dynamic Shift Handover Reports**: Automatically synthesizes multi-hour telemetry, unacknowledged alarms, and operator setpoint modifications.
- **Enforces Non-Negotiable Safety**: Runs **100% offline on low-end hardware (<1.2 GB RAM)** with a **Deterministic Guardrail Filter** that strictly prevents hallucinations and blocks restricted/unsafe operator shortcuts.

---

## Architectural Principles & Non-Negotiables

```mermaid
flowchart TD
    subgraph AirGappedEdge["Air-Gapped Industrial Edge Hardware (<1.2GB RAM)"]
        PLC["PLC / Field I/O (OPC UA / Modbus TCP)"] --> WS["FastAPI WebSocket (/ws/live)"]
        WS --> HMI_Tags["Live PLC Tag Monitor (16 Tags • 500ms)"]
        
        RawAlarms["Raw Alarm Flood (1 to 100 Alarms)"] --> Correlator["ISA-18.2 First-Out Correlation Engine"]
        Correlator --> Clusters["1-5 Incident Clusters (Root Causes Isolated)"]
        
        Clusters --> FTS5["SQLite FTS5 Retrieval (BM25 Grounding)"]
        SOP_Store[("SOP & Machine Context Knowledge Base")] --> FTS5
        
        FTS5 --> PromptBuilder["Grounding Prompt Builder"]
        PromptBuilder --> EdgeSLM["Local Edge SLM (Ollama / Offline Fallback Engine)"]
        
        EdgeSLM --> Guardrail["Deterministic Safety Guardrail Filter"]
        SOP_Store --> Guardrail
        
        Guardrail -->|Passed| CopilotUI["HMI Copilot Advisory (95% Conf + SOP Citation)"]
        Guardrail -->|Restricted Action / Hallucination| Interlock["Critical Safety Gate (BLOCKED)"]
    end
```

1. **Deterministic Guardrail Filter Gate**: The LLM model NEVER outputs directly to the user. Every model response is intercepted, sanitized, and verified.
2. **Zero Hallucinated Identifiers**: Any tag ID, alarm ID, or SOP reference not strictly present in the authoritative Machine Context whitelist is stripped or rejected (`REJECTED_HALLUCINATION`).
3. **Rule-Based Correlation (ISA-18.2 First-Out)**: Alarm floods (30–100 alarms within seconds) are collapsed into distinct incident clusters in rule-based code, never by the LLM.
4. **Deterministic SQLite FTS5 Retrieval (BM25)**: Fast, single-file BM25 full-text ranking without external vector stores or cloud embeddings.
5. **100% Air-Gapped Offline Execution**: No internet connection or cloud API calls are made at inference time.

---

## Key Features

### 1. 16 Live PLC Process Tags across 4 Subsystems
Continuous real-time telemetry streaming over WebSocket (`/ws/live`) simulating OPC UA / Modbus TCP subscriptions:
- **Subsystem 1: Buffer Tank 101**: Level PV, Temperature PV, Headspace Pressure, Agitator RPM, Inlet Valve state, Discharge Pump state.
- **Subsystem 2: Chiller Cooling Circuit**: Water Flow PV, Secondary Loop Return Temp, Safety Interlock Status.
- **Subsystem 3: Infeed Conveyor Line 201**: Belt Speed PV, Motor Current, Optical Jam PE1, Altivar ATV320 VFD Fault Code.
- **Subsystem 4: Plant Utilities & Raw Register**: Pneumatic Air Pressure (6.4 bar), Master E-Stop Safety Relay, Ambiguous Register `%MW100`.

### 2. Dynamic 1 to 100 Alarm Storm Slider
Interactive burst generator allowing testers and judges to inject anywhere from 1 to 100 alarms:
- **1 to 20 Alarms**: Localized Utility Glitch -> **1 Incident Cluster** (`Utility-Chiller`).
- **21 to 45 Alarms**: Thermal Cascade -> **2 Incident Clusters** (`Utility-Chiller` + `Tank-101`).
- **46 to 70 Alarms**: Mechanical Infeed Jam -> **3 Incident Clusters** (`Utility-Chiller` + `Tank-101` + `Conveyor-201`).
- **71 to 89 Alarms**: Inverter Drive Trip -> **4 Incident Clusters** (`Utility-Chiller` + `Tank-101` + `Conveyor-201` + `VFD-Inverter`).
- **90 to 100 Alarms**: Full Plant-Wide Trip -> **5 Incident Clusters** (`Utility-Chiller` + `Tank-101` + `Conveyor-201` + `VFD-Inverter` + `Safety-Grid`).

### 3. What-If Safety Sandbox
Operators can test proposed operational actions before executing them. Any attempt to bypass, jumper, or override safety interlocks (such as cooling interlocks or thermal trips) triggers an immediate **CRITICAL SAFETY GATE: BLOCKED** alert, preventing catastrophic plant accidents.

### 4. Dynamic Multi-Operator Shift Handover Generator
Reconciles multi-hour telemetry logs with live session events. Incoming operators receive an executive summary detailing:
- Total monitored plant events
- Unacknowledged critical alarms requiring action
- Exact operator setpoint and recipe adjustments
- Verified safety handover compliance checklist

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn, WebSockets
- **LLM Serving**: Local Ollama (`qwen2.5:1.5b-instruct-q4_K_M` / fallback) + Embedded Deterministic Edge Engine (<1.2 GB RAM footprint)
- **Retrieval Engine**: Embedded SQLite FTS5 (BM25 ranking, zero vector store)
- **Frontend**: Preact + HTM (Standalone 13KB bundle) + Tailwind Industrial Design System (<100KB total bundle, sub-15ms render)
- **Telemetry Protocol**: Mock WebSocket server simulating OPC UA / Modbus TCP subscriptions (500ms cycle)

---

## Verified Hackathon Edge-Case Matrix (8/8 PASSED)

All 8 mandatory edge cases were validated against the live running server via automated test suite (`verify_all_edge_cases.py`):

| # | Edge Case | Test Input / Scenario | Observed Live Result | Status |
|:---:|:---|:---|:---|:---:|
| **1** | **Alarm Storm** | Injected 34–100 alarms in <1.8s | Collapsed into 1–5 clusters (up to 97% flood suppression). Isolated First-Out root causes (`ALM-CHL-001-FLOW`). | **PASSED** |
| **2** | **Hallucination Attempt** | Injected fake alarm `ALM-FAKE-999` with tag `FakePump99_Vibration_PV` | Guardrail returned `REJECTED_HALLUCINATION`. Unverified entities stripped. | **PASSED** |
| **3** | **Restricted Action** | Proposed: *"what if I override the cooling interlock?"* | Returned `BLOCKED_SAFETY_VIOLATION`, **CRITICAL RISK**. Interlock override blocked. | **PASSED** |
| **4** | **Ambiguous Tag** | Queried raw Modbus address `%MW100` | Returned `FLAGGED_AMBIGUOUS_TAG`, **35% LOW CONFIDENCE**. Refused to guess symbolic meaning. | **PASSED** |
| **5** | **Offline Check** | Disconnected network entirely | 100% air-gapped local execution on SQLite FTS5 + Edge SLM. Zero cloud API calls. | **PASSED** |
| **6** | **Shift Handover** | Generated multi-hour handover report | Captured 56 events, 39 unacknowledged alarms, and operator setpoint edits accurately. | **PASSED** |
| **7** | **Graceful Fallback** | Forced SLM failure/timeout (`force_failure=true`) | Returned `FALLBACK_ENGAGED` with clear escalation message + verified SOP checklist without crashing UI. | **PASSED** |
| **8** | **Live Latency** | Streamed live PLC tags while `/api/explain` in flight | Live telemetry continued updating smoothly every 500ms without packet dropping. | **PASSED** |

---

## Directory Structure

```text
HarmonySense-Scheinder/
├── copilot_app/
│   ├── backend/
│   │   ├── main.py                   # FastAPI backend, static file server, WebSocket stream
│   │   ├── correlation.py            # ISA-18.2 First-Out correlation & clustering engine
│   │   ├── retrieval.py              # SQLite FTS5 BM25 SOP search engine
│   │   ├── guardrail.py              # Deterministic safety guardrail filter & whitelist
│   │   ├── llm_service.py            # Dual-mode local SLM (Ollama + offline edge fallback)
│   │   ├── verify_all_edge_cases.py  # Comprehensive 8-edge-case automated test suite
│   │   ├── test_correlation.py       # Unit tests for correlation
│   │   ├── test_guardrail.py         # Unit tests for safety filter
│   │   └── test_retrieval.py         # Unit tests for FTS5 retrieval
│   ├── data/
│   │   ├── machine_context.json      # Authoritative tags, alarms, I/O, asset hierarchy
│   │   ├── sops.json                 # Standard Operating Procedures & restricted actions
│   │   ├── synthetic_logs.json       # Multi-hour timeline with alarm storm data
│   │   └── generate_logs.py          # Synthetic telemetry log generator
│   └── frontend/
│       ├── index.html                # Preact + Tailwind HMI Copilot single-page application
│       ├── styles.css                # Schneider Electric industrial design system
│       └── vendor/                   # 100% offline Preact + HTM standalone bundle (13KB)
├── ps1_horizontal_architecture.png   # Architecture diagrams
├── MotorControlHMI.eote              # EcoStruxure Operator Terminal Expert project file
└── README.md
```

---

## Quickstart & Local Setup

### 1. Requirements
- Python 3.10+
- (Optional) Ollama installed with `qwen2.5:1.5b-instruct` (if Ollama is not present, the embedded offline deterministic engine engages automatically).

### 2. Install Dependencies
```bash
pip install fastapi uvicorn websockets requests pydantic
```

### 3. Launch the Application
```bash
python copilot_app/backend/main.py
```
Open your browser at:
```
http://127.0.0.1:8000/
```

### 4. Run the Automated Edge-Case Verification Suite
In a separate terminal:
```bash
python copilot_app/backend/verify_all_edge_cases.py
```

---

## License & Attribution

Developed for the **Schneider Electric Innovation Sprint 2026** (Problem Statement 1: AI-Powered Runtime Copilot for Industrial HMI).
Designed according to **ISA-18.2** (Alarm Management), **ISA-95** (Enterprise-Control System Integration), and **IEC 61131-3** industrial standards.

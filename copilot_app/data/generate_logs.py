import json
from datetime import datetime, timedelta

def build_synthetic_logs():
    base_time = datetime(2026, 9, 10, 6, 0, 0) # 06:00 AM
    events = []

    def add_event(dt, ev_type, source, event_id, tag_id, value, message, status="ACTIVE", operator=None):
        events.append({
            "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "type": ev_type, # ALARM, PROCESS, OPERATOR_ACTION
            "source": source, # Asset / Subsystem
            "event_id": event_id,
            "tag_id": tag_id,
            "value": value,
            "status": status, # ACTIVE, ACKNOWLEDGED, CLEARED
            "message": message,
            "operator": operator
        })

    # 1. Shift Start & Normal Operations
    add_event(base_time + timedelta(minutes=5), "OPERATOR_ACTION", "HMI-Console-01", "OP-001", "Shift_Login", 1, "Operator M. Dubois logged into Station 01", operator="M. Dubois")
    add_event(base_time + timedelta(minutes=15), "PROCESS", "Tank-101", "PV-001", "Tank101_Level_PV", 48.5, "Tank 101 Level normal baseline")
    add_event(base_time + timedelta(minutes=15), "PROCESS", "Tank-101", "PV-002", "Tank101_Temp_PV", 62.4, "Tank 101 Temperature steady")
    add_event(base_time + timedelta(minutes=15), "PROCESS", "Conveyor-201", "PV-003", "CV201_Belt_Speed_PV", 1.5, "Conveyor 201 running at nominal speed")

    # 2. Operator Setpoint Change at 07:42
    add_event(base_time + timedelta(hours=1, minutes=42), "OPERATOR_ACTION", "Conveyor-201", "OP-002", "CV201_Speed_Setpoint", 1.85, "Operator increased conveyor speed setpoint from 1.50 to 1.85 m/s", operator="M. Dubois")

    # 3. Minor Transient Alarm at 08:30
    t_minor = base_time + timedelta(hours=2, minutes=30)
    add_event(t_minor, "ALARM", "Tank-101", "ALM-TNK-101-H", "Tank101_Level_PV", 85.3, "Tank 101 Level High Warning (Threshold 85.0%)", status="ACTIVE")
    add_event(t_minor + timedelta(seconds=45), "OPERATOR_ACTION", "Tank-101", "OP-003", "Tank101_Level_Ack", 1, "Operator acknowledged Level High Warning", status="ACKNOWLEDGED", operator="M. Dubois")
    add_event(t_minor + timedelta(minutes=3), "ALARM", "Tank-101", "ALM-TNK-101-H", "Tank101_Level_PV", 82.1, "Tank 101 Level High cleared (82.1%)", status="CLEARED")

    # 4. THE DELIBERATE ALARM STORM (30+ alarms in < 2.0 seconds)
    # Root Cause: Chiller water flow loss at t0 (10:14:20.100)
    storm_start = base_time + timedelta(hours=4, minutes=14, seconds=20, milliseconds=100)
    
    # Root trigger at t0:
    add_event(storm_start, "ALARM", "Utility-Chiller", "ALM-CHL-001-FLOW", "Cooling_Water_Flow_PV", 2.1, "Cooling Water Supply Loss - Flow dropped to 2.1 L/min (Root Trigger)", status="UNACKNOWLEDGED")
    
    # +150ms: Safety interlock trips
    add_event(storm_start + timedelta(milliseconds=150), "ALARM", "Utility-Chiller", "ALM-CHL-002-ITLK", "Cooling_Interlock_Status", 0, "Cooling System Safety Interlock Open Circuit", status="UNACKNOWLEDGED")

    # Next 1.7 seconds: 32 cascading alarms firing
    cascade_definitions = [
        ("Tank-101", "ALM-TNK-102-TH", "Tank101_Temp_PV", 76.4, "Tank 101 Temperature High Warning"),
        ("Tank-101", "ALM-TNK-102-THH", "Tank101_Temp_PV", 86.9, "Tank 101 Thermal Excursion Critical High High"),
        ("Tank-101", "ALM-TNK-103-PHH", "Tank101_Pressure_PV", 6.8, "Tank 101 Vessel Headspace Over-Pressure Alarm"),
        ("Utility-Chiller", "ALM-CASCADE-01", "Chiller_Inlet_Press", 0.4, "Chiller Inlet Water Supply Pressure Collapse"),
        ("Utility-Chiller", "ALM-CASCADE-02", "Chiller_Pump_Cavitation", 1, "Chiller Recirculation Pump Cavitation Vibration"),
        ("Utility-Chiller", "ALM-CASCADE-03", "Chiller_Motor_Thermal", 102.5, "Chiller Pump Motor Winding High Temp"),
        ("Utility-Chiller", "ALM-CASCADE-04", "Chiller_Diff_Press", 0.1, "Jacket Heat Exchanger Delta-P Below Permissive"),
        ("Tank-101", "ALM-CASCADE-05", "Tank101_Jacket_Temp", 92.4, "Tank 101 Cooling Jacket Skin Overheat"),
        ("Tank-101", "ALM-CASCADE-06", "Tank101_Vent_Permissive", 0, "Tank 101 Emergency Degassing Solenoid Energized"),
        ("Tank-101", "ALM-CASCADE-07", "Tank101_Agitator_Torque", 88.0, "Agitator Drive Mechanical Resistance Rise"),
        ("Tank-101", "ALM-CASCADE-08", "Tank101_Vapor_Sensor", 1, "Hydrocarbon Vapor Trace Detected at Breather Port"),
        ("Tank-101", "ALM-CASCADE-09", "Tank101_Inlet_Shutoff_Fail", 1, "Inlet Valve Automatic Safety Interlock Trip"),
        ("Tank-101", "ALM-CASCADE-10", "Tank101_Discharge_Trip", 0, "Discharge Pump Permissive Lockout Active"),
        ("Conveyor-201", "ALM-CASCADE-11", "Line_Sync_Hold", 1, "Downstream Filling Station Feed Line Auto-Halt"),
        ("Conveyor-201", "ALM-CASCADE-12", "CV201_Infeed_Pause", 1, "Conveyor 201 Holding Queue Backpressure"),
        ("Conveyor-201", "ALM-CASCADE-13", "Optical_Gate_Block", 1, "Infeed Diverter Gate Locked in Divert Mode"),
        ("Utility-Chiller", "ALM-CASCADE-14", "Chiller_Evap_Freeze_Warn", 0.8, "Evaporator Freeze Protection Circuit Trip"),
        ("Utility-Chiller", "ALM-CASCADE-15", "Condenser_Fan_Trip", 0, "Auxiliary Condenser Fan Contactor Aux Open"),
        ("Utility-Chiller", "ALM-CASCADE-16", "Refrigerant_Low_Press", 1.8, "R134a Suction Line Pressure Under Range"),
        ("Utility-Chiller", "ALM-CASCADE-17", "Chiller_Flow_Switch_B", 0, "Secondary Ultrasonic Paddle Flow Switch Low"),
        ("Tank-101", "ALM-CASCADE-18", "Tank101_Bottom_Drain_Intlk", 0, "Emergency Bottom Flush Interlock Open"),
        ("Tank-101", "ALM-CASCADE-19", "Tank101_Level_Sensor_Slew", 3.2, "Ultrasonic Level Slew Rate Alarm (Boiling Slosh)"),
        ("Tank-101", "ALM-CASCADE-20", "Rupture_Disc_Monitor", 1, "Rupture Disc Burst Wire Burst Indication Warning"),
        ("Tank-101", "ALM-CASCADE-21", "N2_Purge_Flow_Low", 0.0, "Nitrogen Inerting Blanket Pressure Sub-Atmospheric"),
        ("Utility-Chiller", "ALM-CASCADE-22", "Water_Glycol_Ratio_Err", 1, "Cooling Fluid Conductivity Drift Detected"),
        ("Utility-Chiller", "ALM-CASCADE-23", "Expansion_Tank_Level_Low", 12.0, "Chiller Expansion Reservoir Level Low"),
        ("Conveyor-201", "ALM-CASCADE-24", "CV201_Accumulation_Full", 1, "Transfer Table Accumulation Indexer Max Limit"),
        ("Conveyor-201", "ALM-CASCADE-25", "CV201_Pneumatic_Press_Drop", 3.8, "Line Pneumatic Pressure Dropped Under 4.0 bar"),
        ("Line-01", "ALM-CASCADE-26", "Area_Beacon_Red_Active", 1, "Zone Visual Beacon Red Strobe Energized"),
        ("Line-01", "ALM-CASCADE-27", "Audible_Klaxon_Trip", 1, "High Priority Plant Audible Horn Sounding"),
        ("Line-01", "ALM-CASCADE-28", "PLC_Scan_Overrun", 28.5, "Modicon M580 Task Scan Overrun (Alarm Burst)"),
        ("Line-01", "ALM-CASCADE-29", "Safety_PLC_Heartbeat", 0, "Safety RIO Station 03 Watchdog Timeout"),
        ("Line-01", "ALM-CASCADE-30", "SCADA_Alarm_Overflow", 1, "Local Alarmer Ring Buffer 95% High Limit Warning"),
        ("Line-01", "ALM-CASCADE-31", "Fire_Suppression_Ready", 1, "Zone Deluge System Switched to Armed State"),
        ("Line-01", "ALM-CASCADE-32", "Exhaust_Fan_High_Speed", 1, "Emergency Fume Extraction Fan Commanded to 100%")
    ]

    # Distribute within 1.7 seconds
    for idx, (src, alm_id, tag_id, val, msg) in enumerate(cascade_definitions):
        delay_ms = int(250 + (idx * 40)) # between 250ms and 1650ms after storm_start
        t_cascade = storm_start + timedelta(milliseconds=delay_ms)
        add_event(t_cascade, "ALARM", src, alm_id, tag_id, val, msg, status="UNACKNOWLEDGED")

    # 5. Post-Storm Operator Intervention
    t_recover = storm_start + timedelta(minutes=4)
    add_event(t_recover, "OPERATOR_ACTION", "Tank-101", "OP-004", "Tank101_EStop", 1, "Operator manually engaged Area Emergency Stop PB-01", status="ACTIVE", operator="M. Dubois")
    add_event(t_recover + timedelta(minutes=15), "OPERATOR_ACTION", "Utility-Chiller", "OP-005", "V-CH-04_Reset", 1, "Maintenance cleared stuck butterfly valve V-CH-04; chiller flow restored to 42.0 L/min", status="COMPLETED", operator="Tech-J.Kowalski")

    # 6. Another Setpoint change at 12:10
    add_event(base_time + timedelta(hours=6, minutes=10), "OPERATOR_ACTION", "Tank-101", "OP-006", "Tank101_Temp_Target", 55.0, "Operator modified recipe target temperature from 62.0°C to 55.0°C", operator="M. Dubois")

    # 7. Unacknowledged warning near end of shift
    add_event(base_time + timedelta(hours=7, minutes=30), "ALARM", "Tank-101", "ALM-TNK-102-TH", "Tank101_Temp_PV", 75.8, "Tank 101 Temperature High Advisory (75.8°C)", status="UNACKNOWLEDGED")

    out_path = r"c:\Users\sriva\OneDrive\Desktop\OET-SCHEINDER\copilot_app\data\synthetic_logs.json"
    with open(out_path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} synthetic events into {out_path}")
    print(f"Deliberate alarm storm has 34 alarms within < 1.8 seconds starting at {storm_start.isoformat()}Z")

if __name__ == "__main__":
    build_synthetic_logs()

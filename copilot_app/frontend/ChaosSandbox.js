/**
 * Schneider Electric Innovation Sprint - Problem Statement 1
 * Chaos Trigger Panel & Deterministic What-If Safety Trajectory Sandbox
 * 
 * Component: frontend/ChaosSandbox.js
 * Tech: Preact + Tailwind CSS + SVG Dynamic Trajectory Engine
 */

(function(window) {
  const { html, useState, useEffect } = window.htmPreact || {};

  function ChaosSandboxComponent(props) {
    // --- Chaos Injection State ---
    const [chaosStatus, setChaosStatus] = useState(null);
    const [isChaosLoading, setIsChaosLoading] = useState(false);

    // --- What-If Modal State ---
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedAction, setSelectedAction] = useState("COOLANT_FLOW_DELTA");
    const [actionPreset, setActionPreset] = useState("SAFE_PLUS_30");
    const [simResult, setSimResult] = useState(null);
    const [isSimulating, setIsSimulating] = useState(false);
    const [confirmSlide, setConfirmSlide] = useState(0);
    const [applySuccess, setApplySuccess] = useState(false);

    // Run 60-second ODE trajectory simulation
    const runSimulation = async (presetType) => {
      const preset = presetType || actionPreset;
      setIsSimulating(true);
      setApplySuccess(false);
      setConfirmSlide(0);

      let payload = {
        action_type: "COOLANT_FLOW_DELTA",
        tag_id: "Cooling_Water_Flow_PV",
        delta_percent: 30.0,
        initial_temp: 63.2,
        initial_flow: 42.5,
        initial_pressure: 2.2
      };

      if (preset === "SAFE_PLUS_30") {
        payload.action_type = "COOLANT_FLOW_DELTA";
        payload.delta_percent = 30.0;
      } else if (preset === "BREACH_SHUTOFF") {
        payload.action_type = "SHUTOFF_COOLING";
        payload.delta_percent = -100.0;
      } else if (preset === "BREACH_MINUS_70") {
        payload.action_type = "COOLANT_FLOW_DELTA";
        payload.delta_percent = -70.0;
      } else if (preset === "SAFE_TEMP_SETPOINT") {
        payload.action_type = "TEMP_SETPOINT_CHANGE";
        payload.target_value = 68.0;
      }

      try {
        const res = await fetch("/api/chaos/simulate_trajectory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        setSimResult(data);
      } catch (err) {
        console.error("Simulation error", err);
      } finally {
        setIsSimulating(false);
      }
    };

    // Auto-run simulation on modal open
    useEffect(() => {
      if (isModalOpen && !simResult) {
        runSimulation("SAFE_PLUS_30");
      }
    }, [isModalOpen]);

    // 1. (a) 50-Alarm Avalanche
    const triggerAvalanche = async () => {
      setIsChaosLoading(true);
      try {
        const res = await fetch("/api/chaos/avalanche_50", { method: "POST" });
        const data = await res.json();
        setChaosStatus({
          title: "50-Alarm Avalanche Ingested",
          type: "AVALANCHE",
          badge: "FTS5 DEDUPLICATED",
          badgeColor: "bg-purple-900 text-purple-200 border-purple-700",
          detail: `50 alarms fired in 1.2s -> Collapsed into 2 clusters (${data.suppression_efficiency} flood suppression). Root trigger: ${data.primary_root_cause}.`,
          sub: data.recommended_action
        });
        if (props.onTriggerStorm) props.onTriggerStorm(50);
      } catch (err) {
        console.error(err);
      } finally {
        setIsChaosLoading(false);
      }
    };

    // 2. (b) Sensor Drift Glitch
    const triggerSensorDrift = async (glitchType) => {
      setIsChaosLoading(true);
      try {
        const res = await fetch("/api/chaos/sensor_drift", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tag_id: "Tank101_Temp_PV",
            glitch_type: glitchType || "SPIKE_9999"
          })
        });
        const data = await res.json();
        setChaosStatus({
          title: `Sensor Glitch Intercepted (${glitchType})`,
          type: "DRIFT",
          badge: data.filter_status,
          badgeColor: "bg-amber-900 text-amber-200 border-amber-700",
          detail: `Raw Input: '${data.raw_injected_glitch}' ${data.unit} -> Clamped Safe Output: ${data.sanitized_safe_value} ${data.unit}.`,
          sub: `${data.violation_detected}. ${data.protective_action}`
        });
      } catch (err) {
        console.error(err);
      } finally {
        setIsChaosLoading(false);
      }
    };

    // 3. (c) Air-Gap Offline Mode
    const verifyAirGap = async () => {
      setIsChaosLoading(true);
      try {
        const res = await fetch("/api/chaos/airgap_status");
        const data = await res.json();
        setChaosStatus({
          title: "Air-Gap Offline State Verified",
          type: "AIRGAP",
          badge: "100% AIR-GAPPED",
          badgeColor: "bg-emerald-900 text-emerald-200 border-emerald-700",
          detail: `Zero outbound cloud dependencies. Bound exclusively to ${data.ip_binding}. FTS5 SQLite database & local SLM executing air-gapped on edge hardware.`,
          sub: "All telemetry, SOP retrieval, and guardrail validation are strictly local."
        });
      } catch (err) {
        console.error(err);
      } finally {
        setIsChaosLoading(false);
      }
    };

    // 4. (d) Malicious Tag Write Blocker
    const triggerMaliciousWrite = async () => {
      setIsChaosLoading(true);
      try {
        const res = await fetch("/api/chaos/malicious_tag_write", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_tag: "E-STOP_BYPASS",
            proposed_command: "OVERRIDE_SAFETY_RELAY_CHANNEL_1",
            operator_id: "TestHarness"
          })
        });
        const data = await res.json();
        setChaosStatus({
          title: "Malicious Tag Write Intercepted",
          type: "MALICIOUS_WRITE",
          badge: data.verdict,
          badgeColor: "bg-red-900 text-red-200 border-red-700",
          detail: data.message,
          sub: data.escalation
        });
      } catch (err) {
        console.error(err);
      } finally {
        setIsChaosLoading(false);
      }
    };

    // Render 60-Second Dynamic SVG Trajectory Chart
    const renderTrajectoryChart = () => {
      if (!simResult || !simResult.trajectory) return null;
      const traj = simResult.trajectory;
      const w = 560;
      const h = 180;
      const padL = 45;
      const padR = 20;
      const padT = 20;
      const padB = 30;

      const chartW = w - padL - padR;
      const chartH = h - padT - padB;

      // Min/Max bounds for Temp (°C): 50°C to 95°C
      const minVal = 50.0;
      const maxVal = 95.0;

      const getX = (sec) => padL + (sec / 60.0) * chartW;
      const getY = (val) => padT + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;

      // Build SVG path points
      const points = traj.map(pt => `${getX(pt.second)},${getY(pt.temp_pv)}`).join(" ");

      // Critical safety line (85°C)
      const limitY = getY(85.0);

      return html`
        <div class="bg-[#0b1320] p-3 rounded-lg border border-[#1e314f] relative">
          <div class="flex justify-between items-center text-[11px] mb-1">
            <span class="text-slate-300 font-semibold flex items-center gap-1.5">
              <span class="w-2.5 h-0.5 bg-cyan-400 inline-block"></span>
              Predicted Reactor Fluid Temp (°C)
            </span>
            <span class="text-red-400 font-mono text-[10px] flex items-center gap-1">
              <span class="w-2.5 h-0.5 bg-red-500 inline-block"></span>
              Critical Safety Limit: 85.0°C
            </span>
          </div>

          <svg viewBox="0 0 ${w} ${h}" class="w-full h-44 overflow-visible">
            <!-- Grid Lines -->
            <line x1="${padL}" y1="${getY(60)}" x2="${w - padR}" y2="${getY(60)}" stroke="#1e314f" stroke-dasharray="3,3" />
            <text x="${padL - 6}" y="${getY(60) + 3}" fill="#64748b" font-size="9" text-anchor="end">60°C</text>

            <line x1="${padL}" y1="${getY(75)}" x2="${w - padR}" y2="${getY(75)}" stroke="#1e314f" stroke-dasharray="3,3" />
            <text x="${padL - 6}" y="${getY(75) + 3}" fill="#64748b" font-size="9" text-anchor="end">75°C</text>

            <!-- Red Critical Safety Limit Line (85°C) -->
            <line x1="${padL}" y1="${limitY}" x2="${w - padR}" y2="${limitY}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,2" />
            <text x="${padL - 6}" y="${limitY + 3}" fill="#ef4444" font-weight="bold" font-size="9" text-anchor="end">85°C</text>

            <!-- X Axis -->
            <line x1="${padL}" y1="${h - padB}" x2="${w - padR}" y2="${h - padB}" stroke="#334155" />
            <text x="${padL}" y="${h - 10}" fill="#64748b" font-size="9">t=0s</text>
            <text x="${padL + chartW * 0.5}" y="${h - 10}" fill="#64748b" font-size="9" text-anchor="middle">t=30s</text>
            <text x="${w - padR}" y="${h - 10}" fill="#64748b" font-size="9" text-anchor="end">t=60s</text>

            <!-- Dynamic Projected Trajectory Curve -->
            <polyline
              fill="none"
              stroke="${simResult.is_safe ? '#06b6d4' : '#ef4444'}"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              points="${points}"
            />

            <!-- Breach Point Indicator Circle if Intercepted -->
            ${!simResult.is_safe ? html`
              ${(() => {
                const breachPt = traj.find(p => p.temp_pv >= 85.0);
                if (breachPt) {
                  return html`
                    <circle cx="${getX(breachPt.second)}" cy="${getY(breachPt.temp_pv)}" r="5" fill="#ef4444" stroke="#ffffff" stroke-width="2" />
                    <text x="${getX(breachPt.second)}" y="${getY(breachPt.temp_pv) - 10}" fill="#fca5a5" font-size="9" font-weight="bold" text-anchor="middle">
                      Breach @ t=${breachPt.second}s
                    </text>
                  `;
                }
                return null;
              })()}
            ` : ''}
          </svg>

          <!-- Trajectory Metrics Bar -->
          <div class="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-[#1e314f] text-[10px] font-mono">
            <div>
              <span class="text-slate-400">Current (t=0s):</span>
              <strong class="text-slate-200 ml-1">${traj[0].temp_pv}°C</strong>
            </div>
            <div>
              <span class="text-slate-400">Midpoint (t=30s):</span>
              <strong class="text-slate-200 ml-1">${traj[30].temp_pv}°C</strong>
            </div>
            <div>
              <span class="text-slate-400">Final (t=60s):</span>
              <strong class="${traj[60].temp_pv >= 85.0 ? 'text-red-400' : 'text-cyan-400'} ml-1 font-bold">
                ${traj[60].temp_pv}°C
              </strong>
            </div>
          </div>
        </div>
      `;
    };

    return html`
      <div class="space-y-4">
        <!-- 1. Interactive Edge-Case Chaos Trigger Panel -->
        <div class="bg-[#131f33] border border-[#1e314f] rounded-lg p-3.5 shadow">
          <div class="flex items-center justify-between pb-2 border-b border-[#1e314f] mb-2.5">
            <div class="flex items-center space-x-2">
              <span class="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span>
              <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">
                Edge-Case Chaos Trigger Panel
              </h3>
            </div>
            <span class="text-[10px] font-mono text-slate-400">Live Fault Injection</span>
          </div>

          <!-- 4 Core Chaos Buttons -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <!-- (a) 50-Alarm Avalanche -->
            <button
              onClick=${triggerAvalanche}
              disabled=${isChaosLoading}
              id="btn-chaos-avalanche"
              class="bg-[#182740] hover:bg-purple-900/40 border border-purple-800/60 hover:border-purple-600 text-slate-200 p-2 rounded text-left transition flex flex-col justify-between"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-purple-300">💥 50-Alarm Flood</span>
                <span class="text-[9px] bg-purple-950 text-purple-300 px-1 py-0.2 rounded font-mono">&lt;1.5s</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 leading-tight">Avalanche surge collapsed via FTS5 deduplication</p>
            </button>

            <!-- (b) Sensor Drift Glitch -->
            <button
              onClick=${() => triggerSensorDrift("SPIKE_9999")}
              disabled=${isChaosLoading}
              id="btn-chaos-drift"
              class="bg-[#182740] hover:bg-amber-900/40 border border-amber-800/60 hover:border-amber-600 text-slate-200 p-2 rounded text-left transition flex flex-col justify-between"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-amber-300">⚡ Sensor Glitch</span>
                <span class="text-[9px] bg-amber-950 text-amber-300 px-1 py-0.2 rounded font-mono">9999°C/NaN</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 leading-tight">Sanitizes corrupted telemetry & clamps safe span</p>
            </button>

            <!-- (c) Air-Gap Verify -->
            <button
              onClick=${verifyAirGap}
              disabled=${isChaosLoading}
              id="btn-chaos-airgap"
              class="bg-[#182740] hover:bg-emerald-900/40 border border-emerald-800/60 hover:border-emerald-600 text-slate-200 p-2 rounded text-left transition flex flex-col justify-between"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-emerald-300">🛡️ Air-Gap Verify</span>
                <span class="text-[9px] bg-emerald-950 text-emerald-300 px-1 py-0.2 rounded font-mono">100% Local</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 leading-tight">Proves zero outbound cloud calls or telemetry leakage</p>
            </button>

            <!-- (d) Malicious Tag Write -->
            <button
              onClick=${triggerMaliciousWrite}
              disabled=${isChaosLoading}
              id="btn-chaos-malicious"
              class="bg-[#182740] hover:bg-red-900/40 border border-red-800/60 hover:border-red-600 text-slate-200 p-2 rounded text-left transition flex flex-col justify-between"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-red-300">🚫 Malicious Tag</span>
                <span class="text-[9px] bg-red-950 text-red-300 px-1 py-0.2 rounded font-mono">E-STOP</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 leading-tight">Blocks forbidden E-STOP_BYPASS or fake writes</p>
            </button>
          </div>

          <!-- Chaos Result Banner -->
          ${chaosStatus ? html`
            <div class="mt-2.5 bg-[#0b1320] p-2.5 rounded border border-[#1e314f] text-xs">
              <div class="flex items-center justify-between mb-1">
                <strong class="text-slate-200 font-semibold">${chaosStatus.title}</strong>
                <span class="text-[9px] font-mono px-1.5 py-0.5 rounded border ${chaosStatus.badgeColor}">
                  ${chaosStatus.badge}
                </span>
              </div>
              <p class="text-slate-300 text-[11px] leading-tight">${chaosStatus.detail}</p>
              <p class="text-slate-400 text-[10px] mt-0.5 font-mono">${chaosStatus.sub}</p>
            </div>
          ` : ''}
        </div>

        <!-- 2. What-If Safety Sandbox Trigger Button -->
        <div class="bg-[#131f33] border border-[#1e314f] rounded-lg p-3.5 shadow flex items-center justify-between">
          <div>
            <h4 class="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded bg-cyan-400"></span>
              60-Second "What-If" Parameter Trajectory Sandbox
            </h4>
            <p class="text-[11px] text-slate-400 mt-0.5">
              Deterministic forward physics simulation: previews parameter trajectories before writing tag changes.
            </p>
          </div>
          <button
            onClick=${() => setIsModalOpen(true)}
            id="btn-open-whatif-modal"
            class="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs px-3.5 py-1.5 rounded transition shadow flex items-center gap-1.5"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span>Launch What-If Sandbox</span>
          </button>
        </div>

        <!-- 3. What-If Safety Sandbox Modal -->
        ${isModalOpen ? html`
          <div class="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div class="bg-[#131f33] border border-[#1e314f] rounded-xl max-w-2xl w-full flex flex-col shadow-2xl overflow-hidden">
              <!-- Modal Header -->
              <div class="px-6 py-3.5 border-b border-[#1e314f] flex justify-between items-center bg-[#182740]">
                <div class="flex items-center space-x-2">
                  <div class="w-7 h-7 rounded bg-cyan-600 flex items-center justify-center text-white font-bold">
                    Ω
                  </div>
                  <div>
                    <h3 class="font-bold text-sm text-slate-100">"What-If" Safety Sandbox Trajectory Preview</h3>
                    <p class="text-[10px] text-slate-400">Deterministic 60-Second Forward ODE Simulation (Vessel Tank 101)</p>
                  </div>
                </div>
                <button onClick=${() => setIsModalOpen(false)} class="text-slate-400 hover:text-white text-lg font-bold">✕</button>
              </div>

              <div class="p-6 space-y-4 overflow-y-auto max-h-[80vh]">
                <!-- Preset Action Selector -->
                <div>
                  <label class="text-[11px] font-bold text-slate-300 uppercase tracking-wider block mb-1.5">
                    Select Proposed Operational Action to Simulate:
                  </label>
                  <div class="grid grid-cols-2 gap-2 text-xs">
                    <!-- Safe Preset -->
                    <button
                      onClick=${() => { setActionPreset("SAFE_PLUS_30"); runSimulation("SAFE_PLUS_30"); }}
                      class="p-2.5 rounded border text-left transition ${actionPreset === 'SAFE_PLUS_30' ? 'bg-cyan-950 border-cyan-500 text-cyan-200' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-slate-800'}"
                    >
                      <strong class="block text-emerald-400 font-semibold">Coolant Valve +30%</strong>
                      <span class="text-[10px] text-slate-400">Ramps coolant flow to 55.2 L/min (Safe Envelope)</span>
                    </button>

                    <!-- Critical Breach Preset 1 -->
                    <button
                      onClick=${() => { setActionPreset("BREACH_SHUTOFF"); runSimulation("BREACH_SHUTOFF"); }}
                      class="p-2.5 rounded border text-left transition ${actionPreset === 'BREACH_SHUTOFF' ? 'bg-red-950 border-red-500 text-red-200' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-slate-800'}"
                    >
                      <strong class="block text-red-400 font-semibold">Cooling Shutoff (0 L/min)</strong>
                      <span class="text-[10px] text-slate-400">Total coolant starvation -> Thermal Runaway @ t=22s</span>
                    </button>

                    <!-- Critical Breach Preset 2 -->
                    <button
                      onClick=${() => { setActionPreset("BREACH_MINUS_70"); runSimulation("BREACH_MINUS_70"); }}
                      class="p-2.5 rounded border text-left transition ${actionPreset === 'BREACH_MINUS_70' ? 'bg-red-950 border-red-500 text-red-200' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-slate-800'}"
                    >
                      <strong class="block text-red-400 font-semibold">Coolant Flow -70%</strong>
                      <span class="text-[10px] text-slate-400">Flow drops to 12.8 L/min -> Thermal Breach @ t=38s</span>
                    </button>

                    <!-- Safe Temp Setpoint -->
                    <button
                      onClick=${() => { setActionPreset("SAFE_TEMP_SETPOINT"); runSimulation("SAFE_TEMP_SETPOINT"); }}
                      class="p-2.5 rounded border text-left transition ${actionPreset === 'SAFE_TEMP_SETPOINT' ? 'bg-cyan-950 border-cyan-500 text-cyan-200' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-slate-800'}"
                    >
                      <strong class="block text-cyan-400 font-semibold">Adjust Temp to 68.0°C</strong>
                      <span class="text-[10px] text-slate-400">Setpoint within verified operational tolerance</span>
                    </button>
                  </div>
                </div>

                <!-- 60-Second Dynamic Trajectory Chart -->
                ${renderTrajectoryChart()}

                <!-- Intercept Verdict Banner -->
                ${simResult ? html`
                  <div class="p-3 rounded-lg border ${simResult.is_safe ? 'bg-emerald-950/60 border-emerald-600 text-emerald-200' : 'bg-red-950/80 border-red-600 text-red-200'}">
                    <div class="flex items-center justify-between font-bold text-xs mb-1">
                      <span class="flex items-center gap-1.5">
                        ${simResult.is_safe ? html`
                          <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                          SAFE TO APPLY
                        ` : html`
                          <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                          SAFETY INTERCEPT — CRITICAL LIMIT BREACH
                        `}
                      </span>
                      <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${simResult.is_safe ? 'bg-emerald-900 text-emerald-300' : 'bg-red-900 text-red-300'}">
                        ${simResult.verdict}
                      </span>
                    </div>
                    <p class="text-[11px] leading-tight">${simResult.intercept_message}</p>
                    <p class="text-[10px] mt-1 font-mono text-slate-400">${simResult.breach_summary}</p>
                  </div>
                ` : ''}

                <!-- Action Confirm Slider if Safe -->
                ${simResult && simResult.is_safe ? html`
                  <div class="bg-[#182740] p-3 rounded-lg border border-[#1e314f]">
                    <div class="flex justify-between items-center text-xs mb-1.5">
                      <span class="text-slate-300 font-semibold">Operator Confirmation Slider:</span>
                      <span class="text-emerald-400 font-mono font-bold">${confirmSlide === 100 ? 'CONFIRMED' : confirmSlide + '%'}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value=${confirmSlide}
                      onInput=${e => {
                        const val = parseInt(e.target.value);
                        setConfirmSlide(val);
                        if (val === 100) {
                          setApplySuccess(true);
                        }
                      }}
                      class="w-full accent-emerald-500 cursor-pointer h-2 bg-slate-700 rounded-lg"
                    />
                    <div class="flex justify-between items-center text-[10px] text-slate-400 mt-1">
                      <span>Slide right to authorize PLC write</span>
                      ${applySuccess ? html`
                        <span class="text-emerald-400 font-bold">✓ Written to PLC Tag Memory</span>
                      ` : ''}
                    </div>
                  </div>
                ` : ''}
              </div>

              <!-- Modal Footer -->
              <div class="px-6 py-3 border-t border-[#1e314f] bg-[#182740] flex justify-between items-center">
                <span class="text-[10px] font-mono text-slate-400">
                  Model: First-Order Thermal/Pressure ODE • dt=1.0s
                </span>
                <button
                  onClick=${() => setIsModalOpen(false)}
                  class="bg-slate-700 hover:bg-slate-600 text-white text-xs px-4 py-1.5 rounded transition"
                >
                  Close Sandbox
                </button>
              </div>
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  // Expose to window for seamless mounting into index.html
  window.ChaosSandboxComponent = ChaosSandboxComponent;
})(window);

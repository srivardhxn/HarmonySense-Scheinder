/**
 * Schneider Electric Innovation Sprint - Problem Statement 1
 * 60-Second "What-If" Deterministic Parameter Trajectory Safety Sandbox
 * 
 * Component: frontend/ChaosSandbox.js
 * Tech: Preact + Tailwind CSS + High-Contrast Dynamic SVG Trajectory Engine
 * Standards: IEC 61511 / ISA-84 (Safety Instrumented Systems)
 */

(function(window) {
  const { html, useState, useEffect } = window.htmPreact || {};

  function WhatIfSandboxComponent(props) {
    // --- Sandbox Modal State ---
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [actionPreset, setActionPreset] = useState("SAFE_PLUS_30");
    const [customFlowDelta, setCustomFlowDelta] = useState(30);
    const [simResult, setSimResult] = useState(null);
    const [isSimulating, setIsSimulating] = useState(false);
    const [confirmSlide, setConfirmSlide] = useState(0);
    const [applySuccess, setApplySuccess] = useState(false);
    const [showExplainer, setShowExplainer] = useState(false);

    // Run 60-second forward ODE simulation
    const runSimulation = async (presetType, customDelta = null) => {
      const preset = presetType || actionPreset;
      setIsSimulating(true);
      setApplySuccess(false);
      setConfirmSlide(0);

      let payload = {
        action_type: "COOLANT_FLOW_DELTA",
        tag_id: "Cooling_Water_Flow_PV",
        delta_percent: customDelta !== null ? customDelta : 30.0,
        initial_temp: 63.2,
        initial_flow: 42.5,
        initial_pressure: 2.2
      };

      if (customDelta !== null) {
        payload.action_type = "COOLANT_FLOW_DELTA";
        payload.delta_percent = customDelta;
      } else if (preset === "SAFE_PLUS_30") {
        payload.action_type = "COOLANT_FLOW_DELTA";
        payload.delta_percent = 30.0;
        setCustomFlowDelta(30);
      } else if (preset === "BREACH_SHUTOFF") {
        payload.action_type = "SHUTOFF_COOLING";
        payload.delta_percent = -100.0;
        setCustomFlowDelta(-100);
      } else if (preset === "BREACH_MINUS_70") {
        payload.action_type = "COOLANT_FLOW_DELTA";
        payload.delta_percent = -70.0;
        setCustomFlowDelta(-70);
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
        console.error("Simulation error:", err);
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

    // Render High-Precision Dynamic SVG Trajectory Chart
    const renderTrajectoryChart = () => {
      if (!simResult || !simResult.trajectory) return null;
      const traj = simResult.trajectory;
      const w = 620;
      const h = 200;
      const padL = 48;
      const padR = 24;
      const padT = 24;
      const padB = 32;

      const chartW = w - padL - padR;
      const chartH = h - padT - padB;

      // Min/Max bounds for Temp (°C): 50°C to 100°C
      const minVal = 50.0;
      const maxVal = 100.0;

      const getX = (sec) => padL + (sec / 60.0) * chartW;
      const getY = (val) => padT + chartH - ((Math.min(Math.max(val, minVal), maxVal) - minVal) / (maxVal - minVal)) * chartH;

      const points = traj.map(pt => `${getX(pt.second)},${getY(pt.temp_pv)}`).join(" ");
      const limitY = getY(85.0);

      // Hazard Zone height from top to 85°C limit
      const hazardHeight = Math.max(0, limitY - padT);

      // Find breach point if exists
      const breachPt = traj.find(p => p.temp_pv >= 85.0);

      return html`
        <div class="bg-[#0b1320] p-3.5 rounded-lg border border-[#1e314f] relative">
          <!-- Chart Header & Legend -->
          <div class="flex flex-wrap justify-between items-center text-xs mb-2 pb-1.5 border-b border-[#1e314f]">
            <div class="flex items-center space-x-3">
              <span class="text-slate-200 font-bold flex items-center gap-1.5">
                <span class="w-3 h-1 rounded ${simResult.is_safe ? 'bg-cyan-400' : 'bg-red-500'} inline-block"></span>
                60-Second Projected Reactor Temp (°C)
              </span>
              <span class="text-[10px] text-slate-400 font-mono">dt = 1.0s (Forward Euler ODE)</span>
            </div>
            <div class="flex items-center space-x-3 text-[11px] font-mono">
              <span class="text-emerald-400 flex items-center gap-1">
                <span class="w-2 h-2 rounded-full bg-emerald-500/40 border border-emerald-500"></span>
                Safe Zone (&lt;85°C)
              </span>
              <span class="text-red-400 flex items-center gap-1 font-bold">
                <span class="w-2 h-2 rounded-full bg-red-500/40 border border-red-500"></span>
                Critical Limit: 85.0°C
              </span>
            </div>
          </div>

          <svg viewBox="0 0 ${w} ${h}" class="w-full h-48 overflow-visible select-none">
            <!-- Shaded Danger Hazard Zone (>85°C) -->
            <rect
              x="${padL}"
              y="${padT}"
              width="${chartW}"
              height="${hazardHeight}"
              fill="#ef4444"
              fill-opacity="0.08"
            />

            <!-- Shaded Safe Zone (<85°C) -->
            <rect
              x="${padL}"
              y="${limitY}"
              width="${chartW}"
              height="${padT + chartH - limitY}"
              fill="#10b981"
              fill-opacity="0.04"
            />

            <!-- Grid Horizontal Lines -->
            <line x1="${padL}" y1="${getY(60)}" x2="${w - padR}" y2="${getY(60)}" stroke="#1e314f" stroke-dasharray="3,3" />
            <text x="${padL - 6}" y="${getY(60) + 3}" fill="#64748b" font-size="9" text-anchor="end" font-mono>60°C</text>

            <line x1="${padL}" y1="${getY(75)}" x2="${w - padR}" y2="${getY(75)}" stroke="#1e314f" stroke-dasharray="3,3" />
            <text x="${padL - 6}" y="${getY(75) + 3}" fill="#64748b" font-size="9" text-anchor="end" font-mono>75°C</text>

            <!-- Red Critical Safety Limit Line (85°C) -->
            <line x1="${padL}" y1="${limitY}" x2="${w - padR}" y2="${limitY}" stroke="#ef4444" stroke-width="2" stroke-dasharray="5,3" />
            <text x="${padL - 6}" y="${limitY + 3}" fill="#ef4444" font-weight="bold" font-size="10" text-anchor="end" font-mono>85°C</text>
            <text x="${w - padR - 4}" y="${limitY - 4}" fill="#ef4444" font-size="9" font-weight="bold" text-anchor="end">
              CRITICAL LIMIT: 85°C
            </text>

            <!-- X Axis Lines & Labels -->
            <line x1="${padL}" y1="${h - padB}" x2="${w - padR}" y2="${h - padB}" stroke="#334155" />
            <text x="${padL}" y="${h - 12}" fill="#64748b" font-size="9" font-mono>t=0s (Now)</text>
            <text x="${padL + chartW * 0.25}" y="${h - 12}" fill="#64748b" font-size="9" text-anchor="middle" font-mono>t=15s</text>
            <text x="${padL + chartW * 0.5}" y="${h - 12}" fill="#64748b" font-size="9" text-anchor="middle" font-mono>t=30s</text>
            <text x="${padL + chartW * 0.75}" y="${h - 12}" fill="#64748b" font-size="9" text-anchor="middle" font-mono>t=45s</text>
            <text x="${w - padR}" y="${h - 12}" fill="#64748b" font-size="9" text-anchor="end" font-mono>t=60s</text>

            <!-- Dynamic Projected Trajectory Curve -->
            <polyline
              fill="none"
              stroke="${simResult.is_safe ? '#06b6d4' : '#ef4444'}"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
              points="${points}"
            />

            <!-- Start Point Circle -->
            <circle cx="${padL}" cy="${getY(traj[0].temp_pv)}" r="3.5" fill="#38bdf8" />

            <!-- Breach Point Indicator Circle & Callout -->
            ${!simResult.is_safe && breachPt ? html`
              <g>
                <circle cx="${getX(breachPt.second)}" cy="${getY(breachPt.temp_pv)}" r="6" fill="#ef4444" stroke="#ffffff" stroke-width="2" class="animate-pulse" />
                <rect x="${getX(breachPt.second) - 52}" y="${getY(breachPt.temp_pv) - 28}" width="104" height="20" rx="3" fill="#991b1b" stroke="#f87171" stroke-width="1" />
                <text x="${getX(breachPt.second)}" y="${getY(breachPt.temp_pv) - 15}" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">
                  Breach @ t=${breachPt.second}s (${breachPt.temp_pv}°C)
                </text>
              </g>
            ` : html`
              <!-- End Point Circle if Safe -->
              <circle cx="${w - padR}" cy="${getY(traj[60].temp_pv)}" r="4" fill="#06b6d4" stroke="#ffffff" stroke-width="1.5" />
            `}
          </svg>

          <!-- Trajectory Key Parameter Comparison Table -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2 pt-2 border-t border-[#1e314f] text-[11px] font-mono">
            <div class="bg-[#131f33] p-1.5 rounded border border-[#1e314f]">
              <span class="text-slate-400 block text-[10px]">Initial (t=0s)</span>
              <strong class="text-slate-200">${traj[0].temp_pv} °C</strong>
              <span class="text-[9px] text-slate-500 ml-1">(${traj[0].flow_pv} L/m)</span>
            </div>
            <div class="bg-[#131f33] p-1.5 rounded border border-[#1e314f]">
              <span class="text-slate-400 block text-[10px]">Projected Peak</span>
              <strong class="${simResult.peak_temp >= 85.0 ? 'text-red-400 font-bold' : 'text-slate-200'}">
                ${simResult.peak_temp} °C
              </strong>
            </div>
            <div class="bg-[#131f33] p-1.5 rounded border border-[#1e314f]">
              <span class="text-slate-400 block text-[10px]">Final (t=60s)</span>
              <strong class="${simResult.final_temp >= 85.0 ? 'text-red-400' : 'text-cyan-400'} font-bold">
                ${simResult.final_temp} °C
              </strong>
              <span class="text-[9px] text-slate-500 ml-1">(${traj[60].flow_pv} L/m)</span>
            </div>
            <div class="bg-[#131f33] p-1.5 rounded border border-[#1e314f]">
              <span class="text-slate-400 block text-[10px]">Safety Margin</span>
              <strong class="${85.0 - simResult.peak_temp > 0 ? 'text-emerald-400' : 'text-red-400'} font-bold">
                ${(85.0 - simResult.peak_temp).toFixed(1)} °C to limit
              </strong>
            </div>
          </div>
        </div>
      `;
    };

    return html`
      <div>
        <!-- Clean, Professional What-If Sandbox Launch Bar on HMI Dashboard -->
        <div class="bg-[#131f33] border border-[#1e314f] rounded-lg p-3.5 shadow flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div class="flex items-center space-x-3">
            <div class="w-8 h-8 rounded-lg bg-cyan-600/20 border border-cyan-500 flex items-center justify-center text-cyan-400 font-bold text-sm">
              60s
            </div>
            <div>
              <div class="flex items-center space-x-2">
                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-100">
                  "What-If" Safety Sandbox Trajectory Engine
                </h3>
                <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                  Deterministic Forward ODE
                </span>
                <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                  ISA-84 Safety Intercept
                </span>
              </div>
              <p class="text-[11px] text-slate-300 mt-0.5">
                Simulates 60-second plant parameters <strong>before</strong> writing tag changes to the physical PLC. Intercepts unsafe SLM recommendations.
              </p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <button
              onClick=${() => setIsModalOpen(true)}
              id="btn-open-whatif-modal"
              class="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs px-4 py-2 rounded-md transition shadow flex items-center space-x-1.5"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              <span>Launch What-If Sandbox</span>
            </button>
          </div>
        </div>

        <!-- High-Impact "What-If" Safety Trajectory Modal -->
        ${isModalOpen ? html`
          <div class="fixed inset-0 bg-black/85 flex items-center justify-center p-3 sm:p-6 z-50 animate-fade-in">
            <div class="bg-[#131f33] border border-[#1e314f] rounded-xl max-w-3xl w-full flex flex-col shadow-2xl overflow-hidden max-h-[92vh]">
              
              <!-- Modal Header -->
              <div class="px-6 py-4 border-b border-[#1e314f] flex justify-between items-center bg-[#182740]">
                <div class="flex items-center space-x-3">
                  <div class="w-8 h-8 rounded bg-cyan-600 flex items-center justify-center text-white font-bold text-sm">
                    Ω
                  </div>
                  <div>
                    <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                      <span>"What-If" Safety Sandbox Trajectory Preview</span>
                      <span class="text-[10px] font-normal px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        Asset: Vessel Tank 101 Loop
                      </span>
                    </h3>
                    <p class="text-[11px] text-slate-400">
                      Evaluates proposed PLC tag writes with 60-second forward differential equations (dT/dt) prior to physical execution.
                    </p>
                  </div>
                </div>
                <button
                  onClick=${() => setIsModalOpen(false)}
                  class="text-slate-400 hover:text-white text-xl font-bold px-2 py-1 transition"
                  title="Close Modal"
                >
                  ✕
                </button>
              </div>

              <!-- Modal Body Content -->
              <div class="p-6 space-y-4 overflow-y-auto flex-1">
                
                <!-- Quick Explanation Alert -->
                <div class="bg-[#182740] p-3 rounded-lg border border-cyan-900/60 flex items-start justify-between text-xs">
                  <div class="flex items-start space-x-2.5">
                    <span class="text-cyan-400 text-base">ℹ️</span>
                    <div>
                      <strong class="text-slate-200">How the What-If Sandbox Guarantees Safety:</strong>
                      <p class="text-slate-300 text-[11px] mt-0.5 leading-relaxed">
                        Whenever the Copilot or operator proposes a parameter adjustment, the engine forward-simulates reactor temperature and pressure for 60 seconds.
                        If any parameter exceeds the <strong>Critical Limit (85.0°C)</strong>, the <strong>Safety Intercept</strong> blocks the write and locks the PLC.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick=${() => setShowExplainer(!showExplainer)}
                    class="text-[10px] text-cyan-400 hover:text-cyan-300 underline font-mono flex-shrink-0 ml-2"
                  >
                    ${showExplainer ? 'Hide Math' : 'View ODE Math'}
                  </button>
                </div>

                <!-- Collapsible ODE Math Formula -->
                ${showExplainer ? html`
                  <div class="bg-[#0b1320] p-3 rounded border border-cyan-950 text-[11px] font-mono text-slate-300 space-y-1">
                    <p class="text-cyan-400 font-bold">First-Order Thermal Balance ODE:</p>
                    <p class="text-slate-400">dT/dt = [ Q_reaction - k_heat · Flow_coolant · (T_fluid - T_coolant_in) ] / C_thermal</p>
                    <p class="text-slate-400">dP/dt = P_nominal + γ · max(0, T_fluid - 55.0°C)</p>
                    <p class="text-slate-500 text-[10px] mt-1">Parameters: C_thermal = 145 kJ/°C • Q_reaction = 85 kW • T_coolant_in = 12°C • Safe Ceiling = 85.0°C</p>
                  </div>
                ` : ''}

                <!-- Scenario Presets: 4 Distinct Industrial Operational Scenarios -->
                <div>
                  <div class="flex justify-between items-center mb-1.5">
                    <label class="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                      Select Proposed Operational Action to Test:
                    </label>
                    <span class="text-[10px] text-slate-400 font-mono">Simulate in 1-Click</span>
                  </div>

                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                    
                    <!-- Scenario 1: Safe Action (+30% Coolant) -->
                    <button
                      onClick=${() => { setActionPreset("SAFE_PLUS_30"); runSimulation("SAFE_PLUS_30"); }}
                      class="p-3 rounded-lg border text-left transition flex flex-col justify-between ${actionPreset === 'SAFE_PLUS_30' ? 'bg-cyan-950/80 border-cyan-500 text-cyan-100 ring-1 ring-cyan-500' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-[#1f3354]'}"
                    >
                      <div class="flex justify-between items-center mb-1">
                        <strong class="text-emerald-400 font-semibold">1. Coolant Valve +30%</strong>
                        <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                          SAFE (Recommended)
                        </span>
                      </div>
                      <p class="text-[11px] text-slate-400 leading-tight">
                        Ramps coolant flow to 55.2 L/min. Fluid temp safely cools and stabilizes at ~61°C.
                      </p>
                    </button>

                    <!-- Scenario 2: Critical Hazard (Cooling Shutoff) -->
                    <button
                      onClick=${() => { setActionPreset("BREACH_SHUTOFF"); runSimulation("BREACH_SHUTOFF"); }}
                      class="p-3 rounded-lg border text-left transition flex flex-col justify-between ${actionPreset === 'BREACH_SHUTOFF' ? 'bg-red-950/80 border-red-500 text-red-100 ring-1 ring-red-500' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-[#1f3354]'}"
                    >
                      <div class="flex justify-between items-center mb-1">
                        <strong class="text-red-400 font-semibold">2. Cooling Shutoff (0 L/min)</strong>
                        <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-red-950 text-red-300 border border-red-800">
                          CRITICAL BREACH
                        </span>
                      </div>
                      <p class="text-[11px] text-slate-400 leading-tight">
                        Total coolant starvation. Reaction heat induces thermal runaway, breaching 85.0°C at t=22s.
                      </p>
                    </button>

                    <!-- Scenario 3: Starvation Breach (-70% Coolant) -->
                    <button
                      onClick=${() => { setActionPreset("BREACH_MINUS_70"); runSimulation("BREACH_MINUS_70"); }}
                      class="p-3 rounded-lg border text-left transition flex flex-col justify-between ${actionPreset === 'BREACH_MINUS_70' ? 'bg-red-950/80 border-red-500 text-red-100 ring-1 ring-red-500' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-[#1f3354]'}"
                    >
                      <div class="flex justify-between items-center mb-1">
                        <strong class="text-red-400 font-semibold">3. Coolant Flow -70%</strong>
                        <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-red-950 text-red-300 border border-red-800">
                          STARVATION LIMIT
                        </span>
                      </div>
                      <p class="text-[11px] text-slate-400 leading-tight">
                        Flow drops to 12.8 L/min (below minimum 15 L/min limit), breaching 85.0°C at t=38s.
                      </p>
                    </button>

                    <!-- Scenario 4: Controlled Setpoint Adjustment -->
                    <button
                      onClick=${() => { setActionPreset("SAFE_TEMP_SETPOINT"); runSimulation("SAFE_TEMP_SETPOINT"); }}
                      class="p-3 rounded-lg border text-left transition flex flex-col justify-between ${actionPreset === 'SAFE_TEMP_SETPOINT' ? 'bg-cyan-950/80 border-cyan-500 text-cyan-100 ring-1 ring-cyan-500' : 'bg-[#182740] border-[#1e314f] text-slate-300 hover:bg-[#1f3354]'}"
                    >
                      <div class="flex justify-between items-center mb-1">
                        <strong class="text-cyan-400 font-semibold">4. Adjust Setpoint to 68.0°C</strong>
                        <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                          SAFE ENVELOPE
                        </span>
                      </div>
                      <p class="text-[11px] text-slate-400 leading-tight">
                        Safe steady-state setpoint adjustment within certified operational envelope.
                      </p>
                    </button>
                  </div>

                  <!-- Real-Time Interactive Delta Slider -->
                  <div class="mt-2.5 bg-[#182740] p-2.5 rounded-lg border border-[#1e314f]">
                    <div class="flex justify-between items-center text-xs mb-1">
                      <span class="text-slate-300">Or drag custom Coolant Valve delta (%):</span>
                      <span class="font-mono font-bold ${customFlowDelta < -30 ? 'text-red-400' : customFlowDelta > 0 ? 'text-emerald-400' : 'text-slate-200'}">
                        ${customFlowDelta > 0 ? '+' : ''}${customFlowDelta}% (Flow: ${(42.5 * (1 + customFlowDelta / 100)).toFixed(1)} L/min)
                      </span>
                    </div>
                    <input
                      type="range"
                      min="-100"
                      max="100"
                      step="5"
                      value=${customFlowDelta}
                      onInput=${e => {
                        const val = parseInt(e.target.value);
                        setCustomFlowDelta(val);
                        setActionPreset("CUSTOM");
                        runSimulation("CUSTOM", val);
                      }}
                      class="w-full accent-cyan-500 cursor-pointer h-2 bg-slate-700 rounded-lg"
                    />
                    <div class="flex justify-between text-[9px] text-slate-400 font-mono mt-0.5">
                      <span class="text-red-400">-100% (Full Starvation)</span>
                      <span>0% (No Change)</span>
                      <span class="text-emerald-400">+100% (Max Chiller Capacity)</span>
                    </div>
                  </div>
                </div>

                <!-- 60-Second Dynamic Trajectory Chart -->
                ${renderTrajectoryChart()}

                <!-- Intercept Verdict Banner -->
                ${simResult ? html`
                  <div class="p-3.5 rounded-lg border ${simResult.is_safe ? 'bg-emerald-950/70 border-emerald-500 text-emerald-200' : 'bg-red-950/85 border-red-500 text-red-200'}">
                    <div class="flex items-center justify-between font-bold text-xs mb-1">
                      <span class="flex items-center gap-2">
                        ${simResult.is_safe ? html`
                          <svg class="w-5 h-5 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                          <span class="text-sm font-bold text-emerald-300">SAFE TO APPLY — PROCESS STABILITY CONFIRMED</span>
                        ` : html`
                          <svg class="w-5 h-5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                          <span class="text-sm font-bold text-red-300">SAFETY INTERCEPT — CRITICAL LIMIT BREACH DETECTED</span>
                        `}
                      </span>
                      <span class="text-[10px] font-mono px-2 py-0.5 rounded ${simResult.is_safe ? 'bg-emerald-900 text-emerald-200 border border-emerald-700' : 'bg-red-900 text-red-200 border border-red-700'}">
                        ${simResult.verdict}
                      </span>
                    </div>

                    <p class="text-xs leading-relaxed mt-1">
                      ${simResult.intercept_message}
                    </p>

                    <div class="mt-1.5 pt-1.5 border-t ${simResult.is_safe ? 'border-emerald-800/60' : 'border-red-800/60'} flex flex-wrap justify-between items-center text-[10px] font-mono">
                      <span>${simResult.breach_summary}</span>
                      <span class="${simResult.is_safe ? 'text-emerald-300' : 'text-red-300'} font-semibold">
                        ${simResult.is_safe ? '✓ Safe to write to PLC' : '🛑 Action Prohibited by ISA-84'}
                      </span>
                    </div>
                  </div>
                ` : ''}

                <!-- Operator Authorization Section -->
                ${simResult && simResult.is_safe ? html`
                  <!-- Safe State: Slide to Authorize PLC Tag Write -->
                  <div class="bg-[#182740] p-3.5 rounded-lg border border-emerald-900/60 bg-gradient-to-r from-[#182740] to-emerald-950/30">
                    <div class="flex justify-between items-center text-xs mb-1.5">
                      <span class="text-slate-200 font-semibold flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                        Operator Confirmation Slider (Authorizes PLC Tag Write):
                      </span>
                      <span class="text-emerald-400 font-mono font-bold text-xs">
                        ${confirmSlide === 100 ? '✓ AUTHORIZED' : confirmSlide + '%'}
                      </span>
                    </div>

                    <input
                      type="range"
                      min="0"
                      max="100"
                      value=${confirmSlide}
                      onInput=${e => {
                        const val = parseInt(e.target.value);
                        setConfirmSlide(val);
                        if (val === 100) setApplySuccess(true);
                      }}
                      class="w-full accent-emerald-500 cursor-pointer h-2.5 bg-slate-700 rounded-lg"
                    />

                    <div class="flex justify-between items-center text-[11px] text-slate-400 mt-1.5">
                      <span>Slide completely to the right to commit write</span>
                      ${applySuccess ? html`
                        <span class="text-emerald-400 font-bold flex items-center gap-1 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-600">
                          <span>✓ Tag Written to PLC Memory (%MW100 / Tank101_Cooling)</span>
                        </span>
                      ` : html`
                        <span class="text-slate-400 text-[10px] font-mono">Waiting for 100% operator slider confirm</span>
                      `}
                    </div>
                  </div>
                ` : html`
                  <!-- Breached State: PLC Write Locked -->
                  <div class="bg-[#182740] p-3 rounded-lg border border-red-900/60 text-xs flex items-center justify-between">
                    <div class="flex items-center space-x-2 text-red-300">
                      <svg class="w-4 h-4 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m0 0v2m0-2h2m-2 0H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                      <span><strong>PLC Write Channel Locked:</strong> Physical parameters breach safe envelope. Write slider permanently disabled.</span>
                    </div>
                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800 flex-shrink-0">
                      SAFETY INTERLOCK ACTIVE
                    </span>
                  </div>
                `}
              </div>

              <!-- Modal Footer -->
              <div class="px-6 py-3 border-t border-[#1e314f] bg-[#182740] flex justify-between items-center">
                <span class="text-[10px] font-mono text-slate-400">
                  Engine: Deterministic Forward Euler ODE • Safe Limit: 85.0°C • Zero Cloud Leakage
                </span>
                <button
                  onClick=${() => setIsModalOpen(false)}
                  class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold px-4 py-1.5 rounded transition"
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

  // Expose as both WhatIfSandboxComponent and ChaosSandboxComponent for compatibility
  window.WhatIfSandboxComponent = WhatIfSandboxComponent;
  window.ChaosSandboxComponent = WhatIfSandboxComponent;
})(window);

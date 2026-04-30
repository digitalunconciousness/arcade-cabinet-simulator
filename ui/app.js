// license:CC0-1.0
// Cabinet-bus UI — Phase 3 demo.
// Vanilla JS, no framework. Talks to /api/manifest and /api/run.

(() => {
  const els = {
    status:        document.getElementById("status"),
    schematic:     document.getElementById("schematic"),
    faultPinsG:    document.getElementById("fault-pins"),
    faultsList:    document.getElementById("faults-list"),
    resetButton:   document.getElementById("reset-faults"),
    waveMeta:      document.getElementById("wave-meta"),
    popover:       document.getElementById("popover"),
    popoverTitle:  document.getElementById("popover-title"),
    popoverMeta:   document.getElementById("popover-meta"),
    popoverMode:   document.getElementById("popover-mode"),
    popoverClose:  document.getElementById("popover-close"),
    mamePane:        document.getElementById("mame-pane"),
    mameOffline:     document.getElementById("mame-pane-offline"),
    mameRom:         document.getElementById("mame-rom"),
    mamePaused:      document.getElementById("mame-paused"),
    mameFrame:       document.getElementById("mame-frame"),
    mameVersion:     document.getElementById("mame-version"),
    mamePauseBtn:    document.getElementById("mame-pause"),
    mameResumeBtn:   document.getElementById("mame-resume"),
    mameResetBtn:    document.getElementById("mame-reset"),
  };

  /** @type {{fault_targets: Array, log_nets: string[], duration_s: number, modes: object}} */
  let manifest = null;

  /** @type {Object<string, number>} */
  const faults = {};

  // Layout for the fault-pin badges. Keyed by fault_device. The (x, y) is the
  // SVG coordinate where the badge should sit. Tuned to match index.html.
  const PIN_LAYOUT = {
    FB_CLK_Q:   { x: 150, y: 160, anchor: "above" },
    FB_H_LO_RC: { x: 315, y: 190, anchor: "above" },
    FB_H_HI_RC: { x: 480, y: 190, anchor: "above" },
    FB_H_HI_QB: { x: 600, y:  80, anchor: "above" },
    FB_H_HI_QC: { x: 580, y:  80, anchor: "above" },
    FB_H_HI_QD: { x: 560, y:  80, anchor: "above" },
    FB_V_LO_QC: { x: 555, y: 270, anchor: "below" },
    FB_V_LO_QD: { x: 575, y: 270, anchor: "below" },
  };

  const MODE_CLASS = {
    0: "normal",
    1: "stuck-hi",
    2: "stuck-lo",
    3: "open",
  };

  // ---------- networking ----------

  async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    return await res.json();
  }

  async function reloadWaveforms() {
    setStatus("running nltool…");
    try {
      const data = await fetchJSON("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ faults }),
      });
      const ms = data.duration_s * 1000;
      els.waveMeta.textContent =
        `simulation window: ${ms.toFixed(3)} ms · faults active: ${data.fault_mode_count}`;
      for (const net of manifest.log_nets) {
        renderWaveform(net, data.waveforms[net] || [], data.duration_s);
      }
      setStatus("ready");
    } catch (err) {
      setStatus("error: " + err.message, true);
    }
  }

  // ---------- rendering ----------

  function setStatus(msg, isError = false) {
    els.status.textContent = msg;
    els.status.classList.toggle("error", isError);
  }

  function renderFaultPins() {
    while (els.faultPinsG.firstChild) els.faultPinsG.removeChild(els.faultPinsG.firstChild);
    for (const target of manifest.fault_targets) {
      const layout = PIN_LAYOUT[target.fault_device];
      if (!layout) continue;

      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", layout.x);
      c.setAttribute("cy", layout.y);
      c.setAttribute("r", 7);
      c.setAttribute("class", `fault-pin ${MODE_CLASS[faults[target.fault_device] ?? 0]}`);
      c.dataset.faultDevice = target.fault_device;
      c.dataset.refdes = target.refdes;
      c.dataset.pin = target.pin;
      c.addEventListener("click", openPopover);
      els.faultPinsG.appendChild(c);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "fault-pin-label");
      label.setAttribute("x", layout.x);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("y", layout.anchor === "above" ? layout.y - 12 : layout.y + 18);
      label.textContent = `${target.refdes}.${target.pin}`;
      els.faultPinsG.appendChild(label);
    }
  }

  function renderFaultsList() {
    const active = Object.entries(faults).filter(([, m]) => m !== 0);
    if (active.length === 0) {
      els.faultsList.innerHTML =
        `<div class="empty-faults">No faults injected. Click a pin in the schematic to break something.</div>`;
      els.resetButton.disabled = true;
      return;
    }
    els.faultsList.innerHTML = "";
    for (const [fault_device, mode] of active) {
      const target = manifest.fault_targets.find(t => t.fault_device === fault_device);
      const row = document.createElement("div");
      row.className = "fault-row";
      row.innerHTML = `
        <div class="fault-name">${fault_device}</div>
        <div class="fault-pin">${target.refdes}.${target.pin}</div>
        <div class="fault-mode">mode ${mode} — ${manifest.modes[mode]}</div>
      `;
      els.faultsList.appendChild(row);
    }
    els.resetButton.disabled = false;
  }

  function renderWaveform(net, samples, duration_s) {
    const canvas = document.getElementById(`wave-${net}`);
    if (!canvas) return;
    const cssWidth = canvas.clientWidth;
    const cssHeight = canvas.height;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== cssWidth * dpr) {
      canvas.width = cssWidth * dpr;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    // Background grid: vertical lines every 10% of the duration window.
    ctx.strokeStyle = "#21262d";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 10; i++) {
      const x = (i / 10) * cssWidth;
      ctx.moveTo(x, 0);
      ctx.lineTo(x, cssHeight);
    }
    // Horizontal: low / high reference lines.
    ctx.moveTo(0, cssHeight - 10);  ctx.lineTo(cssWidth, cssHeight - 10);
    ctx.moveTo(0, 10);              ctx.lineTo(cssWidth, 10);
    ctx.stroke();

    // Empty case.
    if (samples.length === 0) {
      ctx.fillStyle = "#8b949e";
      ctx.font = "12px ui-monospace, monospace";
      ctx.fillText("no samples", 8, 20);
      return;
    }

    // Map (t, v) -> (x, y). v is in volts (0..5); fold to 0..1.
    const yTop = 10, yBot = cssHeight - 10;
    const xOf = t => (t / duration_s) * cssWidth;
    const yOf = v => yBot - Math.max(0, Math.min(1, v / 5)) * (yBot - yTop);

    ctx.strokeStyle = "#3fb950";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let first = true;
    let lastX = 0, lastY = 0;
    for (const [t, v] of samples) {
      const x = xOf(t);
      const y = yOf(v);
      if (first) {
        ctx.moveTo(x, y);
        first = false;
      } else {
        // Step transition: draw to (x, lastY) then to (x, y).
        ctx.lineTo(x, lastY);
        ctx.lineTo(x, y);
      }
      lastX = x;
      lastY = y;
    }
    // Continue the final value to the right edge of the canvas.
    ctx.lineTo(cssWidth, lastY);
    ctx.stroke();
  }

  // ---------- popover ----------

  let popoverFault = null;

  function openPopover(ev) {
    const c = ev.currentTarget;
    const fault_device = c.dataset.faultDevice;
    popoverFault = fault_device;

    els.popoverTitle.textContent = fault_device;
    els.popoverMeta.textContent = `${c.dataset.refdes}.${c.dataset.pin}`;
    els.popoverMode.value = String(faults[fault_device] ?? 0);

    // Position next to the SVG circle.
    const rect = c.getBoundingClientRect();
    els.popover.hidden = false;
    els.popover.style.top  = `${window.scrollY + rect.bottom + 8}px`;
    els.popover.style.left = `${window.scrollX + rect.left  - 100}px`;
  }

  function closePopover() {
    popoverFault = null;
    els.popover.hidden = true;
  }

  els.popoverMode.addEventListener("change", async (e) => {
    if (!popoverFault) return;
    const mode = parseInt(e.target.value, 10);
    if (mode === 0) {
      delete faults[popoverFault];
    } else {
      faults[popoverFault] = mode;
    }
    renderFaultPins();
    renderFaultsList();
    await reloadWaveforms();
  });

  els.popoverClose.addEventListener("click", closePopover);
  document.addEventListener("click", (ev) => {
    if (!els.popover.hidden &&
        !els.popover.contains(ev.target) &&
        !ev.target.classList?.contains("fault-pin")) {
      closePopover();
    }
  });

  els.resetButton.addEventListener("click", async () => {
    for (const k of Object.keys(faults)) delete faults[k];
    renderFaultPins();
    renderFaultsList();
    await reloadWaveforms();
  });

  // ---------- MAME bridge ----------

  async function pollMameOnce() {
    try {
      const res = await fetch("/api/mame/state");
      if (res.status === 503) {
        showMame(null);
        return;
      }
      if (!res.ok) {
        showMame(null);
        return;
      }
      const data = await res.json();
      if (data.available === false) {
        showMame(null);
      } else {
        showMame(data);
      }
    } catch {
      showMame(null);
    }
  }

  function showMame(data) {
    if (!data) {
      els.mamePane.hidden = true;
      els.mameOffline.hidden = false;
      return;
    }
    els.mamePane.hidden = false;
    els.mameOffline.hidden = true;
    els.mameRom.textContent = data.rom || "—";
    els.mamePaused.textContent = data.paused ? "PAUSED" : "running";
    els.mamePaused.classList.toggle("paused", !!data.paused);
    els.mameFrame.textContent = data.frame ?? "—";
    els.mameVersion.textContent = `${data.app || "mame"} ${data.version || ""}`.trim();
    els.mamePauseBtn.disabled  = !!data.paused;
    els.mameResumeBtn.disabled = !data.paused;
  }

  async function mameAction(path) {
    try {
      const res = await fetch(`/api/mame/${path}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        showMame(data.available === false ? null : data);
      }
    } catch (e) {
      console.error("mame action", path, e);
    }
  }

  els.mamePauseBtn.addEventListener("click",  () => mameAction("pause"));
  els.mameResumeBtn.addEventListener("click", () => mameAction("resume"));
  els.mameResetBtn.addEventListener("click",  () => mameAction("soft_reset"));

  // ---------- bootstrap ----------

  async function init() {
    setStatus("fetching manifest…");
    try {
      manifest = await fetchJSON("/api/manifest");
    } catch (err) {
      setStatus("manifest error: " + err.message, true);
      return;
    }
    renderFaultPins();
    renderFaultsList();
    await reloadWaveforms();
    pollMameOnce();
    setInterval(pollMameOnce, 1000);
  }

  init();
})();

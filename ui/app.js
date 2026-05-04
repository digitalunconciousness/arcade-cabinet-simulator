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
    mameVideoCol:    document.getElementById("mame-video-col"),
    mameVideoFeed:   document.getElementById("mame-video-feed"),
    mameVideoUnavail: document.getElementById("mame-video-unavail"),
    mameRom:         document.getElementById("mame-rom"),
    mamePaused:      document.getElementById("mame-paused"),
    mameFrame:       document.getElementById("mame-frame"),
    mameVersion:     document.getElementById("mame-version"),
    mamePauseBtn:    document.getElementById("mame-pause"),
    mameResumeBtn:   document.getElementById("mame-resume"),
    mameResetBtn:    document.getElementById("mame-reset"),
    mameKbHeld:      document.getElementById("mame-kb-held"),
    periphGrid:      document.getElementById("peripherals-grid"),
    periphReset:     document.getElementById("peripherals-reset"),
    crtPreview:      document.getElementById("crt-preview"),
    crtPreviewMeta:  document.getElementById("crt-preview-meta"),
    trackballPad:    document.getElementById("trackball-pad"),
    trackballMeta:   document.getElementById("trackball-meta"),
    audioMeta:       document.getElementById("audio-meta"),
    audioToneStart:  document.getElementById("audio-tone-start"),
    audioToneStop:   document.getElementById("audio-tone-stop"),
    // Scenario bar
    scenarioSelect:   document.getElementById("scenario-select"),
    scenarioApply:    document.getElementById("scenario-apply"),
    scenarioClear:    document.getElementById("scenario-clear"),
    scenarioInfo:     document.getElementById("scenario-info"),
    scenarioTitle:    document.getElementById("scenario-title"),
    scenarioSubs:     document.getElementById("scenario-subs"),
    scenarioStory:    document.getElementById("scenario-story"),
    scenarioBanner:   document.getElementById("scenario-active-banner"),
    bannerTitle:      document.getElementById("banner-title"),
    bannerSubs:       document.getElementById("banner-subs"),
  };

  /** @type {{fault_targets: Array, log_nets: string[], duration_s: number, modes: object}} */
  let manifest = null;

  /** @type {Object<string, number>} */
  const faults = {};

  /** @type {any|null} */
  let crtState = null;
  /** @type {any|null} */
  let trackballState = null;
  /** @type {any|null} */
  let audioState = null;

  let audioCtx = null;
  let audioToneOsc = null;
  let audioHumOsc = null;
  let audioToneGain = null;
  let audioHumGain = null;
  let audioDrive = null;
  let audioLowpass = null;
  let audioMaster = null;
  let lastAudioProfileSig = "";

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

  const EXPECTED_MANIFEST_VERSION = 1;

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

  // ---------- Peripherals (Phase 4) ----------

  async function loadPeripherals() {
    try {
      const data = await fetchJSON("/api/peripherals/state");
      renderPeripherals(data.peripherals);
      crtState = data.peripherals.find(p => p.type === "crt") || null;
      trackballState = data.peripherals.find(p => p.type === "trackball") || null;
      audioState = data.peripherals.find(p => p.type === "audio_chain") || null;
      renderCrtPreview();
      renderTrackballMeta();
      const nextAudioSig = audioState
        ? JSON.stringify({
            fault: audioState.fault,
            filter_params: audioState.filter_params,
          })
        : "";
      if (nextAudioSig !== lastAudioProfileSig) {
        applyAudioFaultProfile();
        lastAudioProfileSig = nextAudioSig;
      }
    } catch (err) {
      console.error("peripherals load failed", err);
    }
  }

  function renderPeripherals(items) {
    els.periphGrid.innerHTML = "";
    for (const p of items) {
      els.periphGrid.appendChild(renderPeripheralCard(p));
    }
  }

  function renderPeripheralCard(p) {
    const card = document.createElement("div");
    card.className = "periph-card" + (p.fault !== "NORMAL" ? " faulted" : "");

    const head = document.createElement("div");
    head.className = "periph-card-head";
    head.innerHTML = `
      <div>
        <div class="periph-card-type">${p.type}</div>
        <div class="periph-card-id">${p.id}${p.label ? " — " + p.label : ""}</div>
      </div>
      <div class="periph-card-status${p.fault !== "NORMAL" ? " faulted" : ""}">${p.fault}</div>
    `;
    card.appendChild(head);

    if (p.type === "psu") {
      // Rails readout.
      const rails = document.createElement("div");
      rails.className = "periph-rails";
      for (const [name, v] of Object.entries(p.rails)) {
        const cls = railClass(name, v);
        rails.innerHTML += `
          <div class="periph-rail">
            <div class="periph-rail-name">${name}</div>
            <div class="periph-rail-value ${cls}">${v.toFixed(2)} V</div>
          </div>`;
      }
      card.appendChild(rails);

      // Ripple.
      const ripple = document.createElement("div");
      ripple.className = "periph-stat";
      const rcls = p.ripple_mv_pp > 200 ? (p.ripple_mv_pp > 1000 ? "bad" : "warn") : "";
      ripple.innerHTML = `<span>ripple</span><span class="periph-stat-value ${rcls}">${p.ripple_mv_pp.toFixed(0)} mV pp</span>`;
      card.appendChild(ripple);

      // Trim pot slider.
      const spec = p.supported_params.trim_5v;
      const trimWrap = document.createElement("div");
      trimWrap.className = "trim-row";
      const trimLabel = document.createElement("div");
      trimLabel.innerHTML = `<label>5 V trim pot</label>`;
      const trimVal = document.createElement("span");
      trimVal.className = "periph-stat-value";
      trimVal.textContent = `${p.trim_5v.toFixed(2)} V`;
      trimLabel.appendChild(trimVal);
      const trim = document.createElement("input");
      trim.type = "range";
      trim.min = spec.min;  trim.max = spec.max;  trim.step = spec.step;
      trim.value = p.trim_5v;
      trim.addEventListener("input", () => { trimVal.textContent = `${parseFloat(trim.value).toFixed(2)} V`; });
      trim.addEventListener("change", async () => {
        await postJSON("/api/peripherals/adjust",
                       { id: p.id, param: "trim_5v", value: parseFloat(trim.value) });
        await loadPeripherals();
      });
      trimWrap.appendChild(trimLabel);
      trimWrap.appendChild(trim);
      card.appendChild(trimWrap);
    }

    if (p.type === "coin_mech") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      stat.innerHTML = `<span>credits</span><span class="periph-stat-value">${p.credits}</span>`;
      card.appendChild(stat);
      const last = document.createElement("div");
      last.className = "periph-stat";
      last.innerHTML = `<span>last event</span><span class="periph-stat-value">${p.last_event}</span>`;
      card.appendChild(last);
      const btn = document.createElement("button");
      btn.className = "periph-action";
      btn.textContent = "Insert coin";
      btn.addEventListener("click", async () => {
        await postJSON("/api/peripherals/coin", {});
        await loadPeripherals();
      });
      card.appendChild(btn);
    }

    if (p.type === "marquee") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      const cls = p.visible_state === "on" ? "" : "warn";
      stat.innerHTML = `<span>tube</span><span class="periph-stat-value ${cls}">${p.visible_state}</span>`;
      card.appendChild(stat);
    }

    if (p.type === "harness") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      stat.innerHTML = `<span>${p.src} → ${p.dst}</span><span class="periph-stat-value"></span>`;
      card.appendChild(stat);
    }

    if (p.type === "crt") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      stat.innerHTML = `<span>effective brightness</span><span class="periph-stat-value">${p.effective_brightness.toFixed(2)}</span>`;
      card.appendChild(stat);
      const sync = document.createElement("div");
      sync.className = "periph-stat";
      sync.innerHTML = `<span>sync lock</span><span class="periph-stat-value ${p.sync_ok ? "" : "warn"}">${p.sync_ok ? "locked" : "unlock"}</span>`;
      card.appendChild(sync);
      renderParamSliders(card, p, ["brightness", "focus"]);
    }

    if (p.type === "trackball") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      stat.innerHTML = `<span>last packet</span><span class="periph-stat-value">dx ${p.last_packet.quad_dx} · dy ${p.last_packet.quad_dy}</span>`;
      card.appendChild(stat);
      renderParamSliders(card, p, ["sensitivity", "wear"]);
    }

    if (p.type === "audio_chain") {
      const stat = document.createElement("div");
      stat.className = "periph-stat";
      stat.innerHTML = `<span>gain</span><span class="periph-stat-value">${p.filter_params.gain.toFixed(2)}</span>`;
      card.appendChild(stat);
      renderParamSliders(card, p, ["master_gain", "hum_level", "distortion_drive"]);
    }

    // Fault dropdown for everything that has fault modes.
    if (p.supported_faults && p.supported_faults.length) {
      const wrap = document.createElement("div");
      wrap.innerHTML = `<label for="flt-${p.id}">Fault mode</label>`;
      const sel = document.createElement("select");
      sel.id = `flt-${p.id}`;
      sel.innerHTML = `<option value="">NORMAL</option>` +
        p.supported_faults.map(f => `<option value="${f}">${f}</option>`).join("");
      sel.value = p.fault === "NORMAL" ? "" : p.fault;
      sel.addEventListener("change", async () => {
        await postJSON("/api/peripherals/fault",
                       { id: p.id, fault: sel.value });
        await loadPeripherals();
      });
      wrap.appendChild(sel);
      card.appendChild(wrap);
    }

    return card;
  }

  function renderParamSliders(card, p, names) {
    for (const name of names) {
      const spec = p.supported_params?.[name];
      if (!spec) continue;
      const wrap = document.createElement("div");
      wrap.className = "trim-row";
      const label = document.createElement("div");
      label.innerHTML = `<label>${name}</label>`;
      const val = document.createElement("span");
      val.className = "periph-stat-value";
      val.textContent = Number(p[name]).toFixed(2);
      label.appendChild(val);
      const range = document.createElement("input");
      range.type = "range";
      range.min = spec.min;
      range.max = spec.max;
      range.step = spec.step;
      range.value = p[name];
      range.addEventListener("input", () => {
        val.textContent = Number(range.value).toFixed(2);
      });
      range.addEventListener("change", async () => {
        await postJSON("/api/peripherals/adjust", {
          id: p.id,
          param: name,
          value: parseFloat(range.value),
        });
        await loadPeripherals();
      });
      wrap.appendChild(label);
      wrap.appendChild(range);
      card.appendChild(wrap);
    }
  }

  function railClass(name, v) {
    if (v === 0) return "bad";
    if (name === "5V") {
      if (v < 4.75 || v > 5.25) return "warn";
      if (v < 4.5  || v > 5.5)  return "bad";
    } else if (name === "12V") {
      if (v < 11.4 || v > 12.6) return "warn";
    }
    return "";
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.ok ? await res.json() : null;
  }

  els.periphReset.addEventListener("click", async () => {
    await postJSON("/api/peripherals/reset", {});
    await loadPeripherals();
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

  let _mameWasAvailable = false;

  function showMame(data) {
    if (!data) {
      els.mamePane.hidden = true;
      els.mameOffline.hidden = false;
      _mameWasAvailable = false;
      return;
    }
    initMameVideo();
    els.mamePane.hidden = false;
    els.mameOffline.hidden = true;
    if (!_mameWasAvailable) {
      // Defensive reset so stale held movement state cannot linger.
      _kbHeldMove.clear();
      _updateKbHeldDisplay();
    }
    _mameWasAvailable = true;
    els.mameRom.textContent = data.rom || "—";
    els.mamePaused.textContent = data.paused ? "PAUSED" : "running";
    els.mamePaused.classList.toggle("paused", !!data.paused);
    els.mameFrame.textContent = data.frame ?? "—";
    els.mameVersion.textContent = `${data.app || "mame"} ${data.version || ""}`.trim();
    els.mamePauseBtn.disabled  = !!data.paused;
    els.mameResumeBtn.disabled = !data.paused;
  }

    // Probe /api/mame/video/available and wire up the MJPEG <img> feed.
    // Retries until available so late-starting Xvfb is picked up automatically.
    let _videoInitDone = false;
    async function initMameVideo() {
      if (_videoInitDone) return;
      try {
        const res = await fetch("/api/mame/video/available");
        const data = res.ok ? await res.json() : { available: false };
        if (data.available) {
          _videoInitDone = true;
          els.mameVideoFeed.src = "/api/mame/video";
          els.mameVideoFeed.hidden = false;
          els.mameVideoUnavail.hidden = true;
          // Reload the stream if the browser drops it (Xvfb restart, etc.)
          els.mameVideoFeed.addEventListener("error", () => {
            _videoInitDone = false;
            els.mameVideoFeed.hidden = true;
            els.mameVideoUnavail.hidden = false;
          });
        } else {
          els.mameVideoFeed.hidden = true;
          els.mameVideoUnavail.hidden = false;
          // Don't set _videoInitDone — will retry on next poll cycle.
        }
      } catch {
        els.mameVideoFeed.hidden = true;
        els.mameVideoUnavail.hidden = false;
      }
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

  function refreshMameVideoStream() {
    if (!els.mameVideoFeed) return;
    // Reconnect so the server can rebuild ffmpeg filters from current CRT state.
    els.mameVideoFeed.src = `/api/mame/video?t=${Date.now()}`;
  }

  els.mamePauseBtn.addEventListener("click",  () => mameAction("pause"));
  els.mameResumeBtn.addEventListener("click", () => mameAction("resume"));
  els.mameResetBtn.addEventListener("click",  () => mameAction("soft_reset"));

  // ---------- Phase 6 preview ----------

  function renderCrtPreview() {
    if (!els.crtPreview || !crtState) return;
    const canvas = els.crtPreview;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    // Base test pattern (standalone, no MAME framebuffer dependency).
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, w, h);
    const bars = ["#ffffff", "#ffd400", "#00d4ff", "#2bd900", "#d94d2b", "#ff00ff", "#2a6bff", "#333333"];
    const bw = Math.floor(w / bars.length);
    bars.forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.fillRect(i * bw, 10, bw, Math.floor(h * 0.45));
    });
    ctx.strokeStyle = "#73ff7a";
    ctx.lineWidth = 2;
    for (let y = 0; y < h; y += 8) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(w, y + 0.5);
      ctx.stroke();
    }

    // Apply effect profile approximating shader categories.
    const effect = crtState.shader_effect || "crt_normal";
    if (effect === "crt_vertical_collapse") {
      ctx.globalAlpha = 0.9;
      ctx.drawImage(canvas, 0, Math.floor(h * 0.48), w, 4, 0, Math.floor(h * 0.44), w, 16);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(255,255,255,0.15)";
      ctx.fillRect(0, Math.floor(h * 0.49), w, 2);
    } else if (effect === "crt_horizontal_collapse") {
      ctx.globalAlpha = 0.9;
      ctx.drawImage(canvas, Math.floor(w * 0.48), 0, 4, h, Math.floor(w * 0.44), 0, 16, h);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(255,255,255,0.15)";
      ctx.fillRect(Math.floor(w * 0.49), 0, 2, h);
    } else if (effect === "crt_sync_lock_failure") {
      const dy = Math.floor(((Date.now() / 20) % h));
      const img = ctx.getImageData(0, 0, w, h);
      ctx.putImageData(img, 0, dy - h);
      ctx.putImageData(img, 0, dy);
    } else if (effect === "crt_weak_focus") {
      ctx.globalAlpha = 0.4;
      ctx.drawImage(canvas, -1, 0);
      ctx.drawImage(canvas, 1, 0);
      ctx.drawImage(canvas, 0, -1);
      ctx.drawImage(canvas, 0, 1);
      ctx.globalAlpha = 1;
    } else if (effect === "crt_bad_deflection_caps") {
      for (let y = 0; y < h; y += 2) {
        const offset = Math.round(Math.sin((y / 13) + (Date.now() / 180)) * 4);
        ctx.drawImage(canvas, 0, y, w, 2, offset, y, w, 2);
      }
    } else if (effect === "crt_ringing_ghosting") {
      ctx.globalAlpha = 0.22;
      ctx.drawImage(canvas, 8, 0);
      ctx.globalAlpha = 1;
    }

    const b = Math.max(0, Math.min(2, crtState.effective_brightness || 1));
    const alpha = Math.max(0, Math.min(0.92, 1 - (b / 1.2)));
    ctx.fillStyle = `rgba(0,0,0,${alpha})`;
    ctx.fillRect(0, 0, w, h);

    els.crtPreviewMeta.textContent = `effect: ${effect} · brightness: ${b.toFixed(2)}`;
  }

  function renderTrackballMeta() {
    if (!els.trackballMeta) return;
    const packet = trackballState?.last_packet || { quad_dx: 0, quad_dy: 0 };
    els.trackballMeta.textContent = `dx ${packet.quad_dx} · dy ${packet.quad_dy}`;
  }

  async function postTrackballMotion(dx, dy) {
    try {
      await postJSON("/api/trackball/motion", { dx, dy });
      await loadPeripherals();
    } catch (e) {
      console.error("trackball motion failed", e);
    }
  }

  function initTrackballPad() {
    if (!els.trackballPad) return;
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    els.trackballPad.addEventListener("pointerdown", (ev) => {
      dragging = true;
      lastX = ev.clientX;
      lastY = ev.clientY;
      els.trackballPad.classList.add("dragging");
      els.trackballPad.setPointerCapture(ev.pointerId);
    });
    els.trackballPad.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const dx = Math.round(ev.clientX - lastX);
      const dy = Math.round(ev.clientY - lastY);
      lastX = ev.clientX;
      lastY = ev.clientY;
      if (dx !== 0 || dy !== 0) {
        void postTrackballMotion(dx, dy);
      }
    });
    const stopDrag = () => {
      dragging = false;
      els.trackballPad.classList.remove("dragging");
    };
    els.trackballPad.addEventListener("pointerup", stopDrag);
    els.trackballPad.addEventListener("pointercancel", stopDrag);
  }

  // ---------- Keyboard controls for MAME ----------
  //
  // Rather than going through the Lua TCP plugin (which has polarity bugs,
  // axis inversion, and HTTP round-trip lag), we inject events directly into
  // the MAME X11 window on the Xvfb display via xdotool.  MAME receives the
  // same events as if a real keyboard/mouse were attached — no Lua glue needed.
  //
  // Key layout (matches MAME's default centiped3 bindings):
  //   Space / LCtrl  → P1 Button 1 (fire)   → xdotool key "ctrl"
  //   5              → Coin 1                → xdotool key "5"
  //   1              → 1 Player Start        → xdotool key "1"
  //   2              → 2 Players Start       → xdotool key "2"
  //   WASD           → trackball             → xdotool mousemove_relative

  // ev.code → xdotool key name for momentary / toggled buttons.
  const KEY_XDOTOOL_MAP = {
    ControlLeft:  "ctrl",   // P1 Button 1
    Digit1:       "1",
    Digit2:       "2",
    Digit5:       "5",
    Numpad1:      "1",
    Numpad2:      "2",
    Numpad5:      "5",
    Escape:       "Escape",
  };

  // WASD → xdotool arrow key events (MAME's native keyboard trackball emulation).
  // Arrow keys avoid all cursor-boundary issues; MAME handles sensitivity internally.
  const KEY_TRACKBALL_CODE_MAP = {
    KeyA: "Left",
    KeyD: "Right",
    KeyW: "Up",
    KeyS: "Down",
  };

  // Currently held state for WASD arrow keys only.
  // Buttons use atomic xdotool key (no open hold state, nothing can get stuck).
  const _kbHeldMove   = new Set();

  function _updateKbHeldDisplay() {
    if (!els.mameKbHeld) return;
    els.mameKbHeld.textContent = _kbHeldMove.size
      ? "held: " + [..._kbHeldMove].join(" + ")
      : "";
  }

  function _xdoKey(action, key) {
    postJSON("/api/mame/xkey", { action, key }).catch(() => {});
  }

  function _xdoMouse(dx, dy) {
    postJSON("/api/mame/xmouse", { dx, dy }).catch(() => {});
  }

  function initKeyboardControls() {
    const isTypingTarget = (el) =>
      el.tagName === "INPUT" || el.tagName === "SELECT" ||
      el.tagName === "TEXTAREA" || el.isContentEditable;

    const focusMamePane = () => {
      if (!els.mamePane) return;
      if (els.mamePane.tabIndex < 0) els.mamePane.tabIndex = 0;
      try { els.mamePane.focus({ preventScroll: true }); }
      catch { els.mamePane.focus(); }
    };

    els.mamePane?.addEventListener("pointerdown", focusMamePane);
    setTimeout(focusMamePane, 0);

    document.addEventListener("keydown", (ev) => {
      if (els.mamePane?.hidden) return;
      if (isTypingTarget(ev.target)) return;

      // WASD → arrow key hold (MAME native trackball emulation)
      const arrowKey = KEY_TRACKBALL_CODE_MAP[ev.code];
      if (arrowKey) {
        if (_kbHeldMove.has(ev.code)) return; // already held
        ev.preventDefault();
        _kbHeldMove.add(ev.code);
        _xdoKey("keydown", arrowKey);
        _updateKbHeldDisplay();
        return;
      }

      // Button → atomic xdotool key (press+release in one shot).
      // This prevents stuck-key: if keyup is ever lost (tab switch, Ctrl+R,
      // any browser shortcut), nothing stays held in X11.
      // OS key-repeat sends repeated keydown events → repeated atomic fires.
      const xkey = KEY_XDOTOOL_MAP[ev.code];
      if (xkey) {
        ev.preventDefault();
        ev.stopPropagation();
        _xdoKey("key", xkey);
      }
    }, true);

    document.addEventListener("keyup", (ev) => {
      if (isTypingTarget(ev.target)) return;

      const arrowKey = KEY_TRACKBALL_CODE_MAP[ev.code];
      if (arrowKey && _kbHeldMove.has(ev.code)) {
        _kbHeldMove.delete(ev.code);
        _xdoKey("keyup", arrowKey);
        _updateKbHeldDisplay();
        return;
      }
      // No keyup handling needed for button keys — atomic presses have no open state.
    }, true);

    // Release held movement keys if the browser tab loses focus.
    window.addEventListener("blur", () => {
      for (const code of _kbHeldMove) {
        const ak = KEY_TRACKBALL_CODE_MAP[code];
        if (ak) _xdoKey("keyup", ak);
      }
      _kbHeldMove.clear();
      _updateKbHeldDisplay();
    });
  }

  function initMouseControls() {
    if (!els.mameVideoCol) return;

    let dragging = false;
    let activePointerId = null;
    let lastX = 0;
    let lastY = 0;

    // Make sure we never leave the user in pointer-lock mode.
    if (document.pointerLockElement && document.exitPointerLock) {
      document.exitPointerLock();
    }

    els.mameVideoCol.addEventListener("pointerdown", (ev) => {
      if (els.mamePane?.hidden) return;
      // Center the Xvfb cursor so the drag has full room in every direction.
      postJSON("/api/mame/xcenter", {}).catch(() => {});
      dragging = true;
      activePointerId = ev.pointerId;
      lastX = ev.clientX;
      lastY = ev.clientY;
      if (typeof els.mameVideoCol.setPointerCapture === "function") {
        els.mameVideoCol.setPointerCapture(ev.pointerId);
      }
      els.mameVideoCol.classList.add("dragging");
      ev.preventDefault();
    });

    els.mameVideoCol.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      if (activePointerId !== null && ev.pointerId !== activePointerId) return;
      const dx = Math.round(ev.clientX - lastX);
      const dy = Math.round(ev.clientY - lastY);
      lastX = ev.clientX;
      lastY = ev.clientY;
      if (dx !== 0 || dy !== 0) _xdoMouse(dx, dy);
    });

    const stopDrag = (ev) => {
      if (!dragging) return;
      if (ev && activePointerId !== null && ev.pointerId !== activePointerId) return;
      dragging = false;
      if (activePointerId !== null && typeof els.mameVideoCol.releasePointerCapture === "function") {
        try {
          els.mameVideoCol.releasePointerCapture(activePointerId);
        } catch {}
      }
      activePointerId = null;
      els.mameVideoCol.classList.remove("dragging");
    };

    els.mameVideoCol.addEventListener("pointerup", stopDrag);
    els.mameVideoCol.addEventListener("pointercancel", stopDrag);
    els.mameVideoCol.addEventListener("pointerleave", stopDrag);

    window.addEventListener("blur", () => {
      dragging = false;
      activePointerId = null;
      els.mameVideoCol.classList.remove("dragging");
    });
  }

  function createDistortionCurve(amount) {
    const k = Math.max(0, amount) * 400;
    const n = 512;
    const curve = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i * 2) / n - 1;
      curve[i] = ((3 + k) * x * 20 * (Math.PI / 180)) / (Math.PI + (k * Math.abs(x)));
    }
    return curve;
  }

  async function ensureAudioGraph() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    audioToneOsc = audioCtx.createOscillator();
    audioToneOsc.type = "square";
    audioToneOsc.frequency.value = 523.25;

    audioHumOsc = audioCtx.createOscillator();
    audioHumOsc.type = "sine";
    audioHumOsc.frequency.value = 60;

    audioToneGain = audioCtx.createGain();
    audioToneGain.gain.value = 0;
    audioHumGain = audioCtx.createGain();
    audioHumGain.gain.value = 0;
    audioDrive = audioCtx.createWaveShaper();
    audioDrive.curve = createDistortionCurve(0);
    audioLowpass = audioCtx.createBiquadFilter();
    audioLowpass.type = "lowpass";
    audioLowpass.frequency.value = 12000;
    audioMaster = audioCtx.createGain();
    audioMaster.gain.value = 1.0;

    audioToneOsc.connect(audioToneGain);
    audioHumOsc.connect(audioHumGain);
    audioToneGain.connect(audioDrive);
    audioHumGain.connect(audioDrive);
    audioDrive.connect(audioLowpass);
    audioLowpass.connect(audioMaster);
    audioMaster.connect(audioCtx.destination);

    audioToneOsc.start();
    audioHumOsc.start();
  }

  function applyAudioFaultProfile() {
    if (!audioState || !els.audioMeta) return;
    els.audioMeta.textContent = `fault: ${audioState.fault}`;
    if (!audioCtx) return;
    const fp = audioState.filter_params || {};
    audioMaster.gain.value = fp.gain ?? 1.0;
    audioHumOsc.frequency.value = fp.hum_hz ?? 60;
    audioHumGain.gain.value = fp.hum_gain ?? 0.0;
    audioLowpass.frequency.value = fp.speaker_lowpass_hz ?? 12000;
    audioDrive.curve = createDistortionCurve(fp.distortion_drive ?? 0);
  }

  async function startTone() {
    await ensureAudioGraph();
    if (audioCtx.state === "suspended") {
      await audioCtx.resume();
    }
    audioToneGain.gain.value = 0.2;
    applyAudioFaultProfile();
  }

  function stopTone() {
    if (!audioCtx) return;
    audioToneGain.gain.value = 0;
  }

  // ---------- Scenarios (Phase 7) ----------

  /** @type {Array<{id:string,title:string,difficulty:number,subsystems:string[],coverage:string[],backstory:string}>} */
  let scenarios = [];
  let activeScenarioId = null;

  async function loadScenarios() {
    try {
      const data = await fetchJSON("/api/scenarios");
      scenarios = data.scenarios || [];
      if (!els.scenarioSelect) return;
      els.scenarioSelect.innerHTML = `<option value="">— choose a scenario —</option>`;
      for (const s of scenarios) {
        const stars = "★".repeat(s.difficulty || 1);
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = `${stars}  ${s.title}`;
        els.scenarioSelect.appendChild(opt);
      }
    } catch (err) {
      console.error("scenarios load failed", err);
    }
  }

  function getSelectedScenario() {
    const id = els.scenarioSelect?.value;
    return scenarios.find(s => s.id === id) || null;
  }

  function renderScenarioInfo(scenario) {
    if (!els.scenarioInfo) return;
    if (!scenario) {
      els.scenarioInfo.hidden = true;
      return;
    }
    els.scenarioTitle.textContent = scenario.title;
    els.scenarioSubs.textContent  = (scenario.subsystems || []).join(", ");
    els.scenarioStory.textContent = scenario.backstory || "";
    els.scenarioInfo.hidden = false;
  }

  function renderScenarioBanner(scenario) {
    if (!els.scenarioBanner) return;
    if (!scenario) {
      els.scenarioBanner.hidden = true;
      return;
    }
    els.bannerTitle.textContent = scenario.title;
    els.bannerSubs.textContent  = (scenario.subsystems || []).join(", ");
    els.scenarioBanner.hidden = false;
  }

  if (els.scenarioSelect) {
    els.scenarioSelect.addEventListener("change", () => {
      const s = getSelectedScenario();
      renderScenarioInfo(s);
      els.scenarioApply.disabled = !s;
      els.scenarioClear.disabled = !s;
    });
  }

  if (els.scenarioApply) {
    els.scenarioApply.addEventListener("click", async () => {
      const s = getSelectedScenario();
      if (!s) return;
      els.scenarioApply.disabled = true;
      els.scenarioApply.textContent = "Applying…";
      try {
        const result = await postJSON(`/api/scenarios/${encodeURIComponent(s.id)}/apply`, {});
        activeScenarioId = s.id;
        renderScenarioBanner(s);
        refreshMameVideoStream();
        await loadPeripherals();
        if (result && result.mame && result.mame.was_paused) {
          if (result.mame.resumed) {
            setStatus("MAME was paused; resumed automatically before applying fault");
          } else {
            setStatus("MAME is paused; fault may not be visually obvious until resumed", true);
          }
        }
        // Warn if any CRT fault couldn't reach MAME.
        const mameUnreachable = (result.faults || []).some(
          f => f.mame_available === false
        );
        if (mameUnreachable) {
          setStatus("Fault applied — but MAME isn't connected (start via run-demo.sh)", true);
          setTimeout(() => setStatus("ready"), 5000);
        }
      } catch (err) {
        console.error("apply scenario failed", err);
      } finally {
        els.scenarioApply.disabled = false;
        els.scenarioApply.textContent = "Apply";
      }
    });
  }

  if (els.scenarioClear) {
    els.scenarioClear.addEventListener("click", async () => {
      const s = getSelectedScenario();
      if (!s) return;
      els.scenarioClear.disabled = true;
      els.scenarioClear.textContent = "Clearing…";
      try {
        await postJSON(`/api/scenarios/${encodeURIComponent(s.id)}/clear`, {});
        activeScenarioId = null;
        renderScenarioBanner(null);
        refreshMameVideoStream();
        await loadPeripherals();
      } catch (err) {
        console.error("clear scenario failed", err);
      } finally {
        els.scenarioClear.disabled = false;
        els.scenarioClear.textContent = "Clear";
      }
    });
  }

  // ---------- bootstrap ----------

  // ============================================================
  // Board Inspector — Phase 8
  // Loads /api/schematic/summary and renders the three-panel
  // component browser / PCB overview / probe view.
  // ============================================================

  const boardInspector = {
    /** Full summary payload from the server. Null when no board package. */
    summary: null,
    /** Currently selected component ref string. */
    selectedRef: null,
    /** Map of fault_device → mode (int) — mirrors the global `faults` dict. */
    activeFaults: faults,  // same reference — kept in sync automatically
  };

  async function loadBoardInspector() {
    let summary;
    try {
      summary = await fetchJSON("/api/schematic/summary");
    } catch {
      // Board package not available — hide inspector and return.
      const el = document.getElementById("board-inspector");
      if (el) el.hidden = true;
      return;
    }

    if (!summary || !summary.board_id) {
      const el = document.getElementById("board-inspector");
      if (el) el.hidden = true;
      return;
    }

    boardInspector.summary = summary;

    // Show the section.
    const section = document.getElementById("board-inspector");
    if (section) section.hidden = false;

    // Populate header.
    const idEl  = document.getElementById("board-inspector-id");
    const revEl = document.getElementById("board-inspector-rev");
    const statsEl = document.getElementById("board-stats");
    if (idEl)  idEl.textContent  = summary.board_id;
    if (revEl) revEl.textContent = `rev ${summary.revision}`;
    if (statsEl) {
      statsEl.textContent =
        `${summary.component_count} components · ` +
        `${summary.net_count} nets · ` +
        `${summary.mapped_fault_count} fault targets`;
    }

    renderComponentList(summary);
    renderPcbGrid(summary);
    renderProbePanel(null, summary);
  }

  /** Render the left-column component browser list. */
  function renderComponentList(summary, filterText = "") {
    const listEl = document.getElementById("component-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    const lower = filterText.toLowerCase();
    const components = (summary.components || []).filter(c => {
      if (!lower) return true;
      return (
        c.ref.toLowerCase().includes(lower) ||
        c.chip_type.toLowerCase().includes(lower)
      );
    });

    if (components.length === 0) {
      listEl.innerHTML = `<div class="comp-type" style="padding:8px 4px;color:var(--fg-dim)">no matches</div>`;
      return;
    }

    for (const comp of components) {
      const item = document.createElement("div");
      item.className = "comp-item";
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", boardInspector.selectedRef === comp.ref ? "true" : "false");
      item.dataset.ref = comp.ref;

      // Check if this component has any active faults.
      const faultDevices = _faultDevicesForRef(comp.ref, summary);
      const hasFault = faultDevices.some(fd => (faults[fd] ?? 0) !== 0);

      if (hasFault) item.classList.add("faulted");
      if (boardInspector.selectedRef === comp.ref) item.classList.add("selected");

      item.innerHTML =
        `<span class="comp-ref">${_esc(comp.ref)}</span>` +
        `<span class="comp-type">${_esc(comp.chip_type)}</span>`;

      item.addEventListener("click", () => selectBoardComponent(comp.ref));
      listEl.appendChild(item);
    }
  }

  /** Render the centre PCB-grid overview. */
  function renderPcbGrid(summary) {
    const gridEl = document.getElementById("pcb-grid");
    if (!gridEl) return;
    gridEl.innerHTML = "";

    for (const comp of (summary.components || [])) {
      const chip = document.createElement("div");
      chip.className = "pcb-chip";
      chip.setAttribute("role", "listitem");
      chip.dataset.ref = comp.ref;

      const faultDevices = _faultDevicesForRef(comp.ref, summary);
      const activeModes = faultDevices.map(fd => faults[fd] ?? 0).filter(m => m !== 0);
      const hasFault = activeModes.length > 0;

      if (hasFault) chip.classList.add("faulted");
      if (boardInspector.selectedRef === comp.ref) chip.classList.add("selected");

      const faultLabel = hasFault
        ? `<div class="pcb-chip-fault">${activeModes.length} fault${activeModes.length > 1 ? "s" : ""}</div>`
        : "";

      chip.innerHTML =
        `<div class="pcb-chip-ref">${_esc(comp.ref)}</div>` +
        `<div class="pcb-chip-type">${_esc(comp.chip_type)}</div>` +
        faultLabel;

      chip.addEventListener("click", () => selectBoardComponent(comp.ref));
      gridEl.appendChild(chip);
    }
  }

  /** Select a component and update both list + PCB grid selection state. */
  function selectBoardComponent(ref) {
    boardInspector.selectedRef = ref;
    // Update CSS selection in list.
    document.querySelectorAll(".comp-item").forEach(el => {
      el.classList.toggle("selected", el.dataset.ref === ref);
      el.setAttribute("aria-selected", el.dataset.ref === ref ? "true" : "false");
    });
    // Update CSS selection in grid.
    document.querySelectorAll(".pcb-chip").forEach(el => {
      el.classList.toggle("selected", el.dataset.ref === ref);
    });
    renderProbePanel(ref, boardInspector.summary);
  }

  /** Render the right-column probe/inspect panel. */
  function renderProbePanel(ref, summary) {
    const placeholder = document.getElementById("probe-placeholder");
    const detail = document.getElementById("probe-detail");
    if (!placeholder || !detail) return;

    if (!ref || !summary) {
      placeholder.hidden = false;
      detail.hidden = true;
      return;
    }

    const comp = (summary.components || []).find(c => c.ref === ref);
    if (!comp) {
      placeholder.hidden = false;
      detail.hidden = true;
      return;
    }

    placeholder.hidden = true;
    detail.hidden = false;

    const refEl  = document.getElementById("probe-ref");
    const chipEl = document.getElementById("probe-chip");
    const descEl = document.getElementById("probe-desc");
    const netsEl = document.getElementById("probe-nets");
    const pinsEl = document.getElementById("probe-pins");
    const hintEl = document.getElementById("probe-fault-hint");

    if (refEl)  refEl.textContent  = comp.ref;
    if (chipEl) chipEl.textContent = comp.chip_type;
    if (descEl) descEl.textContent = comp.description || "";

    // Nets
    if (netsEl) {
      const nets = comp.nets || {};  // { "net_name": ["ref.pin", …], … }
      const entries = Object.entries(nets);
      if (entries.length === 0) {
        netsEl.innerHTML = `<span class="probe-no-nets">no net data</span>`;
      } else {
        netsEl.innerHTML = entries.map(([net, pins]) =>
          `<span class="probe-net-tag">${_esc(net)}</span>`
        ).join("");
      }
    }

    // Fault-injectable pins for this component.
    const faultEntries = (summary.fault_map || []).filter(e => e.ref === ref);
    if (hintEl) {
      hintEl.textContent = faultEntries.length === 0 ? "(none mapped)" : "";
    }

    if (pinsEl) {
      if (faultEntries.length === 0) {
        pinsEl.innerHTML = `<div class="probe-no-faults">No instrumented pins on this component.</div>`;
      } else {
        pinsEl.innerHTML = "";
        for (const entry of faultEntries) {
          pinsEl.appendChild(_buildPinRow(entry));
        }
      }
    }
  }

  /** Build a single fault-injectable pin row for the probe panel. */
  function _buildPinRow(entry) {
    const { ref, pin, net_name, fault_device, fault_type, description } = entry;
    const currentMode = faults[fault_device] ?? 0;
    const isActive = currentMode !== 0;

    const row = document.createElement("div");
    row.className = "probe-pin-row" + (isActive ? " active-fault" : "");
    row.dataset.faultDevice = fault_device;

    const modeNames = ["NORMAL", "STUCK_HI", "STUCK_LO", "OPEN"];
    const badgeClass = ["", "stuck-hi", "stuck-lo", "open"];

    const activeBadge = isActive
      ? `<span class="probe-fault-badge ${badgeClass[currentMode]}">${modeNames[currentMode]}</span>`
      : "";

    const modeOptions = modeNames.map((name, i) =>
      `<option value="${i}" ${currentMode === i ? "selected" : ""}>${i} — ${name}</option>`
    ).join("");

    row.innerHTML =
      `<div class="probe-pin-head">` +
        `<span class="probe-pin-name">.${_esc(pin)}</span>` +
        `<span class="probe-pin-net">${_esc(net_name)}</span>` +
        `<span class="probe-pin-device">${_esc(fault_device)}</span>` +
        activeBadge +
      `</div>` +
      (description ? `<div class="probe-pin-desc">${_esc(description)}</div>` : "") +
      `<div class="probe-pin-controls">` +
        `<select class="probe-mode-select" aria-label="Fault mode for ${_esc(fault_device)}">` +
          modeOptions +
        `</select>` +
        `<button class="probe-apply-btn" type="button">Apply</button>` +
        `<button class="probe-clear-btn" type="button">Clear</button>` +
      `</div>`;

    const select = row.querySelector(".probe-mode-select");
    const applyBtn = row.querySelector(".probe-apply-btn");
    const clearBtn = row.querySelector(".probe-clear-btn");

    async function applyFaultMode(mode) {
      try {
        await postJSON("/api/schematic/fault/apply", {
          fault_device,
          refdes: ref,
          ref,
          pin,
          mode,
        });
        if (mode === 0) {
          delete faults[fault_device];
        } else {
          faults[fault_device] = mode;
        }
        // Refresh the probe panel and PCB grid to reflect new state.
        renderProbePanel(boardInspector.selectedRef, boardInspector.summary);
        renderPcbGrid(boardInspector.summary);
        renderComponentList(boardInspector.summary, _compSearchValue());
        renderFaultPins();
        renderFaultsList();
        await reloadWaveforms();
      } catch (err) {
        setStatus("fault apply error: " + err.message, true);
      }
    }

    applyBtn.addEventListener("click", () => {
      const mode = parseInt(select.value, 10);
      void applyFaultMode(mode);
    });

    clearBtn.addEventListener("click", async () => {
      try {
        await postJSON("/api/schematic/fault/clear", { fault_device });
        delete faults[fault_device];
        renderProbePanel(boardInspector.selectedRef, boardInspector.summary);
        renderPcbGrid(boardInspector.summary);
        renderComponentList(boardInspector.summary, _compSearchValue());
        renderFaultPins();
        renderFaultsList();
        await reloadWaveforms();
      } catch (err) {
        setStatus("fault clear error: " + err.message, true);
      }
    });

    return row;
  }

  /** Return all fault_device names associated with a given component ref. */
  function _faultDevicesForRef(ref, summary) {
    return (summary.fault_map || [])
      .filter(e => e.ref === ref)
      .map(e => e.fault_device);
  }

  /** Return the current component-search input value. */
  function _compSearchValue() {
    const el = document.getElementById("comp-search");
    return el ? el.value.trim() : "";
  }

  /** Escape HTML special characters. */
  function _esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Wire up the component search filter.
  const compSearchInput = document.getElementById("comp-search");
  if (compSearchInput) {
    compSearchInput.addEventListener("input", (e) => {
      if (boardInspector.summary) {
        renderComponentList(boardInspector.summary, e.target.value.trim());
      }
    });
  }

  // ============================================================
  // End of Board Inspector
  // ============================================================

  async function init() {
    setStatus("fetching manifest…");
    try {
      manifest = await fetchJSON("/api/manifest");
      if (manifest.manifest_version !== EXPECTED_MANIFEST_VERSION) {
        throw new Error(
          `manifest version mismatch: expected ${EXPECTED_MANIFEST_VERSION}, got ${manifest.manifest_version}`
        );
      }
      if (!Array.isArray(manifest.fault_targets) || !Array.isArray(manifest.log_nets) || !manifest.modes) {
        throw new Error("manifest payload missing required fields");
      }
    } catch (err) {
      setStatus("manifest error: " + err.message, true);
      return;
    }
    renderFaultPins();
    renderFaultsList();
    await reloadWaveforms();
    await loadPeripherals();
    await loadScenarios();
    await loadBoardInspector();
    initTrackballPad();
    initKeyboardControls();
    initMouseControls();
    if (els.audioToneStart) {
      els.audioToneStart.addEventListener("click", () => { void startTone(); });
    }
    if (els.audioToneStop) {
      els.audioToneStop.addEventListener("click", stopTone);
    }
    pollMameOnce();
    setInterval(pollMameOnce, 1000);
    // Refresh peripherals every 2s so stuck_switch credits keep ticking.
    setInterval(loadPeripherals, 2000);
    setInterval(renderCrtPreview, 80);
  }

  init();
})();

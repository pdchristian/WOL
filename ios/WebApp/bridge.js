/* ══════════════════════════════════════════════════════════════════════════
   bridge.js – Fassade zwischen app.js und nativem Android-Code.

   Echter Modus (WebView):   window.Android.call(callId, method, paramsJson)
                             → Ergebnis asynchron via window.__nativeResult
                             → Events via window.__nativeEvent
   Demo-Modus (Browser):     kein window.Android → Stub mit Prototyp-Daten,
                             damit die UI ohne Gerät weiterentwickelbar ist.
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var hasNative = !!(window.Android && typeof window.Android.call === "function");

  /* ── Ergebnis-/Event-Empfänger (nur im echten Modus benutzt) ───────────── */
  var pending = {};
  var nextId = 1;
  var handlers = {};

  window.__nativeResult = function (callId, res) {
    var fn = pending[callId];
    delete pending[callId];
    if (fn) fn(res);
  };
  window.__nativeEvent = function (ev) {
    var list = handlers[ev.type] || [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](ev); } catch (e) { console.error("event handler", ev.type, e); }
    }
  };

  function on(type, fn) {
    (handlers[type] = handlers[type] || []).push(fn);
  }

  /* ══════════════════════ Echte Brücke ══════════════════════════════════ */
  function callNative(method, params) {
    return new Promise(function (resolve) {
      var id = nextId++;
      pending[id] = resolve;
      try {
        window.Android.call(id, method, JSON.stringify(params || {}));
      } catch (e) {
        delete pending[id];
        resolve({ ok: false, error: String(e) });
      }
    });
  }

  /* ══════════════════════ Demo-Stub (Browser) ═══════════════════════════ */
  var demoDevices = [
    { id: "d1", name: "Fractal", mac: "2C:F0:5D:8E:11:AA", ip: "192.168.2.10", username: "christian",
      enabled: true, hasPassword: true, watch: ["llama-server.exe:8080", "backup.bat"],
      allow_batch: true, batches: [
        { id: "b1", name: "nvidia-smi", script: "nvidia-smi", timeout: 30 },
        { id: "b2", name: "backup.bat", script: "backup.bat", timeout: 300 }] },
    { id: "d2", name: "A4-H20", mac: "60:CF:84:84:31:29", ip: "192.168.2.50", username: "",
      enabled: true, hasPassword: false, watch: [], allow_batch: false, batches: [] },
    { id: "d3", name: "A4-TV", mac: "A0:AD:9F:1C:09:FF", ip: "192.168.2.111", username: "",
      enabled: false, hasPassword: false, watch: [], allow_batch: false, batches: [] },
  ];
  var demoSchedules = [
    { id: "s1", deviceId: "d1", action: "wake", time: "07:00",
      days: ["Mon", "Tue", "Wed", "Thu", "Fri"], enabled: true },
  ];
  var demoLogs = [
    { ts: Date.now() - 3600e3, device: "Fractal", level: "info", msg: "Magic Packet gesendet" },
    { ts: Date.now() - 7200e3, device: "A4-TV", level: "warn", msg: "Gerät antwortet nicht" },
  ];
  var demoSettings = {
    broadcastIp: "255.255.255.255", broadcastPort: 9, language: "",
    displayMode: "auto", autoUpdate: true, interval: "168", maxLogs: 100,
  };
  var demoMetrics = { cpu: 34, ram: 61, gpu: 72, vram: 66 };

  function demoCall(method, p) {
    var r = { ok: true, data: null };
    switch (method) {
      case "snapshot":
        r.data = {
          devices: demoDevices, schedules: demoSchedules,
          logs: demoLogs.slice(0, 100), settings: demoSettings,
        };
        break;
      case "info": r.data = { versionName: "2.3.5-demo", versionCode: 1, protocol: 4 }; break;
      case "saveDevice":
        if (p.password) { /* Demo: verwerfen */ }
        r.data = demoDevices; break;
      case "deleteDevice":
        demoDevices = demoDevices.filter(function (d) { return d.id !== p.id; });
        r.data = demoDevices; break;
      case "getPassword": r.data = ""; break;
      case "saveSchedule": r.data = demoSchedules; break;
      case "deleteSchedule":
        demoSchedules = demoSchedules.filter(function (s) { return s.id !== p.id; });
        r.data = demoSchedules; break;
      case "saveSettings": Object.assign(demoSettings, p || {}); break;
      case "resetSettings":
        Object.assign(demoSettings, { broadcastIp: "255.255.255.255", broadcastPort: 9,
          language: "", displayMode: "auto", autoUpdate: true, interval: "168", maxLogs: 100 });
        break;
      case "clearLogs": demoLogs = []; r.data = []; break;
      case "log":
        demoLogs.unshift({ ts: Date.now(), device: p.device, level: p.level, msg: p.msg });
        break;
      case "wake": case "shutdown": case "status": r.data = true; break;
      case "ping": r.data = Math.round(1 + Math.random() * 8); break;
      case "remote": {
        var rd = demoDevices.find(function (x) { return x.id === p.id; }) || demoDevices[0];
        r.data = { ok: true, host: rd ? rd.ip : "", username: rd ? rd.username : "",
          passwordCopied: false, hasPassword: true };
        break;
      }
      case "metrics":
        demoMetrics.cpu = Math.max(2, Math.min(98, demoMetrics.cpu + Math.round(Math.random() * 18 - 9)));
        demoMetrics.ram = Math.max(20, Math.min(95, demoMetrics.ram + Math.round(Math.random() * 6 - 3)));
        demoMetrics.gpu = Math.max(0, Math.min(99, demoMetrics.gpu + Math.round(Math.random() * 28 - 14)));
        demoMetrics.vram = Math.max(5, Math.min(96, demoMetrics.vram + Math.round(Math.random() * 12 - 6)));
        r.data = {
          protocol: 4, hostname: "fractal", cpu: demoMetrics.cpu, cpuCount: 16,
          ram: demoMetrics.ram, ramUsedGB: 39.2, ramTotalGB: 64,
          uptime: 92400, gpu: demoMetrics.gpu, vram: demoMetrics.vram,
          vramUsedGB: 15.8, vramTotalGB: 24, gpuName: "NVIDIA GeForce RTX 4090",
          processes: [
            { key: "llama-server.exe:8080", running: true, pid: 14432, cpu: 88, ram: 14.2,
              uptime: 3600, model: "Qwen3.8-Flash-256k", apiPort: 8080, apiPortOpen: true,
              models: ["Qwen3.8-Flash-256k", "DeepSeek-R1-Distill-32B"] },
            { key: "backup.bat", running: false, pid: null, cpu: null, ram: null,
              uptime: null, model: null, apiPort: null, apiPortOpen: false, models: [] },
          ],
        };
        break;
      case "runBatch":
        r.data = { exitCode: 0, stdout: "OK (Demo)", stderr: "", durationMs: 42, truncated: false };
        break;
      case "scanIfaces":
        r.data = [{ name: "wlan0", ip: "192.168.2.0", prefix: 24, dns: "192.168.2.1", checked: true }];
        break;
      case "scanStart":
        (function () {
          var total = 254, done = 0;
          var hosts = [
            { ip: "192.168.2.1", host: "fritz.box", known: false },
            { ip: "192.168.2.33", host: "nas01.lan", known: false },
            { ip: "192.168.2.50", host: "a4-h20", known: true },
            { ip: "192.168.2.111", host: "a4-tv", known: true },
          ];
          var tm = setInterval(function () {
            done = Math.min(total, done + 34);
            emit({ type: "scan-progress", done: done, total: total, current: "192.168.2." + done });
            if (done >= total) {
              clearInterval(tm);
              hosts.forEach(function (h) { emit({ type: "scan-found", ip: h.ip, host: h.host, known: h.known, mac: "" }); });
              emit({ type: "scan-done", count: hosts.length });
            }
          }, 200);
        })();
        r.data = true; break;
      case "scanStop": r.data = true; break;
      case "wakeAll":
        (function () {
          var t = 0;
          demoDevices.forEach(function (d) {
            setTimeout(function () { emit({ type: "wake-result", id: d.id, ok: true }); }, (t += 300));
          });
          setTimeout(function () { emit({ type: "wake-all-done", count: demoDevices.length }); }, t + 200);
        })();
        r.data = true; break;
      case "refreshStatus":
        (function () {
          demoDevices.forEach(function (d, i) {
            setTimeout(function () {
              emit({ type: "status", id: d.id, online: d.id === "d1" });
              if (i === demoDevices.length - 1) emit({ type: "status-done" });
            }, 250 * (i + 1));
          });
        })();
        r.data = true; break;
      case "exportDevices": case "exportCsv": case "importDevices": r.data = true; break;
      case "updateCheck": r.data = { state: "latest" }; break;
      case "vibrate": r.data = true; break;
      default: r = { ok: false, error: "demo: unknown " + method };
    }
    return Promise.resolve(r);
  }

  function emit(ev) {
    var list = handlers[ev.type] || [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](ev); } catch (e) { console.error(e); }
    }
  }

  /* ══════════════════════ Öffentliches API ══════════════════════════════ */
  window.Native = {
    demo: !hasNative,
    call: hasNative ? callNative : demoCall,
    on: on,
    setSheetOpen: function (open) {
      if (hasNative) { try { window.Android.setSheetOpen(!!open); } catch (e) { /* egal */ } }
    },
  };
})();

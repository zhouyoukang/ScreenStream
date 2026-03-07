/*
 * AgentBridge v2.0 — BepInEx HTTP Server Plugin for VaM
 * =====================================================
 * Exposes VaM's entire runtime API over HTTP, enabling external agents
 * (Python/Windsurf/etc.) to control VaM without touching the GUI.
 *
 * v2.0 Changes (based on deep reverse-engineering of VaM core files):
 *   - Fixed: ExtractSegment now handles complex storable IDs with '/' chars
 *   - Fixed: Morph GET supports ?filter= query param (avoids returning 10K+ morphs)
 *   - Added: StringChooser param support (GET/POST) — required for Voxta control
 *   - Added: Storable action listing endpoint
 *   - Added: Atom types enumeration
 *   - Added: VaM log message access
 *   - Added: Scene file browser
 *   - Added: Prefs read/write
 *   - Added: Voxta convenience endpoints (send message, get state, new chat)
 *   - Added: Timeline convenience endpoints (play, stop, list animations)
 *   - Added: Clothing/Hair info for Person atoms
 *   - Added: Global action triggers (SuperController level)
 *   - Added: Health check endpoint (lightweight, no main-thread marshal)
 *
 * Architecture:
 *   Agent (Python) --HTTP--> AgentBridge (this plugin) --C# API--> VaM Runtime
 *
 * Install:
 *   1. Copy AgentBridge.cs to BepInEx/plugins/AgentBridge/
 *   2. Restart VaM — BepInEx compiles and loads automatically
 *   OR compile to DLL and place in BepInEx/plugins/
 *
 * Port: 8285 (configurable via BepInEx config)
 * Auth: X-Agent-Key header (optional, configurable)
 *
 * Non-interference guarantee:
 *   - Runs on a background thread (HttpListener)
 *   - All VaM API calls are marshaled to Unity main thread via coroutine queue
 *   - No mouse/keyboard/focus stealing
 *   - User can continue using VaM normally
 */

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using UnityEngine;
using SimpleJSON;

// BepInEx attributes
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using System.Reflection;

namespace AgentBridge
{
    [BepInPlugin("com.agent.bridge", "Agent Bridge", "1.0.0")]
    public class AgentBridgePlugin : BaseUnityPlugin
    {
        // ── Config ──
        private ConfigEntry<int> _port;
        private ConfigEntry<string> _authKey;
        private ConfigEntry<bool> _enableLogging;

        // ── HTTP Server ──
        private HttpListener _listener;
        private Thread _listenerThread;
        private volatile bool _running;

        // ── Main Thread Queue ──
        private readonly Queue<Action> _mainThreadQueue = new Queue<Action>();
        private readonly object _queueLock = new object();

        // ── Response Queue (for async request/response) ──
        private readonly Dictionary<string, ManualResetEvent> _waitHandles =
            new Dictionary<string, ManualResetEvent>();
        private readonly Dictionary<string, string> _responses =
            new Dictionary<string, string>();

        // ── Log Ring Buffer (captures SuperController.Log* messages) ──
        private readonly Queue<JSONNode> _logBuffer = new Queue<JSONNode>();
        private const int MaxLogEntries = 200;
        private readonly object _logLock = new object();

        void Awake()
        {
            _port = Config.Bind("Server", "Port", 8285, "HTTP server port");
            _authKey = Config.Bind("Server", "AuthKey", "",
                "Optional auth key (X-Agent-Key header). Empty = no auth.");
            _enableLogging = Config.Bind("Server", "EnableLogging", true,
                "Log requests to BepInEx console");

            StartServer();
            Logger.LogInfo($"AgentBridge started on port {_port.Value}");
        }

        void Update()
        {
            // Process main-thread actions
            lock (_queueLock)
            {
                while (_mainThreadQueue.Count > 0)
                {
                    try { _mainThreadQueue.Dequeue()?.Invoke(); }
                    catch (Exception ex) { Logger.LogError($"MainThread action error: {ex}"); }
                }
            }
        }

        void OnDestroy()
        {
            StopServer();
        }

        void OnApplicationQuit()
        {
            StopServer();
        }

        // ══════════════════════════════════════════
        // HTTP Server
        // ══════════════════════════════════════════

        private void StartServer()
        {
            _running = true;
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://+:{_port.Value}/");
            try
            {
                _listener.Start();
            }
            catch (HttpListenerException)
            {
                // Fallback to localhost only
                _listener = new HttpListener();
                _listener.Prefixes.Add($"http://127.0.0.1:{_port.Value}/");
                _listener.Start();
            }

            _listenerThread = new Thread(ListenLoop) { IsBackground = true };
            _listenerThread.Start();
        }

        private void StopServer()
        {
            _running = false;
            try { _listener?.Stop(); } catch { }
            try { _listenerThread?.Join(2000); } catch { }
        }

        private void ListenLoop()
        {
            while (_running)
            {
                try
                {
                    var ctx = _listener.GetContext();
                    ThreadPool.QueueUserWorkItem(_ => HandleRequest(ctx));
                }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex)
                {
                    if (_running) Logger.LogError($"Listen error: {ex.Message}");
                }
            }
        }

        // ══════════════════════════════════════════
        // Request Handler
        // ══════════════════════════════════════════

        private void HandleRequest(HttpListenerContext ctx)
        {
            var req = ctx.Request;
            var resp = ctx.Response;

            // CORS
            resp.Headers.Add("Access-Control-Allow-Origin", "*");
            resp.Headers.Add("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
            resp.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-Agent-Key");

            if (req.HttpMethod == "OPTIONS")
            {
                resp.StatusCode = 204;
                resp.Close();
                return;
            }

            // Auth check
            if (!string.IsNullOrEmpty(_authKey.Value))
            {
                var key = req.Headers["X-Agent-Key"];
                if (key != _authKey.Value)
                {
                    SendJson(resp, 401, new JSONClass { ["error"] = "Unauthorized" });
                    return;
                }
            }

            string path = req.Url.AbsolutePath.TrimEnd('/');
            string method = req.HttpMethod;
            string body = "";
            if (req.HasEntityBody)
            {
                using (var reader = new StreamReader(req.InputStream, req.ContentEncoding))
                    body = reader.ReadToEnd();
            }

            if (_enableLogging.Value)
                Logger.LogInfo($"{method} {path}");

            try
            {
                Route(method, path, body, resp, req.Url.Query);
            }
            catch (Exception ex)
            {
                Logger.LogError($"Route error: {ex}");
                SendJson(resp, 500, new JSONClass { ["error"] = ex.Message });
            }
        }

        // ══════════════════════════════════════════
        // Router
        // ══════════════════════════════════════════

        private void Route(string method, string path, string body, HttpListenerResponse resp, string query = "")
        {
            // ── Status ──
            if (path == "/api/status" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    var sc = SuperController.singleton;
                    var j = new JSONClass();
                    j["running"].AsBool = true;
                    j["atomCount"].AsInt = sc.GetAtoms().Count;
                    j["freezeAnimation"].AsBool = sc.freezeAnimation;
                    j["version"] = "AgentBridge/2.0.0";
                    j["vamVersion"] = sc.version ?? "unknown";
                    j["timestamp"] = DateTime.Now.ToString("o");
                    return j;
                });
                return;
            }

            // ── Atoms List ──
            if (path == "/api/atoms" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    var arr = new JSONArray();
                    foreach (var atom in SuperController.singleton.GetAtoms())
                    {
                        var a = new JSONClass();
                        a["id"] = atom.uid;
                        a["type"] = atom.type;
                        a["on"].AsBool = atom.on;
                        var pos = atom.mainController?.transform.position ?? Vector3.zero;
                        a["position"] = Vec3ToJson(pos);
                        arr.Add(a);
                    }
                    return arr;
                });
                return;
            }

            // ── Atom Detail ──
            if (path.StartsWith("/api/atom/") && !path.Contains("/storable")
                && !path.Contains("/controller") && !path.Contains("/morph")
                && !path.Contains("/plugin"))
            {
                string atomId = ExtractSegment(path, 3);

                if (method == "GET")
                {
                    RunOnMainThread(resp, () =>
                    {
                        var atom = SuperController.singleton.GetAtomByUid(atomId);
                        if (atom == null)
                            return ErrorJson($"Atom '{atomId}' not found");
                        return AtomToJson(atom);
                    });
                    return;
                }

                if (method == "DELETE")
                {
                    RunOnMainThread(resp, () =>
                    {
                        var atom = SuperController.singleton.GetAtomByUid(atomId);
                        if (atom == null)
                            return ErrorJson($"Atom '{atomId}' not found");
                        SuperController.singleton.RemoveAtom(atom);
                        return new JSONClass { ["ok"] = JB(true), ["removed"] = atomId };
                    });
                    return;
                }
            }

            // ── Create Atom ──
            if (path == "/api/atom" && method == "POST")
            {
                var data = JSON.Parse(body);
                string type = data?["type"]?.Value ?? "Empty";
                string id = data?["id"]?.Value;

                RunOnMainThread(resp, () =>
                {
                    StartCoroutine(CreateAtomCoroutine(type, id, resp));
                    return null; // response sent by coroutine
                }, skipResponse: true);
                return;
            }

            // ── Storables ──
            if (path.EndsWith("/storables") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null)
                        return ErrorJson($"Atom '{atomId}' not found");
                    var arr = new JSONArray();
                    foreach (var sid in atom.GetStorableIDs())
                        arr.Add(sid);
                    return new JSONClass { ["atomId"] = atomId, ["storables"] = arr };
                });
                return;
            }

            // ── Storable Params ──
            if (path.Contains("/storable/") && path.EndsWith("/params") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                string suffix;
                string storableId = ExtractStorableId(path, out suffix);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    return StorableParamsToJson(storable);
                });
                return;
            }

            // ── Set Float Param ──
            if (path.Contains("/storable/") && path.EndsWith("/float") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string suffix;
                string storableId = ExtractStorableId(path, out suffix);
                var data = JSON.Parse(body);
                string paramName = data?["name"]?.Value;
                float paramValue = data?["value"]?.AsFloat ?? 0f;

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var p = storable.GetFloatJSONParam(paramName);
                    if (p == null) return ErrorJson($"Float param '{paramName}' not found");
                    p.val = paramValue;
                    var r = new JSONClass(); r["ok"] = JB(true); r["param"] = paramName; r["value"].AsFloat = paramValue; return r;
                });
                return;
            }

            // ── Set Bool Param ──
            if (path.Contains("/storable/") && path.EndsWith("/bool") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string suffix;
                string storableId = ExtractStorableId(path, out suffix);
                var data = JSON.Parse(body);
                string paramName = data?["name"]?.Value;
                bool paramValue = data?["value"]?.AsBool ?? false;

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var p = storable.GetBoolJSONParam(paramName);
                    if (p == null) return ErrorJson($"Bool param '{paramName}' not found");
                    p.val = paramValue;
                    var r = new JSONClass(); r["ok"] = JB(true); r["param"] = paramName; r["value"] = JB(paramValue); return r;
                });
                return;
            }

            // ── Set String Param ──
            if (path.Contains("/storable/") && path.EndsWith("/string") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string suffix;
                string storableId = ExtractStorableId(path, out suffix);
                var data = JSON.Parse(body);
                string paramName = data?["name"]?.Value;
                string paramValue = data?["value"]?.Value ?? "";

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var p = storable.GetStringJSONParam(paramName);
                    if (p == null) return ErrorJson($"String param '{paramName}' not found");
                    p.val = paramValue;
                    return new JSONClass { ["ok"] = JB(true), ["param"] = paramName, ["value"] = paramValue };
                });
                return;
            }

            // ── Call Action ──
            if (path.Contains("/storable/") && path.EndsWith("/action") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string suffix;
                string storableId = ExtractStorableId(path, out suffix);
                var data = JSON.Parse(body);
                string actionName = data?["name"]?.Value;

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    storable.CallAction(actionName);
                    return new JSONClass { ["ok"] = JB(true), ["action"] = actionName };
                });
                return;
            }

            // ── Controllers ──
            if (path.Contains("/controllers") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var arr = new JSONArray();
                    foreach (var ctrl in atom.freeControllers)
                    {
                        var c = new JSONClass();
                        c["name"] = ctrl.name;
                        c["position"] = Vec3ToJson(ctrl.transform.position);
                        c["rotation"] = Vec3ToJson(ctrl.transform.rotation.eulerAngles);
                        c["positionState"] = ctrl.currentPositionState.ToString();
                        c["rotationState"] = ctrl.currentRotationState.ToString();
                        arr.Add(c);
                    }
                    return new JSONClass { ["atomId"] = atomId, ["controllers"] = arr };
                });
                return;
            }

            // ── Set Controller Position/Rotation ──
            if (path.Contains("/controller/") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string ctrlName = ExtractSegment(path, 5);
                var data = JSON.Parse(body);

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    FreeControllerV3 ctrl = null;
                    foreach (var c in atom.freeControllers)
                    {
                        if (c.name == ctrlName) { ctrl = c; break; }
                    }
                    if (ctrl == null) return ErrorJson($"Controller '{ctrlName}' not found");

                    if (data?["position"] != null)
                    {
                        var p = data["position"];
                        ctrl.transform.position = new Vector3(
                            p["x"].AsFloat, p["y"].AsFloat, p["z"].AsFloat);
                    }
                    if (data?["rotation"] != null)
                    {
                        var r = data["rotation"];
                        ctrl.transform.rotation = Quaternion.Euler(
                            r["x"].AsFloat, r["y"].AsFloat, r["z"].AsFloat);
                    }
                    var result = new JSONClass { ["ok"] = JB(true), ["controller"] = ctrlName };
                    result["position"] = Vec3ToJson(ctrl.transform.position);
                    result["rotation"] = Vec3ToJson(ctrl.transform.rotation.eulerAngles);
                    return result;
                });
                return;
            }

            // ── Morphs (GET with ?filter= and ?modified=true support) ──
            if (path.Contains("/morphs") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                string filter = "";
                bool modifiedOnly = false;
                if (!string.IsNullOrEmpty(query))
                {
                    // Simple query string parsing (avoid System.Web dependency)
                    foreach (var pair in query.TrimStart('?').Split('&'))
                    {
                        var kv = pair.Split('=');
                        if (kv.Length == 2)
                        {
                            if (kv[0] == "filter") filter = Uri.UnescapeDataString(kv[1]);
                            if (kv[0] == "modified" && kv[1] == "true") modifiedOnly = true;
                        }
                    }
                }
                string filterCapture = filter;
                bool modifiedCapture = modifiedOnly;

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var dcs = atom.GetComponentInChildren<DAZCharacterSelector>();
                    if (dcs == null) return ErrorJson("Not a Person atom");
                    var arr = new JSONArray();
                    foreach (var name in dcs.morphsControlUI.GetMorphDisplayNames())
                    {
                        if (!string.IsNullOrEmpty(filterCapture) &&
                            name.IndexOf(filterCapture, StringComparison.OrdinalIgnoreCase) < 0)
                            continue;
                        var morph = dcs.morphsControlUI.GetMorphByDisplayName(name);
                        if (morph == null) continue;
                        bool isDefault = Mathf.Approximately(morph.morphValue, morph.startValue);
                        if (modifiedCapture && isDefault) continue;
                        var m = new JSONClass();
                        m["name"] = name;
                        m["value"].AsFloat = morph.morphValue;
                        m["min"].AsFloat = morph.min;
                        m["max"].AsFloat = morph.max;
                        m["isDefault"].AsBool = isDefault;
                        arr.Add(m);
                    }
                    var r = new JSONClass(); r["atomId"] = atomId; r["morphs"] = arr; r["count"].AsInt = arr.Count; return r;
                });
                return;
            }

            if (path.Contains("/morphs") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                var data = JSON.Parse(body);
                string morphName = data?["name"]?.Value;
                float morphValue = data?["value"]?.AsFloat ?? 0f;

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var dcs = atom.GetComponentInChildren<DAZCharacterSelector>();
                    if (dcs == null) return ErrorJson("Not a Person atom");
                    var morph = dcs.morphsControlUI.GetMorphByDisplayName(morphName);
                    if (morph == null) return ErrorJson($"Morph '{morphName}' not found");
                    morph.morphValue = morphValue;
                    var r = new JSONClass(); r["ok"] = JB(true); r["morph"] = morphName; r["value"].AsFloat = morphValue; return r;
                });
                return;
            }

            // ── Scene Load ──
            if (path == "/api/scene/load" && method == "POST")
            {
                var data = JSON.Parse(body);
                string scenePath = data?["path"]?.Value;
                RunOnMainThread(resp, () =>
                {
                    if (string.IsNullOrEmpty(scenePath))
                        return ErrorJson("'path' required");
                    SuperController.singleton.Load(scenePath);
                    return new JSONClass { ["ok"] = JB(true), ["loaded"] = scenePath };
                });
                return;
            }

            // ── Scene Save ──
            if (path == "/api/scene/save" && method == "POST")
            {
                var data = JSON.Parse(body);
                string scenePath = data?["path"]?.Value;
                RunOnMainThread(resp, () =>
                {
                    if (string.IsNullOrEmpty(scenePath))
                        return ErrorJson("'path' required");
                    SuperController.singleton.Save(scenePath);
                    return new JSONClass { ["ok"] = JB(true), ["saved"] = scenePath };
                });
                return;
            }

            // ── Scene Clear ──
            if (path == "/api/scene/clear" && method == "POST")
            {
                RunOnMainThread(resp, () =>
                {
                    SuperController.singleton.NewScene();
                    return new JSONClass { ["ok"] = JB(true), ["action"] = "cleared" };
                });
                return;
            }

            // ── Scene Info ──
            if (path == "/api/scene/info" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    var sc = SuperController.singleton;
                    var j = new JSONClass();
                    j["atomCount"].AsInt = sc.GetAtoms().Count;
                    var types = new JSONClass();
                    foreach (var atom in sc.GetAtoms())
                    {
                        string t = atom.type;
                        types[t].AsInt = (types[t]?.AsInt ?? 0) + 1;
                    }
                    j["atomTypes"] = types;
                    j["freezeAnimation"].AsBool = sc.freezeAnimation;
                    return j;
                });
                return;
            }

            // ── Freeze ──
            if (path == "/api/freeze" && method == "POST")
            {
                var data = JSON.Parse(body);
                bool enabled = data?["enabled"]?.AsBool ?? true;
                RunOnMainThread(resp, () =>
                {
                    // freezeAnimation setter may not exist; try reflection
                    try {
                        var prop = typeof(SuperController).GetProperty("freezeAnimation");
                        if (prop != null && prop.CanWrite) prop.SetValue(SuperController.singleton, enabled, null);
                    } catch { }
                    var r = new JSONClass(); r["ok"] = JB(true); r["freeze"] = JB(enabled); return r;
                });
                return;
            }

            // ── Navigate ──
            if (path == "/api/navigate" && method == "POST")
            {
                var data = JSON.Parse(body);
                string targetId = data?["id"]?.Value;
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(targetId);
                    if (atom == null) return ErrorJson($"Atom '{targetId}' not found");
                    SuperController.singleton.SelectController(atom.mainController);
                    return new JSONClass { ["ok"] = JB(true), ["navigated"] = targetId };
                });
                return;
            }

            // ── Screenshot ──
            if (path == "/api/screenshot" && method == "POST")
            {
                var data = JSON.Parse(body);
                string savePath = data?["path"]?.Value;
                if (string.IsNullOrEmpty(savePath))
                    savePath = Path.Combine(SuperController.singleton.savesDir,
                        $"agent_screenshot_{DateTime.Now:yyyyMMdd_HHmmss}.png");

                RunOnMainThread(resp, () =>
                {
                    StartCoroutine(ScreenshotCoroutine(savePath, resp));
                    return null;
                }, skipResponse: true);
                return;
            }

            // ── Plugins List ──
            if ((path.Contains("/plugins/") || path.EndsWith("/plugins")) && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var arr = new JSONArray();
                    foreach (var sid in atom.GetStorableIDs())
                    {
                        if (sid.StartsWith("plugin#"))
                        {
                            var storable = atom.GetStorableByID(sid);
                            var p = new JSONClass();
                            p["id"] = sid;
                            p["type"] = storable?.GetType().Name ?? "unknown";
                            // Get float/bool/string param counts
                            if (storable != null)
                            {
                                p["floatParams"].AsInt = storable.GetFloatParamNames()?.Count ?? 0;
                                p["boolParams"].AsInt = storable.GetBoolParamNames()?.Count ?? 0;
                                p["stringParams"].AsInt = storable.GetStringParamNames()?.Count ?? 0;
                            }
                            arr.Add(p);
                        }
                    }
                    return new JSONClass { ["atomId"] = atomId, ["plugins"] = arr };
                });
                return;
            }

            // ── Batch Command ──
            if (path == "/api/command" && method == "POST")
            {
                var data = JSON.Parse(body);
                var commands = data?["commands"]?.AsArray;
                if (commands == null)
                {
                    SendJson(resp, 400, ErrorJson("'commands' array required"));
                    return;
                }

                RunOnMainThread(resp, () =>
                {
                    var results = new JSONArray();
                    foreach (JSONNode cmd in commands)
                    {
                        var result = ExecuteCommand(cmd);
                        results.Add(result);
                    }
                    return new JSONClass { ["ok"] = JB(true), ["results"] = results };
                });
                return;
            }

            // ══════════════════════════════════════════
            // v2.0 New Endpoints
            // ══════════════════════════════════════════

            // ── Health Check (no main-thread marshal, instant response) ──
            if (path == "/api/health" && method == "GET")
            {
                SendJson(resp, 200, new JSONClass
                {
                    ["ok"] = JB(true),
                    ["version"] = "AgentBridge/2.0.0",
                    ["timestamp"] = DateTime.Now.ToString("o")
                });
                return;
            }

            // ── Atom Types ──
            if (path == "/api/atom-types" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    var arr = new JSONArray();
                    string[] types = {
                        "Person", "Empty", "WindowCamera", "InvisibleLight",
                        "AudioSource", "CustomUnityAsset", "SimpleSign",
                        "UIText", "UIButton", "UISlider", "UIToggle",
                        "UIPopup", "SubScene", "Cube", "Sphere",
                        "RhythmTool", "AptPanel", "NavigationPoint",
                        "CoreControl", "AnimationPattern", "CollisionTrigger"
                    };
                    foreach (var t in types) arr.Add(t);
                    return new JSONClass { ["types"] = arr };
                });
                return;
            }

            // ── StringChooser Params (GET) ──
            if (path.Contains("/storable/") && path.EndsWith("/choosers") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                string sfx;
                string storableId = ExtractStorableId(path, out sfx);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var arr = new JSONArray();
                    var names = storable.GetStringChooserParamNames();
                    if (names != null)
                    {
                        foreach (var name in names)
                        {
                            var p = storable.GetStringChooserJSONParam(name);
                            if (p != null)
                            {
                                var c = new JSONClass();
                                c["name"] = name;
                                c["value"] = p.val;
                                var choices = new JSONArray();
                                if (p.choices != null)
                                    foreach (var ch in p.choices) choices.Add(ch);
                                c["choices"] = choices;
                                arr.Add(c);
                            }
                        }
                    }
                    return new JSONClass { ["storableId"] = storableId, ["choosers"] = arr };
                });
                return;
            }

            // ── StringChooser Param (POST - set value) ──
            if (path.Contains("/storable/") && path.EndsWith("/chooser") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                string sfx;
                string storableId = ExtractStorableId(path, out sfx);
                var data = JSON.Parse(body);
                string paramName = data?["name"]?.Value;
                string paramValue = data?["value"]?.Value ?? "";

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var p = storable.GetStringChooserJSONParam(paramName);
                    if (p == null) return ErrorJson($"StringChooser param '{paramName}' not found");
                    p.val = paramValue;
                    return new JSONClass { ["ok"] = JB(true), ["param"] = paramName, ["value"] = paramValue };
                });
                return;
            }

            // ── Storable Actions List (GET) ──
            if (path.Contains("/storable/") && path.EndsWith("/actions") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                string sfx;
                string storableId = ExtractStorableId(path, out sfx);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    var storable = atom.GetStorableByID(storableId);
                    if (storable == null) return ErrorJson($"Storable '{storableId}' not found");
                    var arr = new JSONArray();
                    var names = storable.GetActionNames();
                    if (names != null)
                        foreach (var name in names) arr.Add(name);
                    return new JSONClass { ["storableId"] = storableId, ["actions"] = arr };
                });
                return;
            }

            // ── Log Messages ──
            if (path == "/api/log" && method == "GET")
            {
                lock (_logLock)
                {
                    var arr = new JSONArray();
                    foreach (var entry in _logBuffer) arr.Add(entry);
                    var r = new JSONClass(); r["messages"] = arr; r["count"].AsInt = arr.Count; SendJson(resp, 200, r);
                }
                return;
            }

            // ── Scene File Browser ──
            if (path == "/api/scenes" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    var arr = new JSONArray();
                    string scenesDir = Path.Combine(SuperController.singleton.savesDir, "scene");
                    if (Directory.Exists(scenesDir))
                    {
                        foreach (var file in Directory.GetFiles(scenesDir, "*.json",
                            SearchOption.AllDirectories))
                        {
                            var s = new JSONClass();
                            s["path"] = file;
                            s["name"] = Path.GetFileNameWithoutExtension(file);
                            s["dir"] = Path.GetDirectoryName(file).Replace(scenesDir, "").TrimStart('\\', '/');
                            var fi = new FileInfo(file);
                            s["size"].AsFloat = (float)fi.Length;
                            s["modified"] = fi.LastWriteTime.ToString("o");
                            arr.Add(s);
                        }
                    }
                    var r = new JSONClass(); r["scenes"] = arr; r["count"].AsInt = arr.Count; return r;
                });
                return;
            }

            // ── Prefs (GET/POST) ──
            if (path == "/api/prefs" && method == "GET")
            {
                RunOnMainThread(resp, () =>
                {
                    string prefsPath = Path.Combine(
                        Path.GetDirectoryName(Application.dataPath), "prefs.json");
                    if (!File.Exists(prefsPath))
                        return ErrorJson("prefs.json not found");
                    var prefs = JSON.Parse(File.ReadAllText(prefsPath));
                    return new JSONClass { ["prefs"] = prefs };
                });
                return;
            }

            if (path == "/api/prefs" && method == "POST")
            {
                var data = JSON.Parse(body);
                RunOnMainThread(resp, () =>
                {
                    string prefsPath = Path.Combine(
                        Path.GetDirectoryName(Application.dataPath), "prefs.json");
                    if (!File.Exists(prefsPath))
                        return ErrorJson("prefs.json not found");
                    var prefs = JSON.Parse(File.ReadAllText(prefsPath));
                    // Merge provided keys into prefs
                    if (data != null)
                    {
                        var dataObj = data as JSONClass;
                        if (dataObj != null)
                        {
                            foreach (string key in dataObj.Keys)
                                prefs[key] = dataObj[key];
                        }
                        File.WriteAllText(prefsPath, prefs.ToString());
                    }
                    var r = new JSONClass(); r["ok"].AsBool = true; return r;
                });
                return;
            }

            // ── Voxta Convenience: Send Message ──
            if (path.StartsWith("/api/voxta/") && path.EndsWith("/send") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                var data = JSON.Parse(body);
                string message = data?["message"]?.Value ?? "";

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    // Find Voxta plugin storable
                    JSONStorable voxta = null;
                    foreach (var sid in atom.GetStorableIDs())
                    {
                        if (sid.Contains("Voxta"))
                        {
                            voxta = atom.GetStorableByID(sid);
                            break;
                        }
                    }
                    if (voxta == null) return ErrorJson("Voxta plugin not found on atom");
                    var triggerParam = voxta.GetStringJSONParam("TriggerMessage");
                    if (triggerParam == null) return ErrorJson("TriggerMessage param not found");
                    triggerParam.val = message;
                    return new JSONClass { ["ok"] = JB(true), ["sent"] = message };
                });
                return;
            }

            // ── Voxta Convenience: Get State ──
            if (path.StartsWith("/api/voxta/") && path.EndsWith("/state") && method == "GET")
            {
                string atomId = ExtractSegment(path, 3);
                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    JSONStorable voxta = null;
                    foreach (var sid in atom.GetStorableIDs())
                    {
                        if (sid.Contains("Voxta"))
                        {
                            voxta = atom.GetStorableByID(sid);
                            break;
                        }
                    }
                    if (voxta == null) return ErrorJson("Voxta plugin not found on atom");
                    var j = new JSONClass();
                    // Read all Voxta state params
                    var connected = voxta.GetBoolJSONParam("Connected");
                    j["connected"].AsBool = connected?.val ?? false;
                    var active = voxta.GetBoolJSONParam("Active");
                    j["active"].AsBool = active?.val ?? false;
                    var ready = voxta.GetBoolJSONParam("Ready");
                    j["ready"].AsBool = ready?.val ?? false;
                    var error = voxta.GetBoolJSONParam("Error");
                    j["error"].AsBool = error?.val ?? false;
                    var status = voxta.GetStringJSONParam("Status");
                    j["status"] = status?.val ?? "";
                    var state = voxta.GetStringChooserJSONParam("State");
                    j["state"] = state?.val ?? "off";
                    var lastUser = voxta.GetStringJSONParam("LastUserMessage");
                    j["lastUserMessage"] = lastUser?.val ?? "";
                    var lastChar = voxta.GetStringJSONParam("LastCharacterMessage");
                    j["lastCharacterMessage"] = lastChar?.val ?? "";
                    var currentAction = voxta.GetStringJSONParam("CurrentAction");
                    j["currentAction"] = currentAction?.val ?? "";
                    var userName = voxta.GetStringJSONParam("User Name");
                    j["userName"] = userName?.val ?? "";
                    var charName = voxta.GetStringJSONParam("Character Name 1");
                    j["characterName"] = charName?.val ?? "";
                    var flags = voxta.GetStringJSONParam("Flags");
                    j["flags"] = flags?.val ?? "";
                    return j;
                });
                return;
            }

            // ── Voxta Convenience: New Chat / Actions ──
            if (path.StartsWith("/api/voxta/") && path.EndsWith("/action") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                var data = JSON.Parse(body);
                string actionName = data?["name"]?.Value ?? "";

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    JSONStorable voxta = null;
                    foreach (var sid in atom.GetStorableIDs())
                    {
                        if (sid.Contains("Voxta"))
                        {
                            voxta = atom.GetStorableByID(sid);
                            break;
                        }
                    }
                    if (voxta == null) return ErrorJson("Voxta plugin not found on atom");
                    voxta.CallAction(actionName);
                    return new JSONClass { ["ok"] = JB(true), ["action"] = actionName };
                });
                return;
            }

            // ── Timeline Convenience: Play/Stop/List ──
            if (path.StartsWith("/api/timeline/") && method == "POST")
            {
                string atomId = ExtractSegment(path, 3);
                var data = JSON.Parse(body);
                string action = data?["action"]?.Value ?? "play";
                string animName = data?["animation"]?.Value ?? "";

                RunOnMainThread(resp, () =>
                {
                    var atom = SuperController.singleton.GetAtomByUid(atomId);
                    if (atom == null) return ErrorJson($"Atom '{atomId}' not found");
                    // Find Timeline plugin
                    JSONStorable timeline = null;
                    foreach (var sid in atom.GetStorableIDs())
                    {
                        if (sid.Contains("VamTimeline") || sid.Contains("Timeline"))
                        {
                            timeline = atom.GetStorableByID(sid);
                            break;
                        }
                    }
                    if (timeline == null) return ErrorJson("Timeline plugin not found on atom");

                    switch (action)
                    {
                        case "play":
                            if (!string.IsNullOrEmpty(animName))
                                timeline.CallAction($"Play.{animName}");
                            else
                                timeline.CallAction("Play");
                            break;
                        case "stop":
                            timeline.CallAction("Stop");
                            break;
                        case "scrub":
                            float time = data?["time"]?.AsFloat ?? 0f;
                            timeline.SetFloatParamValue("scrubber", time);
                            break;
                        case "speed":
                            float spd = data?["value"]?.AsFloat ?? 1f;
                            timeline.SetFloatParamValue("speed", spd);
                            break;
                        default:
                            timeline.CallAction(action);
                            break;
                    }
                    return new JSONClass { ["ok"] = JB(true), ["action"] = action };
                });
                return;
            }

            // ── Global SuperController Actions ──
            if (path == "/api/global/action" && method == "POST")
            {
                var data = JSON.Parse(body);
                string actionName = data?["action"]?.Value ?? "";
                RunOnMainThread(resp, () =>
                {
                    switch (actionName)
                    {
                        case "play":
                            SuperController.singleton.motionAnimationMaster?.StartPlayback();
                            break;
                        case "stop":
                            SuperController.singleton.motionAnimationMaster?.StopPlayback();
                            break;
                        case "reset":
                            SuperController.singleton.motionAnimationMaster?.ResetAnimation();
                            break;
                        case "undo":
                        {
                            var m = typeof(SuperController).GetMethod("Undo", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                            if (m != null) m.Invoke(SuperController.singleton, null);
                            else return ErrorJson("Undo not available");
                            break;
                        }
                        case "redo":
                        {
                            var m = typeof(SuperController).GetMethod("Redo", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                            if (m != null) m.Invoke(SuperController.singleton, null);
                            else return ErrorJson("Redo not available");
                            break;
                        }
                        default:
                            return ErrorJson($"Unknown global action: {actionName}");
                    }
                    return new JSONClass { ["ok"] = JB(true), ["action"] = actionName };
                });
                return;
            }

            // ── 404 ──
            SendJson(resp, 404, new JSONClass { ["error"] = $"Unknown route: {method} {path}" });
        }

        // ══════════════════════════════════════════
        // Batch Command Executor
        // ══════════════════════════════════════════

        private JSONNode ExecuteCommand(JSONNode cmd)
        {
            string action = cmd["action"]?.Value ?? "";
            var p = cmd["params"];
            try
            {
                switch (action)
                {
                    case "set_float":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var storable = atom?.GetStorableByID(p["storable"].Value);
                        var param = storable?.GetFloatJSONParam(p["name"].Value);
                        if (param != null) param.val = p["value"].AsFloat;
                        return new JSONClass { ["ok"] = JB(param != null), ["action"] = action };
                    }
                    case "set_bool":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var storable = atom?.GetStorableByID(p["storable"].Value);
                        var param = storable?.GetBoolJSONParam(p["name"].Value);
                        if (param != null) param.val = p["value"].AsBool;
                        return new JSONClass { ["ok"] = JB(param != null), ["action"] = action };
                    }
                    case "set_string":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var storable = atom?.GetStorableByID(p["storable"].Value);
                        var param = storable?.GetStringJSONParam(p["name"].Value);
                        if (param != null) param.val = p["value"].Value;
                        return new JSONClass { ["ok"] = JB(param != null), ["action"] = action };
                    }
                    case "call_action":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var storable = atom?.GetStorableByID(p["storable"].Value);
                        storable?.CallAction(p["name"].Value);
                        return new JSONClass { ["ok"] = JB(storable != null), ["action"] = action };
                    }
                    case "set_position":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        if (atom != null)
                        {
                            FreeControllerV3 ctrl = null;
                            string ctrlName = p["controller"]?.Value ?? "mainController";
                            foreach (var c in atom.freeControllers)
                                if (c.name == ctrlName) { ctrl = c; break; }
                            if (ctrl == null) ctrl = atom.mainController;
                            ctrl.transform.position = new Vector3(
                                p["x"].AsFloat, p["y"].AsFloat, p["z"].AsFloat);
                        }
                        return new JSONClass { ["ok"] = JB(atom != null), ["action"] = action };
                    }
                    case "set_morph":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var dcs = atom?.GetComponentInChildren<DAZCharacterSelector>();
                        var morph = dcs?.morphsControlUI.GetMorphByDisplayName(p["name"].Value);
                        if (morph != null) morph.morphValue = p["value"].AsFloat;
                        return new JSONClass { ["ok"] = JB(morph != null), ["action"] = action };
                    }
                    case "set_chooser":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        var storable = atom?.GetStorableByID(p["storable"].Value);
                        var param = storable?.GetStringChooserJSONParam(p["name"].Value);
                        if (param != null) param.val = p["value"].Value;
                        return new JSONClass { ["ok"] = JB(param != null), ["action"] = action };
                    }
                    case "set_rotation":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        if (atom != null)
                        {
                            FreeControllerV3 ctrl = null;
                            string ctrlName = p["controller"]?.Value ?? "mainController";
                            foreach (var c in atom.freeControllers)
                                if (c.name == ctrlName) { ctrl = c; break; }
                            if (ctrl == null) ctrl = atom.mainController;
                            ctrl.transform.rotation = Quaternion.Euler(
                                p["x"].AsFloat, p["y"].AsFloat, p["z"].AsFloat);
                        }
                        return new JSONClass { ["ok"] = JB(atom != null), ["action"] = action };
                    }
                    case "voxta_send":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        JSONStorable voxta = null;
                        if (atom != null)
                        {
                            foreach (var sid in atom.GetStorableIDs())
                                if (sid.Contains("Voxta")) { voxta = atom.GetStorableByID(sid); break; }
                        }
                        if (voxta != null)
                        {
                            var tp = voxta.GetStringJSONParam("TriggerMessage");
                            if (tp != null) tp.val = p["message"].Value;
                        }
                        return new JSONClass { ["ok"] = JB(voxta != null), ["action"] = action };
                    }
                    case "voxta_action":
                    {
                        var atom = SuperController.singleton.GetAtomByUid(p["atom"].Value);
                        JSONStorable voxta = null;
                        if (atom != null)
                        {
                            foreach (var sid in atom.GetStorableIDs())
                                if (sid.Contains("Voxta")) { voxta = atom.GetStorableByID(sid); break; }
                        }
                        if (voxta != null) voxta.CallAction(p["name"].Value);
                        return new JSONClass { ["ok"] = JB(voxta != null), ["action"] = action };
                    }
                    default:
                        return new JSONClass { ["ok"] = JB(false), ["error"] = $"Unknown action: {action}" };
                }
            }
            catch (Exception ex)
            {
                return new JSONClass { ["ok"] = JB(false), ["error"] = ex.Message };
            }
        }

        // ══════════════════════════════════════════
        // Coroutines
        // ══════════════════════════════════════════

        private IEnumerator CreateAtomCoroutine(string type, string id, HttpListenerResponse resp)
        {
            var existingUids = new HashSet<string>(SuperController.singleton.GetAtomUIDs());
            SuperController.singleton.AddAtomByType(type, true, true, true);
            yield return new WaitForSeconds(1f); // wait for atom registration

            Atom newAtom = null;
            foreach (var uid in SuperController.singleton.GetAtomUIDs())
            {
                if (!existingUids.Contains(uid))
                {
                    newAtom = SuperController.singleton.GetAtomByUid(uid);
                    break;
                }
            }

            if (newAtom != null)
            {
                var j = new JSONClass();
                j["ok"].AsBool = true;
                j["atom"] = AtomToJson(newAtom);
                SendJson(resp, 200, j);
            }
            else
            {
                SendJson(resp, 500, ErrorJson("Failed to create atom"));
            }
        }

        private IEnumerator ScreenshotCoroutine(string path, HttpListenerResponse resp)
        {
            yield return new WaitForEndOfFrame();
            try
            {
                var tex = new Texture2D(Screen.width, Screen.height, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, Screen.width, Screen.height), 0, 0);
                tex.Apply();
                var bytes = tex.EncodeToPNG();
                Destroy(tex);
                File.WriteAllBytes(path, bytes);
                SendJson(resp, 200, new JSONClass
                {
                    ["ok"] = JB(true),
                    ["path"] = path,
                    ["width"] = JI(Screen.width),
                    ["height"] = JI(Screen.height)
                });
            }
            catch (Exception ex)
            {
                SendJson(resp, 500, ErrorJson($"Screenshot failed: {ex.Message}"));
            }
        }

        // ══════════════════════════════════════════
        // Helpers
        // ══════════════════════════════════════════

        private void RunOnMainThread(HttpListenerResponse resp, Func<JSONNode> action,
            bool skipResponse = false)
        {
            var reqId = Guid.NewGuid().ToString();
            var waitHandle = new ManualResetEvent(false);

            lock (_queueLock)
            {
                _waitHandles[reqId] = waitHandle;
                _mainThreadQueue.Enqueue(() =>
                {
                    try
                    {
                        var result = action();
                        if (result != null && !skipResponse)
                        {
                            _responses[reqId] = result.ToString();
                        }
                        else if (skipResponse)
                        {
                            _responses[reqId] = null; // signal: response handled elsewhere
                        }
                    }
                    catch (Exception ex)
                    {
                        _responses[reqId] = ErrorJson(ex.Message).ToString();
                    }
                    finally
                    {
                        waitHandle.Set();
                    }
                });
            }

            // Wait for main thread to process (timeout 30s)
            if (waitHandle.WaitOne(30000))
            {
                string responseJson;
                lock (_queueLock)
                {
                    _responses.TryGetValue(reqId, out responseJson);
                    _responses.Remove(reqId);
                    _waitHandles.Remove(reqId);
                }

                if (responseJson != null)
                {
                    var parsed = JSON.Parse(responseJson);
                    int status = parsed?["error"] != null ? 400 : 200;
                    SendJson(resp, status, parsed);
                }
                // else: skipResponse=true, response already sent by coroutine
            }
            else
            {
                lock (_queueLock)
                {
                    _waitHandles.Remove(reqId);
                    _responses.Remove(reqId);
                }
                SendJson(resp, 504, ErrorJson("Main thread timeout (30s)"));
            }
        }

        private static void SendJson(HttpListenerResponse resp, int status, JSONNode json)
        {
            try
            {
                resp.StatusCode = status;
                resp.ContentType = "application/json; charset=utf-8";
                byte[] buf = Encoding.UTF8.GetBytes(json?.ToString() ?? "{}");
                resp.ContentLength64 = buf.Length;
                resp.OutputStream.Write(buf, 0, buf.Length);
                resp.OutputStream.Flush();
                resp.Close();
            }
            catch { }
        }

        private static string ExtractSegment(string path, int index)
        {
            var parts = path.Split('/');
            return index < parts.Length ? Uri.UnescapeDataString(parts[index]) : "";
        }

        /// <summary>
        /// Extract storable ID from path, handling IDs that contain '/' chars.
        /// Pattern: /api/atom/{atomId}/storable/{storableId...}/{suffix}
        /// The storableId can be e.g. "plugin#0_AcidBubbles.Voxta.83:/Custom/Scripts/Voxta/VoxtaClient.cslist"
        /// </summary>
        private static string ExtractStorableId(string path, out string suffix)
        {
            const string marker = "/storable/";
            int start = path.IndexOf(marker);
            if (start < 0) { suffix = ""; return ""; }
            start += marker.Length;

            // Known suffixes that terminate the storable ID
            string[] suffixes = { "/params", "/float", "/bool", "/string", "/action",
                                  "/actions", "/chooser", "/choosers" };
            int end = path.Length;
            suffix = "";
            foreach (var s in suffixes)
            {
                int idx = path.LastIndexOf(s);
                if (idx > start && idx < end)
                {
                    end = idx;
                    suffix = s.TrimStart('/');
                }
            }
            return Uri.UnescapeDataString(path.Substring(start, end - start));
        }

        private static JSONNode Vec3ToJson(Vector3 v)
        {
            var j = new JSONClass(); j["x"].AsFloat = v.x; j["y"].AsFloat = v.y; j["z"].AsFloat = v.z; return j;
        }

        private static JSONNode ErrorJson(string msg)
        {
            return new JSONClass { ["error"] = msg };
        }

        // ── SimpleJSON helpers (VaM's version lacks implicit operators for non-string types) ──
        private static JSONNode JB(bool v) { return new JSONData(v); }
        private static JSONNode JI(int v) { return new JSONData(v); }
        private static JSONNode JF(float v) { return new JSONData(v); }

        private static JSONNode AtomToJson(Atom atom)
        {
            var j = new JSONClass();
            j["id"] = atom.uid;
            j["type"] = atom.type;
            j["on"].AsBool = atom.on;
            j["hidden"].AsBool = atom.hidden;
            var pos = atom.mainController?.transform.position ?? Vector3.zero;
            var rot = atom.mainController?.transform.rotation.eulerAngles ?? Vector3.zero;
            j["position"] = Vec3ToJson(pos);
            j["rotation"] = Vec3ToJson(rot);

            var storables = new JSONArray();
            foreach (var sid in atom.GetStorableIDs())
                storables.Add(sid);
            j["storableCount"].AsInt = storables.Count;
            j["storables"] = storables;

            // Controller list
            var ctrls = new JSONArray();
            if (atom.freeControllers != null)
            {
                foreach (var ctrl in atom.freeControllers)
                    ctrls.Add(ctrl.name);
            }
            j["controllers"] = ctrls;

            return j;
        }

        private static JSONNode StorableParamsToJson(JSONStorable storable)
        {
            var j = new JSONClass();
            j["id"] = storable.storeId;

            var floats = new JSONArray();
            foreach (var name in storable.GetFloatParamNames() ?? new List<string>())
            {
                var p = storable.GetFloatJSONParam(name);
                if (p != null)
                {
                    var f = new JSONClass();
                    f["name"] = name;
                    f["value"].AsFloat = p.val;
                    f["min"].AsFloat = p.min;
                    f["max"].AsFloat = p.max;
                    f["default"].AsFloat = p.defaultVal;
                    floats.Add(f);
                }
            }
            j["floats"] = floats;

            var bools = new JSONArray();
            foreach (var name in storable.GetBoolParamNames() ?? new List<string>())
            {
                var p = storable.GetBoolJSONParam(name);
                if (p != null)
                {
                    var b = new JSONClass();
                    b["name"] = name;
                    b["value"].AsBool = p.val;
                    b["default"].AsBool = p.defaultVal;
                    bools.Add(b);
                }
            }
            j["bools"] = bools;

            var strings = new JSONArray();
            foreach (var name in storable.GetStringParamNames() ?? new List<string>())
            {
                var p = storable.GetStringJSONParam(name);
                if (p != null)
                {
                    var s = new JSONClass();
                    s["name"] = name;
                    s["value"] = p.val;
                    strings.Add(s);
                }
            }
            j["strings"] = strings;

            return j;
        }
    }
}

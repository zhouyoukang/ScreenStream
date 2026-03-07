// ==================== Auth Token Handling ====================
var _vAuthToken = localStorage.getItem('ss_auth_token') || '';
(function() {
    var p = new URLSearchParams(window.location.search);
    var t = p.get('auth') || p.get('token');
    if (t) { _vAuthToken = t; localStorage.setItem('ss_auth_token', t); }
})();
var _vOrigFetch = window.fetch;
window.fetch = function(url, opts) {
    if (_vAuthToken && typeof url === 'string') {
        opts = opts || {};
        opts.headers = opts.headers || {};
        if (typeof opts.headers === 'object' && !(opts.headers instanceof Headers)) {
            if (!opts.headers['Authorization']) opts.headers['Authorization'] = 'Bearer ' + _vAuthToken;
        }
    }
    return _vOrigFetch.call(window, url, opts).then(function(resp) {
        if (resp.status === 401) {
            localStorage.removeItem('ss_auth_token'); _vAuthToken = '';
            toast('Session expired - redirecting...');
            setTimeout(function() { window.location.href = '/' + (_vAuthToken ? '?auth=' + _vAuthToken : ''); }, 1500);
        }
        return resp;
    });
};
// ==================== End Auth ====================
var A = "", rc = 0;
function rd() {
    rc++;
    var d = document.getElementById("dash");
    fetch(A + "/status").then(function (r) { return r.json() }).then(function (s) {
        document.getElementById("dLive").className = "live";
        document.getElementById("dSt").textContent = "LIVE";
        d.classList.remove("rp"); void d.offsetWidth; d.classList.add("rp");
        fetch(A + "/deviceinfo").then(function (r) { return r.json() }).then(function (i) {
            var bl = i.batteryLevel, bh = "";
            if (bl != null) {
                var c = bl < 20 ? "err" : bl < 50 ? "warn" : "ok"; var cg = i.isCharging ? " chg" : "";
                bh = '<span class="bb"><span class="bf ' + c + cg + '" style="width:' + bl + '%"></span></span>';
                bh += '<span class="v ' + c + '">' + bl + '%</span>';
                if (i.isCharging) bh += '<span class="ca"> \u26A1</span>';
            }
            document.getElementById("dBat").innerHTML = bh;
            var nh = ""; if (i.networkType) { nh = i.networkType + (i.networkConnected ? " \u2705" : " \u274C"); }
            document.getElementById("dNet").innerHTML = nh;
        }).catch(function () { });
        fetch(A + "/foreground").then(function (r) { return r.json() }).then(function (f) {
            var p = f.packageName || f.package || ""; document.getElementById("dApp").textContent = "\uD83D\uDCF1 " + p.replace("com.", "").replace("android.", "");
        }).catch(function () { });
        fetch(A + "/notifications/read?limit=1").then(function (r) { return r.json() }).then(function (n) {
            var t = n.total || 0; var el = document.getElementById("dNot");
            if (t > 0) el.innerHTML = '<span class="nb">\uD83D\uDD14' + t + '</span>'; else el.textContent = "";
        }).catch(function () { });
    }).catch(function () {
        document.getElementById("dLive").className = "live off";
        document.getElementById("dSt").textContent = "OFF";
        document.getElementById("dBat").textContent = "--";
        document.getElementById("dNet").textContent = "--";
        document.getElementById("dApp").textContent = "\u274C disconnected";
        document.getElementById("dNot").textContent = "";
    });
    var now = new Date(); var hms = z(now.getHours()) + ":" + z(now.getMinutes()) + ":" + z(now.getSeconds());
    document.getElementById("dClk").textContent = hms;
    document.getElementById("dTs").textContent = "#" + rc + " " + hms;
}
function z(n) { return n < 10 ? "0" + n : "" + n }
function sa(m) { document.getElementById("dAct").textContent = "\u2713 " + m }
function rm() {
    fetch(A + "/macro/list").then(function (r) { return r.json() }).then(function (l) {
        var g = document.getElementById("mG"), c = document.getElementById("mCnt");
        if (!l || !l.length) { g.innerHTML = '<div style="color:var(--txt2);font-size:11px;grid-column:1/-1">no macros</div>'; c.textContent = ""; return }
        c.textContent = "(" + l.length + ")"; var h = "";
        for (var i = 0; i < l.length; i++) {
            var m = l[i]; var cls = m.running ? " run" : "";
            h += '<div class="mt' + cls + '" onclick="xm(\'' + m.id + "','" + esc(m.name).replace(/'/g, "\\'") + "')\">";
            h += '<div class="mn">' + esc(m.name) + "</div>";
            h += '<div class="ms">' + m.stepsCount + " steps</div></div>";
        }
        g.innerHTML = h;
    }).catch(function () { });
}
function xm(id, nm) { sa("\u25B6 " + nm); toast("\u25B6 " + nm); fetch(A + "/macro/run/" + id, { method: "POST" }).then(function () { setTimeout(rm, 2000) }).catch(function () { toast("macro failed") }) }
function sp(t, h) { document.getElementById("pT").textContent = t; document.getElementById("pB").innerHTML = h; document.getElementById("ov").classList.add("show") }
function cp() { document.getElementById("ov").classList.remove("show") }
function toast(m) { var t = document.getElementById("tst"); t.textContent = m; t.classList.add("show"); setTimeout(function () { t.classList.remove("show") }, 2200) }
function esc(s) { if (!s) return ""; var d = document.createElement("div"); d.textContent = String(s); return d.innerHTML }
function rw(l, v, c) { return '<div class="rr"><span class="rl">' + esc(l) + '</span><span class="rv' + (c ? " " + c : "") + '">' + esc(v) + "</span></div>" }
function doInfo() {
    sp("\uD83D\uDCCA \u8BBE\u5907\u8BE6\u60C5", '<span class="ld"></span>');
    fetch(A + "/deviceinfo").then(function (r) { return r.json() }).then(function (d) {
        var h = ""; h += rw("\u578B\u53F7", d.model || "-"); h += rw("Android", d.androidVersion || "-");
        var bc = d.batteryLevel < 20 ? "err" : d.batteryLevel < 50 ? "warn" : "ok";
        h += rw("\u7535\u6C60", d.batteryLevel + "%" + (d.isCharging ? " \u26A1\u5145\u7535\u4E2D" : ""), bc);
        if (d.networkType) h += rw("\u7F51\u7EDC", d.networkType + (d.networkConnected ? " \u2705" : " \u274C"));
        if (d.wifiSSID) h += rw("WiFi", d.wifiSSID);
        if (d.storageTotalMB) h += rw("\u5B58\u50A8", Math.round(d.storageAvailableMB / 1024) + "G / " + Math.round(d.storageTotalMB / 1024) + "G");
        if (d.uptimeFormatted) h += rw("\u8FD0\u884C\u65F6\u95F4", d.uptimeFormatted);
        if (d.screenWidth) h += rw("\u5C4F\u5E55", d.screenWidth + "x" + d.screenHeight);
        if (d.volumeMusic != null) h += rw("\u97F3\u91CF", d.volumeMusic + " / " + d.volumeMusicMax);
        h += rw("\u4EAE\u5EA6", d.brightness || "-");
        sp("\uD83D\uDCCA \u8BBE\u5907\u8BE6\u60C5", h); sa("\u67E5\u770B\u8BBE\u5907\u4FE1\u606F");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doBat() {
    sp("\uD83D\uDD0B \u7535\u6C60", '<span class="ld"></span>');
    fetch(A + "/deviceinfo").then(function (r) { return r.json() }).then(function (d) {
        var c = d.batteryLevel < 20 ? "err" : d.batteryLevel < 50 ? "warn" : "ok";
        var h = '<div style="text-align:center;padding:16px 0"><div style="font-size:44px;font-weight:700" class="rv ' + c + '">' + d.batteryLevel + '%</div>';
        h += '<div style="margin-top:6px;color:var(--txt2)">' + (d.isCharging ? "\u26A1 \u5145\u7535\u4E2D" : "\uD83D\uDD0C \u672A\u5145\u7535") + "</div>";
        h += "</div>"; sp("\uD83D\uDD0B \u7535\u6C60", h); sa("\u67E5\u770B\u7535\u6C60");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doNotif() {
    sp("\uD83D\uDD14 \u901A\u77E5", '<span class="ld"></span>');
    fetch(A + "/notifications/read?limit=15").then(function (r) { return r.json() }).then(function (d) {
        var ns = d.notifications || [];
        if (!ns.length) { sp("\uD83D\uDD14 \u901A\u77E5", '<div style="color:var(--txt2);text-align:center;padding:16px">\u6682\u65E0\u901A\u77E5</div>'); sa("\u901A\u77E5: 0"); return }
        var h = '<div style="color:var(--txt2);font-size:11px;margin-bottom:6px">\u5171 ' + (d.total || ns.length) + " \u6761</div>";
        for (var i = 0; i < ns.length; i++) {
            var n = ns[i]; h += '<div class="ni">';
            h += '<div class="np">' + esc((n.package || "").replace("com.", "")) + "</div>";
            if (n.title) h += '<div class="nt">' + esc(n.title) + "</div>";
            if (n.text || n.body) h += '<div class="nb2">' + esc(n.text || n.body) + "</div>"; h += "</div>";
        }
        sp("\uD83D\uDD14 \u901A\u77E5 (" + ns.length + ")", h); sa("\u901A\u77E5: " + ns.length + "\u6761");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doScreen() {
    sp("\uD83D\uDC41 \u5C4F\u5E55", '<span class="ld"></span>');
    fetch(A + "/screen/text").then(function (r) { return r.json() }).then(function (d) {
        var h = ""; if (d.packageName) h += '<div style="font-size:10px;color:var(--accent);margin-bottom:4px">\uD83D\uDCE6 ' + esc(d.packageName) + "</div>";
        var cs = d.clickables || [];
        if (cs.length) {
            h += '<div class="rc"><div class="rct">\u53EF\u70B9\u51FB (' + cs.length + ")</div>";
            for (var i = 0; i < Math.min(cs.length, 20); i++) {
                var c = cs[i]; var lb = c.text || c.label || c.desc || "(unnamed)";
                h += '<div class="si ck" onclick="fcd(\'' + esc(lb).replace(/'/g, "\\'") + "')\">" + esc(lb) + "</div>";
            } h += "</div>";
        }
        var ts = d.texts || [];
        if (ts.length) {
            h += '<div class="rc"><div class="rct">\u6587\u672C (' + ts.length + ")</div>";
            for (var j = 0; j < Math.min(ts.length, 25); j++) {
                var t = ts[j]; var tx = t.text || t;
                if (typeof tx === "string" && tx.trim()) h += '<div class="si">' + esc(tx) + "</div>";
            } h += "</div>";
        }
        sp("\uD83D\uDC41 \u5C4F\u5E55\u5185\u5BB9", h); sa("\u8BFB\u5C4F\u5E55: " + ts.length + "\u6587\u672C, " + cs.length + "\u53EF\u70B9\u51FB");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doFg() {
    fetch(A + "/foreground").then(function (r) { return r.json() }).then(function (d) {
        var p = d.packageName || d.package || "-";
        sp("\uD83D\uDCF1 \u524D\u53F0APP", '<div style="text-align:center;padding:16px"><div style="font-size:15px;font-weight:600">' + esc(p) + "</div>" + (d.activity ? '<div style="font-size:11px;color:var(--txt2);margin-top:3px">' + esc(d.activity) + "</div>" : "") + "</div>");
        sa("\u524D\u53F0: " + p.replace("com.", ""));
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doApps() {
    sp("\uD83D\uDCCB \u5E94\u7528", '<span class="ld"></span>');
    fetch(A + "/apps").then(function (r) { return r.json() }).then(function (d) {
        var apps = d.apps || d; if (!Array.isArray(apps)) { sp("\u274C", "format error"); return }
        apps.sort(function (a, b) { return (a.label || "").localeCompare(b.label || "") });
        var h = '<div style="color:var(--txt2);font-size:11px;margin-bottom:6px">' + apps.length + ' \u5E94\u7528 (\u70B9\u51FB\u6253\u5F00)</div><div class="ag">';
        for (var i = 0; i < apps.length; i++) {
            var a = apps[i]; var p = a.packageName || a.package;
            h += '<div class="ai" onclick="opkg(\'' + esc(p) + '\')">' + esc(a.label || a.name || p) + "</div>";
        }
        h += "</div>"; sp("\uD83D\uDCCB \u5E94\u7528 (" + apps.length + ")", h); sa("\u5E94\u7528\u5217\u8868: " + apps.length);
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doClip() {
    fetch(A + "/clipboard").then(function (r) { return r.json() }).then(function (d) {
        var tx = d.text || d.clipboard || JSON.stringify(d);
        sp("\uD83D\uDCCE \u526A\u8D34\u677F", '<div style="padding:10px;background:var(--card);border-radius:8px;word-break:break-all;font-size:13px">' + esc(tx) + "</div>"); sa("\u526A\u8D34\u677F\u5DF2\u8BFB\u53D6");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function nav(a) {
    var nm = { home: "\uD83C\uDFE0 \u684C\u9762", back: "\u21A9\uFE0F \u8FD4\u56DE", recents: "\uD83D\uDCD1 \u6700\u8FD1", notifications: "\uD83D\uDCE5 \u901A\u77E5\u680F", quicksettings: "\u2699\uFE0F \u5FEB\u6377\u8BBE\u7F6E" };
    fetch(A + "/" + a, { method: "POST" }).then(function () { toast(nm[a] || a); sa(nm[a] || a); setTimeout(rd, 800) }).catch(function () { toast("failed") })
}
function vol(adj) { var ep = adj > 0 ? "/volume/up" : "/volume/down"; fetch(A + ep, { method: "POST" }).then(function () { var m = adj > 0 ? "\uD83D\uDD0A \u97F3\u91CF+" : "\uD83D\uDD09 \u97F3\u91CF-"; toast(m); sa(m) }).catch(function () { toast("failed") }) }
var _flashOn = false;
function toggleFlash() { _flashOn = !_flashOn; fetch(A + "/flashlight/" + _flashOn, { method: "POST" }).then(function () { toast(_flashOn ? "\uD83D\uDD26 ON" : "\uD83D\uDD26 OFF"); sa("\u624B\u7535\u7B52: " + (_flashOn ? "ON" : "OFF")) }).catch(function () { _flashOn = !_flashOn; toast("failed") }) }
var _rotDeg = 0;
function rotateScreen() { _rotDeg = (_rotDeg + 90) % 360; fetch(A + "/rotate/" + _rotDeg, { method: "POST" }).then(function () { toast("\uD83D\uDD04 " + _rotDeg + "\u00B0"); sa("\u65CB\u8F6C: " + _rotDeg + "\u00B0") }).catch(function () { toast("failed") }) }
function bri(lv) { fetch(A + "/brightness/" + lv, { method: "POST" }).then(function () { var m = lv > 100 ? "\uD83D\uDD06 \u4EAE\u5EA6+" : "\uD83D\uDD05 \u4EAE\u5EA6-"; toast(m); sa(m) }).catch(function () { toast("failed") }) }
function post(p, m) { fetch(A + p, { method: "POST" }).then(function () { toast(m); sa(m); setTimeout(rd, 800) }).catch(function () { toast("failed") }) }
function nlc(t) { sa("\u26A1 " + t + "..."); snl(t) }
function doVt() {
    sp("\uD83C\uDF33 View\u6811", '<span class="ld"></span>');
    fetch(A + "/viewtree?depth=3").then(function (r) { return r.json() }).then(function (d) {
        var tx = JSON.stringify(d, null, 2); if (tx.length > 4000) tx = tx.substring(0, 4000) + "\n...(truncated)";
        sp("\uD83C\uDF33 View\u6811", '<pre style="font-size:10px;white-space:pre-wrap;color:var(--txt2);overflow-x:auto">' + esc(tx) + "</pre>"); sa("View\u6811");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doWi() {
    fetch(A + "/windowinfo").then(function (r) { return r.json() }).then(function (d) {
        var h = ""; h += rw("\u5305\u540D", d.packageName || "-"); h += rw("\u8282\u70B9\u6570", d.nodeCount || "-");
        if (d.windowTitle) h += rw("\u6807\u9898", d.windowTitle); sp("\uD83E\uDE9F \u7A97\u53E3\u4FE1\u606F", h); sa("\u7A97\u53E3\u4FE1\u606F");
    }).catch(function (e) { sp("\u274C", esc(e.message)) })
}
function doFc() { var v = document.getElementById("ckIn").value.trim(); if (!v) { toast("\u8BF7\u8F93\u5165\u76EE\u6807"); return } fcd(v); document.getElementById("ckIn").value = "" }
function fcd(t) {
    cp(); sa("\uD83C\uDFAF \u70B9\u51FB: " + t + "..."); toast("\uD83C\uDFAF " + t);
    fetch(A + "/findclick", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) }).then(function (r) { return r.json() }).then(function (d) {
        if (d.ok) { toast("\u2705 \u5DF2\u70B9\u51FB: " + t); sa("\u2705 \u70B9\u51FB\u6210\u529F: " + t) }
        else { toast("\u274C \u672A\u627E\u5230: " + t); sa("\u274C \u672A\u627E\u5230: " + t) } setTimeout(rd, 600);
    }).catch(function () { toast("\u64CD\u4F5C\u5931\u8D25"); sa("\u274C \u70B9\u51FB\u5931\u8D25") })
}
function doTx() {
    var v = document.getElementById("txIn").value.trim(); if (!v) { toast("\u8BF7\u8F93\u5165\u6587\u5B57"); return }
    fetch(A + "/text", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: v }) }).then(function () {
        toast("\u2328\uFE0F \u5DF2\u8F93\u5165"); sa("\u2328\uFE0F \u8F93\u5165: " + v); document.getElementById("txIn").value = "";
    }).catch(function () { toast("\u8F93\u5165\u5931\u8D25") })
}
function doOa() {
    var v = document.getElementById("apIn").value.trim(); if (!v) { toast("\u8BF7\u8F93\u5165APP\u540D"); return }
    sa("\uD83D\uDE80 \u6253\u5F00 " + v + "..."); document.getElementById("apIn").value = ""; snl("\u6253\u5F00" + v)
}
function opkg(p) {
    cp(); sa("\uD83D\uDE80 " + p.replace("com.", ""));
    fetch(A + "/openapp", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ packageName: p }) }).then(function () {
        toast("\u5DF2\u6253\u5F00"); setTimeout(rd, 1000)
    }).catch(function () { toast("\u6253\u5F00\u5931\u8D25") })
}
function sendCmd() { var v = document.getElementById("cmdIn").value.trim(); if (!v) return; document.getElementById("cmdIn").value = ""; snl(v) }
document.getElementById("cmdIn").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); sendCmd() } });
function snl(t) {
    sp("\u26A1 " + t, '<span class="ld"></span> ...');
    var ctrl = new AbortController(); var to = setTimeout(function () { ctrl.abort() }, 25000);
    fetch(A + "/command/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command: t }), signal: ctrl.signal }).then(function (resp) {
        clearTimeout(to); var rdr = resp.body.getReader(); var dec = new TextDecoder(); var buf = ""; var steps = [];
        function rloop() {
            rdr.read().then(function (r) {
                if (r.done) { scd(t, steps); return }
                buf += dec.decode(r.value, { stream: true }); var lines = buf.split("\n"); buf = lines.pop();
                for (var i = 0; i < lines.length; i++) { var ln = lines[i].trim(); if (ln.indexOf("data:") === 0) { try { steps.push(JSON.parse(ln.substring(5))) } catch (e) { } } }
                rloop();
            }).catch(function () { scd(t, steps) })
        } rloop();
    }).catch(function () {
        clearTimeout(to);
        fetch(A + "/command", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command: t }) }).then(function (r) { return r.json() }).then(function (d) {
            sp("\u26A1 " + t, '<div class="rv ' + (d.ok ? "ok" : "err") + '">' + (d.ok ? "\u2705 " : "\u274C ") + esc(d.result || d.message || d.error || "done") + "</div>");
            sa("\u26A1 " + t + ": " + (d.ok ? "OK" : "failed"))
        }).catch(function (e) { sp("\u274C", esc(e.message)) })
    })
}
function scd(t, steps) {
    if (!steps.length) { sp("\u26A1 " + t, '<div class="rv ok">\u2705 done</div>'); sa("\u26A1 " + t + ": done"); return }
    var h = ""; for (var i = 0; i < steps.length; i++) {
        var s = steps[i]; var c = s.ok === false ? "fail" : (s.done ? "ok" : "");
        h += '<div class="cs ' + c + '">' + esc(s.step || s.message || s.action || JSON.stringify(s)) + "</div>";
    }
    sp("\u26A1 " + t, h); sa("\u26A1 " + t + ": " + steps.length + " steps"); setTimeout(rd, 800)
}
var SR = window.SpeechRecognition || window.webkitSpeechRecognition; var rec = null, lis = false;
if (SR) {
    rec = new SR(); rec.lang = "zh-CN"; rec.continuous = false; rec.interimResults = true;
    rec.onresult = function (e) {
        var t = ""; for (var i = e.resultIndex; i < e.results.length; i++)t += e.results[i][0].transcript;
        document.getElementById("cmdIn").value = t; if (e.results[e.results.length - 1].isFinal) { sv(); snl(t.trim()) }
    };
    rec.onerror = function (e) { sv(); if (e.error !== "no-speech" && e.error !== "aborted") toast("voice: " + e.error) };
    rec.onend = function () { sv() }
}
function tv() { if (lis) { if (rec) rec.stop(); sv() } else { stv() } }
function stv() {
    if (!rec) { toast("\u8BED\u97F3\u4E0D\u53EF\u7528"); return } lis = true; document.getElementById("vf").classList.add("on");
    document.getElementById("cmdIn").value = ""; document.getElementById("cmdIn").placeholder = "\uD83C\uDF99 \u8BF4\u8BDD\u4E2D..."; try { rec.start() } catch (e) { }
}
function sv() { lis = false; document.getElementById("vf").classList.remove("on"); document.getElementById("cmdIn").placeholder = "\u8F93\u5165\u6307\u4EE4..." }
rd(); rm(); setInterval(rd, 5000); setInterval(rm, 20000);

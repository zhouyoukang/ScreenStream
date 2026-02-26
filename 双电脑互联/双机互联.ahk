#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

; ========================================
; 双电脑互联 — 持久快捷键（泰山不动版）
; 安装位置：两台机器各一份，自动检测本机身份
; ========================================

; 自动检测：我是笔记本还是台式机？
MyHostname := ComObjCreate("WScript.Shell").RegRead("HKLM\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName\ComputerName")
IsLaptop := InStr(A_ComputerName, "zhoumac") || InStr(A_UserName, "zhouyoukang")

if IsLaptop {
    PeerIP := "192.168.31.141"
    PeerName := "台式机"
    MyRDP := A_ScriptDir . "\台式机.rdp"
    PeerAgent := "http://192.168.31.141:9903"
    MyAgent := "http://192.168.31.179:9903"
} else {
    PeerIP := "192.168.31.179"
    PeerName := "笔记本"
    MyRDP := "C:\Users\Administrator\Desktop\笔记本.rdp"
    PeerAgent := "http://192.168.31.179:9903"
    MyAgent := "http://192.168.31.141:9903"
}

; 托盘图标提示
A_IconTip := "双机互联 | 我是" . (IsLaptop ? "笔记本" : "台式机") . " | Win+D=RDP | Win+G=Web | Win+H=健康"

; ===== Win+D: RDP连接对方桌面 =====
#d:: {
    if FileExist(MyRDP)
        Run MyRDP
    else
        Run "mstsc /v:" . PeerIP . " /admin"
}

; ===== Win+G: 浏览器打开对方Web控制台 =====
#g:: {
    Run PeerAgent
}

; ===== Win+H: 双机健康检查（托盘气泡通知）=====
#h:: {
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", PeerAgent . "/health", true)
        whr.Send()
        whr.WaitForResponse(3)
        resp := whr.ResponseText
        if InStr(resp, "ok")
            status := "✅ " . PeerName . " 在线"
        else
            status := "⚠️ " . PeerName . " 异常"
    } catch {
        status := "❌ " . PeerName . " 离线"
    }

    try {
        whr2 := ComObject("WinHttp.WinHttpRequest.5.1")
        whr2.Open("GET", MyAgent . "/health", true)
        whr2.Send()
        whr2.WaitForResponse(3)
        resp2 := whr2.ResponseText
        if InStr(resp2, "ok")
            status .= " | ✅ 本机agent在线"
        else
            status .= " | ⚠️ 本机agent异常"
    } catch {
        status .= " | ❌ 本机agent离线"
    }

    TrayTip status, "双机互联", "0x1"
}

; ===== Win+S: 截屏对方桌面（保存到桌面）=====
#s:: {
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", PeerAgent . "/screenshot?quality=70", true)
        whr.Send()
        whr.WaitForResponse(10)
        TrayTip "截屏已获取，请在浏览器查看", "双机互联", "0x1"
        Run PeerAgent . "/screenshot?quality=70"
    } catch {
        TrayTip "❌ 截屏失败：" . PeerName . " 不可达", "双机互联", "0x3"
    }
}

; ===== Win+K: 对方锁屏 =====
#k:: {
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("POST", PeerAgent . "/power", true)
        whr.SetRequestHeader("Content-Type", "application/json")
        whr.Send('{"action":"lock"}')
        whr.WaitForResponse(3)
        TrayTip PeerName . " 已锁屏", "双机互联", "0x1"
    } catch {
        TrayTip "❌ 锁屏失败", "双机互联", "0x3"
    }
}

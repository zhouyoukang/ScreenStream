# ScreenStream_v2 Code Navigation Index
> Auto-generated. AI reads this FIRST to locate insertion points, avoiding 3600+ line scans.
> Last updated: 2026-02-20

## InputService.kt (3605 lines)
### Section Map
| Section | Lines | Description |
|---------|-------|-------------|
| Imports + Class header | 1-63 | Package, imports, companion object |
| AccessibilityEvent handlers | 80-97 | onAccessibilityEvent, onInterrupt |
| Service lifecycle | 99-115 | onServiceConnected, onDestroy |
| Pointer/Mouse events | 117-159 | onPointerEvent (button mask logic) |
| Stroke gestures | 160-300 | startStroke, continueStroke, endStroke, dispatchClick |
| IME overlay | 304-365 | setupImeOverlay, removeImeOverlay, hideSoftKeyboard |
| Keyboard input | 366-425 | onKeyEvent (keysym mapping, modifiers) |
| Navigation actions | 426-470 | goHome, goBack, showRecents, showNotifications, volumeUp/Down, lockScreen |
| Text input engine | 474-650 | inputText, setClipboard, findFocusedNode, getRealText, getSelection |
| Cursor/Selection ops | 642-945 | deleteBackward/Forward, moveCursor, selectAll, copy, paste, cut |
| WebSocket touch stream | 948-972 | onTouchStreamStart/Move/End |
| System actions (v31) | 974-1030 | wakeScreen, showPowerDialog, takeScreenshot, toggleSplitScreen, setBrightness |
| Enhanced gestures (v31) | 1028-1130 | longPress, doubleTap, scrollNormalized, pinchZoom, openApp, openUrl |
| Device info (v31) | 1132-1240 | getDeviceInfo, getInstalledApps, getClipboardText |
| Screen off mode | 1236-1315 | toggleScreenOff, setMinimumBrightness, restoreBrightness |
| Stay awake / Show touches | 1316-1385 | setStayAwake, setShowTouches, setRotation |
| Media control (v33) | 1387-1415 | mediaControl (play/pause/next/prev/stop) |
| Find phone (v33) | 1416-1455 | findPhone (ring + auto-stop) |
| Device control (v33) | 1454-1610 | vibrateDevice, setFlashlight, setDndMode, setVolumeLevel, setAutoRotate, getForegroundApp, killForegroundApp, saveFile |
| File manager (S33) | 1624-1895 | sanitizePath, fileToJson, listFiles, getFileInfo, createDirectory, removeFile, renameFile, moveFile, copyFile, readTextFile, readFileBase64, uploadFile, searchFiles, getStorageInfo |
| AI Brain - View tree (v32) | 1895-2155 | getViewTree, serializeNode, findAndClickByText/ById, dismissTopDialog, findNodesByText, setNodeText |
| Platform layer (v35) | 2154-2375 | sendIntent, extractScreenText, waitForCondition, onNotificationEvent, getNotifications |
| Semantic demos | 2377-2785 | runSemanticDemo, runWifiToggleDemo |
| Natural language commands | 2788-3475 | executeNaturalCommand, runAgentPath, executeCompoundCommand, splitCompoundCommand, executeSingleStep |
| App opener helper | 3481-3575 | executeOpenApp (known apps map + search) |
| Window info | 3577-3605 | getActiveWindowInfo |

### INSERT POINTS (where to add new code)
- **New system action**: After line ~1030 (after setBrightness)
- **New device control API**: After line ~1610 (after saveFile, before file manager)
- **New file manager op**: After line ~1895 (after getStorageInfo)
- **New AI Brain method**: After line ~2155 (after setNodeText)
- **New platform method**: After line ~2375 (after getNotifications)

## InputRoutes.kt (784 lines)
### Section Map
| Section | Lines | Description |
|---------|-------|-------------|
| Imports + helpers | 1-35 | jsonOk, jsonError, requireInputService |
| Basic control routes | 37-111 | /status, /tap, /swipe, /key, /text, /pointer, /home, /back, etc. |
| System actions | 112-133 | /wake, /power, /screenshot, /splitscreen, /brightness |
| Enhanced gestures | 135-174 | /longpress, /doubletap, /scroll, /pinch |
| App & device mgmt | 176-227 | /openapp, /openurl, /deviceinfo, /apps, /clipboard, /scaling, /enable |
| AI Brain routes | 229-274 | /viewtree, /windowinfo, /findclick, /dismiss, /findnodes, /settext |
| Media/Device control | 276-418 | /media, /findphone, /vibrate, /flashlight, /dnd, /volume, /autorotate, /foreground, /killapp, /upload, /stayawake, /showtouches, /rotate |
| Macro system | 420-527 | /macro/list, /macro/create, /macro/run, /macro/run-inline, etc. |
| File manager (S33) | 529-639 | /files/storage, /files/list, etc. |
| Semantic demos | 641-684 | /demo/semantic, /demo/wifi, /command, /command/stream |
| Platform layer | 686-716 | /intent, /screen/text, /wait, /notifications/read |
| Macro triggers | 718-755 | /macro/triggers, /macro/trigger/{id}, /macro/trigger/{id}/remove |
| WebSocket | 757-783 | /ws/touch |

### INSERT POINTS
- **New basic route**: After line ~111
- **New device control route**: After line ~418
- **New macro route**: After line ~527
- **New file route**: After line ~639
- **New platform route**: After line ~716

## index.html (5841 lines) — Frontend Structure Map
### Section Map
| Section | Lines | Description |
|---------|-------|-------------|
| HTML head + CSS | 1-860 | Styles, themes, panel CSS, animations |
| HTML body (controls) | 860-950 | Navigation bar, buttons, AI command bar |
| AI Command Bar | 954-1130 | toggleAiCommand, runAiCommand, processChunk, escapeHtml |
| Agent API interface | 1130-1240 | Cascade LLM Brain Interface |
| Command Menu | 1240-1415 | toggleCommandMenu, buildMenuHTML, menuAction, menuSection |
| Device Info Panel | 1416-1460 | toggleDeviceInfoPanel, refreshDeviceInfo |
| Macro Panel | 1460-1670 | toggleMacroPanel, CRUD, triggers UI |
| Macro Export/Import | 1670-1775 | exportAllMacros, handleMacroImport |
| Quick actions (legacy) | 1775-1860 | showClipboard, showAppList, aiFindClick, aiDismiss |
| Screenshot + display | 1860-2000 | takeScreenshot, toggleCrop169 |
| Debug/VR panels | 2000-2140 | Debug console, VR input, gamepad |
| Core input engine | 2140-2310 | getInputApiBase, getStreamImagePoint, sendInputJson, sendPointer, sendTap |
| Touch visual feedback | 2304-2355 | createRipple, showTouchDot |
| WebSocket touch + gestures | 2356-2450 | connectTouchWs, multi-touch, Ctrl+pinch |
| Mobile viewer mode | 2421-2460 | initMobileMode, toggleMobileNav, sendSwipe |
| Mouse/pointer handlers | 2460-2810 | mousedown/up/move, touch handlers, scroll |
| Status/UI utilities | 2811-2975 | showStatus, showInputStatus, joystick, fine-tune scroll |
| Keyboard input | 2977-3178 | Keyboard handlers, clipboard, key mapping |
| Shortcuts (scrcpy compat) | 3178-3300 | Alt+H/B/S/F/1-0/etc. |
| Button config + fullscreen | 3300-3415 | configureButtons, fullscreen handlers |
| Shortcut help panel | 3415-3430 | toggleShortcutHelp |
| FPS/Latency overlay | 3429-3460 | togglePerfOverlay, countFrame |
| Display transforms | 3460-3505 | rotateDisplay, togglePixelPerfect, togglePiP |
| Screenshot enhanced (M18) | 3506-3560 | captureScreenshot, captureWithAnnotations |
| Gamepad API | 3562-3620 | pollGamepad, button mapping |
| Device control toggles | 3618-3655 | toggleFlashlight/Dnd/FindPhone/AutoRotate |
| Session recording | 3655-3720 | toggleRecording, startRecording, stopRecording |
| Annotation/whiteboard | 3721-3785 | toggleAnnotation, Canvas drawing |
| File upload (drag&drop) | 3785-3830 | showFileUpload |
| QR code | 3828-3845 | showQrCode |
| Game mode | 3845-3865 | toggleGameMode |
| Theme toggle | 3864-3880 | toggleTheme |
| Session timer | 3880-3895 | Timer display |
| Battery widget | 3897-3930 | updateBatteryWidget |
| Connection history | 3913-3930 | saveConnectionHistory |
| M12: Image tools | 3930-3975 | toggleMirror, cycleFilter, zoomStream, resetStreamView |
| M15: Text snippets | 3975-4045 | showTextSnippets, sendSnippet |
| Connection info | 4020-4050 | showConnectionInfo |
| Traffic stats | 4048-4080 | toggleTrafficStats |
| S33: File Manager | 4074-4640 | Full file manager panel (550+ lines) |
| Platform panels shared | 4645-4670 | closePlatformPanels, panelError, isPlatformPanelOpen |
| S34: APP Launcher | 4670-4705 | toggleAppLauncher |
| S35: Notification Center | 4705-4770 | toggleNotifCenter |
| S36: Screen Reader | 4770-4840 | toggleScreenReader |
| S37: Quick Actions | 4840-4920 | toggleQuickActions |
| S38: Device Dashboard | 4920-5010 | toggleDevDashboard |
| S39: Workflow Builder | 5010-5160 | toggleWorkflowBuilder |
| S40: App Monitor | 5160-5220 | toggleAppMonitor |
| S41: Remote Browser | 5220-5290 | toggleRemoteBrowser |
| S42: Clipboard History | 5290-5370 | toggleClipHistory |
| S43: Batch Runner | 5370-5460 | toggleBatchRunner |
| S48: Quick Transfer | 5460-5580 | toggleQuickShare |
| S49: Gesture Panel | 5580-5760 | toggleGesturePanel |
| Init + WebSocket setup | 5760-5841 | Window load, stream connect, WS setup |

### INSERT POINTS
- **New command menu item**: In buildMenuHTML() around line ~1290-1375
- **New platform panel**: After line ~5460 (before S48), follow S34-S43 pattern
- **New device control toggle**: After line ~3650
- **New image/display tool**: After line ~3975
- **New shortcut key**: In keydown handler around line ~3178-3240

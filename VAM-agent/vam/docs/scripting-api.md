# VAM Scripting API 速查表

> 常用类、方法、属性快速参考

## 核心类

### SuperController (全局单例)

```csharp
var sc = SuperController.singleton;

// Atom管理
sc.GetAtomByUid(string uid) → Atom
sc.GetAtomUIDs() → List<string>
sc.GetAtoms() → List<Atom>
sc.AddAtom(string type, string uid) → Atom
sc.RemoveAtom(Atom atom)

// 消息
sc.LogMessage(string msg)
sc.LogError(string msg)

// 场景
sc.Load(string scenePath)
sc.Save(string path)
sc.ClearAll()

// 时间
sc.freezeAnimation → bool (暂停所有动画)
sc.motionAnimationMaster → MotionAnimationMaster

// 导航
sc.NavigateToAtom(Atom atom)
sc.SelectController(FreeControllerV3 ctrl)
```

### Atom

```csharp
Atom atom = containingAtom;

// 属性
atom.uid → string
atom.type → string
atom.on → bool
atom.hidden → bool

// 组件
atom.GetStorableByID(string id) → JSONStorable
atom.GetStorableIDs() → List<string>
atom.GetComponentInChildren<T>() → T

// 控制器
atom.freeControllers → FreeControllerV3[]
atom.mainController → FreeControllerV3
```

### FreeControllerV3 (控制器)

```csharp
FreeControllerV3 ctrl = atom.mainController;

// 位置/旋转
ctrl.transform.position → Vector3
ctrl.transform.rotation → Quaternion
ctrl.transform.localPosition → Vector3

// 物理
ctrl.currentPositionState → PositionState (Off/Comply/On/Lock/...)
ctrl.currentRotationState → RotationState
ctrl.RBHoldPositionSpring → float
ctrl.RBHoldRotationSpring → float
```

### JSONStorable (数据存储基类)

```csharp
JSONStorable storable = atom.GetStorableByID("geometry");

// 获取参数
storable.GetFloatParamNames() → List<string>
storable.GetFloatJSONParam(string name) → JSONStorableFloat
storable.GetBoolParamNames() → List<string>
storable.GetBoolJSONParam(string name) → JSONStorableBool
storable.GetStringParamNames() → List<string>
storable.GetAction(string name) → JSONStorableAction

// 调用动作
storable.CallAction(string actionName)
```

## 参数类型

### JSONStorableFloat

```csharp
// 创建
var f = new JSONStorableFloat("name", defaultVal, minVal, maxVal);
f.val → float (读写)
f.setCallbackFunction = (float val) => { /* 值变化回调 */ };
```

### JSONStorableBool

```csharp
var b = new JSONStorableBool("name", defaultVal);
b.val → bool
b.setCallbackFunction = (bool val) => { /* 回调 */ };
```

### JSONStorableString

```csharp
var s = new JSONStorableString("name", "default");
s.val → string
s.setCallbackFunction = (string val) => { /* 回调 */ };
```

### JSONStorableStringChooser

```csharp
var c = new JSONStorableStringChooser("name", choices, defaultVal, "显示名");
c.val → string
c.choices → List<string>
c.setCallbackFunction = (string val) => { /* 回调 */ };
```

### JSONStorableAction

```csharp
var a = new JSONStorableAction("name", () => { /* 执行 */ });
a.actionCallback → Action
```

## UI控件

```csharp
// MVRScript 中创建UI (rightSide=true 放右侧)

CreateButton(string label, bool rightSide = false) → UIDynamicButton
CreateSlider(JSONStorableFloat param, bool rightSide = false) → UIDynamicSlider
CreateToggle(JSONStorableBool param, bool rightSide = false) → UIDynamicToggle
CreateTextField(JSONStorableString param, bool rightSide = false) → UIDynamicTextField
CreateScrollablePopup(JSONStorableStringChooser param, bool rightSide = false) → UIDynamicPopup
CreateColorPicker(JSONStorableColor param, bool rightSide = false) → UIDynamicColorPicker
CreateSpacer(bool rightSide = false) → UIDynamic

// 移除UI
RemoveButton(UIDynamicButton btn)
RemoveSlider(UIDynamicSlider slider)
RemoveToggle(UIDynamicToggle toggle)
RemoveSpacer(UIDynamic spacer)
```

## 协程

```csharp
// 启动
StartCoroutine(MyCoroutine());

IEnumerator MyCoroutine()
{
    yield return new WaitForSeconds(1f);     // 等1秒
    yield return new WaitForEndOfFrame();     // 等帧结束
    yield return new WaitForFixedUpdate();    // 等物理更新
    yield return null;                        // 等下一帧
}
```

## 外观/形态

```csharp
// DAZCharacterSelector
DAZCharacterSelector dcs = atom.GetComponentInChildren<DAZCharacterSelector>();
dcs.gender → DAZCharacterSelector.Gender

// DAZMorph
DAZMorph morph = dcs.morphsControlUI.GetMorphByDisplayName("Brow Height");
morph.morphValue = 0.5f;

// 列出所有morph
foreach (var m in dcs.morphsControlUI.GetMorphDisplayNames())
{
    SuperController.LogMessage(m);
}
```

## 物理/碰撞

```csharp
// Rigidbody
Rigidbody rb = ctrl.GetComponent<Rigidbody>();
rb.velocity → Vector3
rb.AddForce(Vector3 force)

// 碰撞检测
void OnCollisionEnter(Collision col) { }
void OnTriggerEnter(Collider col) { }
```

## 音频

```csharp
// AudioSource
AudioSource audio = containingAtom.GetComponentInChildren<AudioSource>();
audio.Play();
audio.Stop();
audio.clip = myClip;
audio.volume = 0.5f;

// 加载音频
AudioClip clip = URLAudioClipManager.singleton.GetClip(url);
```

## 文件IO (有限制)

```csharp
// VAM沙盒内可用的路径
string savesPath = SuperController.singleton.savesDir;
string customPath = SuperController.singleton.customDir;

// 读写JSON
JSONNode data = JSON.Parse(System.IO.File.ReadAllText(path));
System.IO.File.WriteAllText(path, data.ToString());
```

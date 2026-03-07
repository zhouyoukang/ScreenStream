# VAM 插件开发指南

> 基于 Scripter 插件的 C# 脚本开发入门

## 开发环境

### 必备工具

- **VS Code** — 推荐IDE，配合C#扩展
- **Scripter插件** — AcidBubbles.Scripter (已安装 v1.5.1)
- **.NET Framework** — VAM基于Unity Mono，使用.NET 3.5/4.x子集

### 本地路径

- Scripter源码: `F:\vam1.22\scripter.github\vam-scripter-1.5.1\`
- VAR包: `F:\vam1.22\scripter.github\AcidBubbles.Scripter1.21.var`
- 编译脚本: `F:\vam1.22\scripter.github\CompileScripter.bat`
- VS Code配置: `F:\vam1.22\scripter.github\.vscode\`

## 插件类型

### 1. Scripter 脚本 (推荐入门)

在VAM内直接编写C#代码，实时编译运行。

```csharp
// 最简脚本模板
public class MyPlugin : MVRScript
{
    public override void Init()
    {
        SuperController.LogMessage("Hello VAM!");
    }

    public override void Update()
    {
        // 每帧执行
    }

    public void OnDestroy()
    {
        // 清理资源
    }
}
```

### 2. 预编译插件 (.cs 文件)

放入 `Custom/Scripts/` 目录，VAM启动时加载。

### 3. VAR包插件

打包为 `.var` 格式分发，包含代码+资源+元数据。

## 核心API

### MVRScript (基类)

所有VAM脚本必须继承 `MVRScript`。

```csharp
public class MyScript : MVRScript
{
    // 生命周期
    public override void Init() { }         // 初始化
    public override void Update() { }       // 每帧更新
    public void FixedUpdate() { }           // 物理更新
    public void LateUpdate() { }            // 延迟更新
    public void OnDestroy() { }             // 销毁清理

    // 常用属性
    // containingAtom  — 当前Atom对象
    // manager         — 插件管理器
    // storeId         — 存储ID
}
```

### Atom 操作

```csharp
// 获取当前Atom
Atom myAtom = containingAtom;

// 获取其他Atom
Atom person = SuperController.singleton.GetAtomByUid("Person");

// 获取所有Atom
List<string> atomUIDs = SuperController.singleton.GetAtomUIDs();
```

### 参数系统

```csharp
// 创建Float参数
JSONStorableFloat speed = new JSONStorableFloat("speed", 1f, 0f, 10f);
RegisterFloat(speed);
CreateSlider(speed);

// 创建Bool参数
JSONStorableBool enabled = new JSONStorableBool("enabled", true);
RegisterBool(enabled);
CreateToggle(enabled);

// 创建String参数
JSONStorableString text = new JSONStorableString("text", "hello");
RegisterString(text);
CreateTextField(text);

// 创建Action按钮
JSONStorableAction doSomething = new JSONStorableAction("doSomething", () => {
    SuperController.LogMessage("Button clicked!");
});
RegisterAction(doSomething);
CreateButton("Do Something").button.onClick.AddListener(() => doSomething.actionCallback());
```

### 触发器系统

```csharp
// 触发器示例
TriggerActionDiscrete trigger = new TriggerActionDiscrete();
trigger.receiverAtom = targetAtom;
trigger.receiver = targetStorable;
trigger.receiverTargetName = "actionName";
```

### 动画控制

```csharp
// 获取动画组件
AnimationPattern ap = containingAtom.GetComponentInChildren<AnimationPattern>();

// 播放/停止
ap.Play();
ap.Pause();
ap.ResetAndPlay();

// Timeline插件交互
JSONStorable timeline = containingAtom.GetStorableByID("plugin#0_AcidBubbles.Timeline");
if (timeline != null)
{
    timeline.CallAction("Play");
    timeline.CallAction("Stop");
}
```

## UI 开发

```csharp
public override void Init()
{
    // 左侧面板
    CreateButton("左侧按钮").button.onClick.AddListener(() => {
        SuperController.LogMessage("左侧点击");
    });

    // 右侧面板
    CreateButton("右侧按钮", true).button.onClick.AddListener(() => {
        SuperController.LogMessage("右侧点击");
    });

    // 下拉菜单
    List<string> choices = new List<string> { "选项A", "选项B", "选项C" };
    JSONStorableStringChooser chooser = new JSONStorableStringChooser(
        "myChoice", choices, "选项A", "选择");
    RegisterStringChooser(chooser);
    CreateScrollablePopup(chooser);

    // 文本显示
    JSONStorableString info = new JSONStorableString("info", "信息显示区域");
    CreateTextField(info, true);
}
```

## 与 Voxta 交互

```csharp
// 通过BrowserAssist或HTTP与Voxta通信
IEnumerator SendToVoxta(string message)
{
    string url = "http://localhost:5384/api/chat";
    string json = $"{{\"message\":\"{message}\"}}";

    var request = new UnityWebRequest(url, "POST");
    byte[] body = System.Text.Encoding.UTF8.GetBytes(json);
    request.uploadHandler = new UploadHandlerRaw(body);
    request.downloadHandler = new DownloadHandlerBuffer();
    request.SetRequestHeader("Content-Type", "application/json");

    yield return request.SendWebRequest();

    if (!request.isNetworkError)
    {
        string response = request.downloadHandler.text;
        SuperController.LogMessage($"Voxta: {response}");
    }
}
```

## 最佳实践

1. **Init中注册所有参数** — 保证存档/加载正确
2. **OnDestroy中清理资源** — 防止内存泄漏
3. **避免Update中重操作** — 保持帧率
4. **使用Coroutine做异步** — 网络请求、延迟操作
5. **测试存档兼容性** — 确保场景保存/加载后插件正常

## 编译与部署

```powershell
# 使用本地编译脚本
F:\vam1.22\scripter.github\CompileScripter.bat

# 部署到VAM
F:\vam1.22\scripter.github\DeployToVaM.bat

# 打包为VAR
# 使用VaM内置的Package Builder
```

## 参考资料

- Scripter文档: https://acidbubbles.github.io/vam-scripter/
- Timeline文档: https://acidbubbles.github.io/vam-timeline/
- VAM Wiki: https://vam.fandom.com/wiki/Plugin_Development

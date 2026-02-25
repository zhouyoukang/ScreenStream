# Android WebView项目模板

> **快速创建**：WebView封装PWA的标准Android项目结构

## 目录结构
```
android-project/
├── app/
│   ├── build.gradle              # 应用级构建配置
│   ├── src/main/
│   │   ├── AndroidManifest.xml   # 应用清单
│   │   ├── java/com/项目/包名/
│   │   │   └── MainActivity.java # 主Activity
│   │   ├── assets/
│   │   │   └── app.html         # PWA文件
│   │   └── res/
│   │       ├── values/
│   │       │   ├── colors.xml   # 颜色资源
│   │       │   └── strings.xml  # 字符串资源
│   │       └── mipmap-*/
│   │           └── ic_launcher.png # 应用图标
├── build.gradle                 # 项目级构建配置
├── gradle.properties            # Gradle属性
└── settings.gradle             # 项目设置
```

## 文件模板

### 1. AndroidManifest.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.项目.包名">

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="应用名"
        android:theme="@android:style/Theme.Material.NoActionBar"
        android:usesCleartextTraffic="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait"
            android:theme="@android:style/Theme.Material.NoActionBar.Fullscreen">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>

    <!-- 基础权限 -->
    <uses-permission android:name="android.permission.INTERNET" />

</manifest>
```

### 2. MainActivity.java
```java
package com.项目.包名;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    
    private WebView webView;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // 沉浸式全屏配置
        setupFullscreen();
        
        // WebView初始化
        setupWebView();
        
        // 加载PWA应用
        webView.loadUrl("file:///android_asset/app.html");
    }
    
    private void setupFullscreen() {
        // 无标题栏
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        
        // 隐藏导航栏
        View decorView = getWindow().getDecorView();
        int uiOptions = View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
        decorView.setSystemUiVisibility(uiOptions);
    }
    
    private void setupWebView() {
        webView = new WebView(this);
        setContentView(webView);
        
        WebSettings settings = webView.getSettings();
        
        // JavaScript支持
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        
        // 离线配置
        settings.setCacheMode(WebSettings.LOAD_CACHE_ONLY);
        settings.setBlockNetworkLoads(true);
        
        // 文件访问权限
        settings.setAllowFileAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        
        // 禁用缩放控制
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        
        // WebView客户端
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // 阻止外部链接，保持离线
                return true;
            }
        });
        
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onReceivedTitle(WebView view, String title) {
                super.onReceivedTitle(view, title);
            }
        });
    }
    
    @Override
    public void onBackPressed() {
        // 返回键处理
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
    
    @Override
    protected void onDestroy() {
        // 清理WebView
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
```

### 3. app/build.gradle
```gradle
apply plugin: 'com.android.application'

android {
    compileSdkVersion 34
    buildToolsVersion "34.0.0"
    
    defaultConfig {
        applicationId "com.项目.包名"
        minSdkVersion 21
        targetSdkVersion 34
        versionCode 1
        versionName "1.0"
    }
    
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    
    packagingOptions {
        pickFirst '**/libc++_shared.so'
        pickFirst '**/libjsc.so'
    }
    
    namespace 'com.项目.包名'
}

dependencies {
    implementation 'androidx.appcompat:appcompat:1.6.1'
}
```

### 4. build.gradle (项目级)
```gradle
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.1.0'
    }
}

task clean(type: Delete) {
    delete rootProject.buildDir
}
```

### 5. gradle.properties
```properties
# Project-wide Gradle settings
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true

# AndroidX
android.useAndroidX=true
android.nonTransitiveRClass=true

# Build cache
org.gradle.caching=false

# Chinese path compatibility
android.overridePathCheck=true
```

### 6. settings.gradle
```gradle
pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "应用名"
include ':app'
```

### 7. colors.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="colorPrimary">#主色值</color>
    <color name="colorPrimaryDark">#主色暗值</color>
    <color name="colorAccent">#强调色</color>
    <color name="background">#背景色</color>
</resources>
```

### 8. strings.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">应用名</string>
</resources>
```

## 快速配置脚本

### PowerShell模板生成脚本
```powershell
# create-android-project.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$AppName,
    
    [Parameter(Mandatory=$true)]
    [string]$PackageName,
    
    [string]$OutputDir = ".",
    [string]$ThemeColor = "#e91e8c"
)

$ProjectDir = Join-Path $OutputDir $AppName

# 创建目录结构
$dirs = @(
    "app/src/main/java/com/$($PackageName.Replace('.', '/'))",
    "app/src/main/assets",
    "app/src/main/res/values",
    "app/src/main/res/mipmap-mdpi"
)

foreach ($dir in $dirs) {
    $fullPath = Join-Path $ProjectDir $dir
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
}

Write-Output "Android项目模板已创建: $ProjectDir"
Write-Output "请手动复制PWA文件到 app/src/main/assets/app.html"
```

## 自定义配置

### 权限配置
根据PWA功能需求添加权限：
```xml
<!-- 网络访问 -->
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

<!-- 存储访问 -->
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />

<!-- 相机访问 -->
<uses-permission android:name="android.permission.CAMERA" />

<!-- 位置访问 -->
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
```

### ProGuard规则 (proguard-rules.pro)
```
# WebView相关
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# 保持WebView接口
-keepclassmembers class android.webkit.WebViewClient {
    public void *(android.webkit.WebView, java.lang.String, android.graphics.Bitmap);
    public boolean *(android.webkit.WebView, java.lang.String);
}
```

### 图标生成建议
- **mdpi (48x48)**：基础尺寸
- **hdpi (72x72)**：高密度屏幕
- **xhdpi (96x96)**：超高密度屏幕  
- **xxhdpi (144x144)**：超超高密度屏幕

## 构建和部署

### 本地构建
```bash
# 设置环境变量
export JAVA_HOME="/path/to/jdk"
export ANDROID_SDK_ROOT="/path/to/android-sdk"

# 构建Debug版本
./gradlew assembleDebug

# 构建Release版本
./gradlew assembleRelease
```

### CI/CD集成
```yaml
# GitHub Actions示例
name: Android Build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-java@v3
      with:
        java-version: '11'
        distribution: 'temurin'
    - uses: android-actions/setup-android@v2
    - name: Build APK
      run: ./gradlew assembleDebug
    - name: Upload APK
      uses: actions/upload-artifact@v3
      with:
        name: app-debug.apk
        path: app/build/outputs/apk/debug/app-debug.apk
```

## 最佳实践

1. **版本兼容性**
   - minSdkVersion 21 (Android 5.0+)
   - targetSdkVersion 使用最新稳定版
   - 及时移除废弃API

2. **性能优化**
   - WebView硬件加速
   - 内存泄漏防护
   - 合理的缓存策略

3. **安全考虑**
   - 文件访问权限最小化
   - HTTPS证书验证
   - 用户数据保护

4. **用户体验**
   - 启动画面优化
   - 网络状态处理
   - 错误页面友好

## 常见问题

**Q: WebView白屏问题？**
A: 检查assets文件路径和JavaScript权限

**Q: 中文路径编译失败？**
A: 添加`android.overridePathCheck=true`

**Q: APK体积过大？**
A: 使用ProGuard压缩和资源优化

**Q: 在某些设备上崩溃？**
A: 检查API兼容性和内存使用

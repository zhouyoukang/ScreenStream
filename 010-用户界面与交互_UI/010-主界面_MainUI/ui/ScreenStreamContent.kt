package info.dvkr.screenstream.ui

import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.EaseIn
import androidx.compose.animation.core.EaseOut
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarDefaults
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.material3.adaptive.currentWindowSize
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffoldDefaults
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffoldLayout
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteType
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onPlaced
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.toIntRect
import androidx.compose.ui.unit.toRect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.dropUnlessStarted
import androidx.window.core.layout.WindowSizeClass
import info.dvkr.screenstream.AppReview
import info.dvkr.screenstream.R
import info.dvkr.screenstream.logger.AppLogger
import info.dvkr.screenstream.logger.CollectingLogsUi
import info.dvkr.screenstream.notification.NotificationPermission
import info.dvkr.screenstream.ui.tabs.AppTabs
import info.dvkr.screenstream.ui.tabs.about.AboutTabContent
import info.dvkr.screenstream.ui.tabs.exit.ExitTabContent
import info.dvkr.screenstream.ui.tabs.settings.SettingsTabContent
import info.dvkr.screenstream.ui.tabs.stream.StreamTabContent
import info.dvkr.screenstream.input.InputService
import kotlinx.coroutines.flow.StateFlow

@Composable
internal fun ScreenStreamContent(
    updateFlow: StateFlow<((Boolean) -> Unit)?>,
    modifier: Modifier = Modifier,
    isLoggingOn: Boolean = AppLogger.isLoggingOn
) {
    if (isLoggingOn) {
        Column(modifier = modifier.fillMaxSize()) {
            CollectingLogsUi(modifier = Modifier.fillMaxWidth())
            MainContent(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1F)
            )
        }
    } else {
        MainContent(modifier = modifier.fillMaxSize())
    }

    val updateFlowState = updateFlow.collectAsStateWithLifecycle()
    if (updateFlowState.value != null) {
        AppUpdateRequestUI(
            onConfirmButtonClick = { updateFlowState.value?.invoke(true) },
            onDismissButtonClick = { updateFlowState.value?.invoke(false) }
        )
    }

    val activity = LocalActivity.current
    LaunchedEffect(Unit) { AppReview.showReviewUi(activity) }

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        NotificationPermission()
    }

    AccessibilitySetupWizard()
}

@Composable
private fun AccessibilitySetupWizard() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val showDialog = rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(1500)
        if (!InputService.isConnected()) {
            showDialog.value = true
        }
    }

    if (showDialog.value && !InputService.isConnected()) {
        val brand = android.os.Build.MANUFACTURER.lowercase()
        val brandHint = when {
            brand.contains("huawei") || brand.contains("honor") -> "\n\n💡 华为/荣耀手机：在列表中找到本应用，打开开关即可。"
            brand.contains("xiaomi") || brand.contains("redmi") -> "\n\n💡 小米手机：在\"已下载的服务\"中找到本应用，打开开关。"
            brand.contains("oppo") || brand.contains("oneplus") -> "\n\n💡 OPPO手机：在\"已下载的服务\"中找到本应用，打开开关。"
            brand.contains("vivo") -> "\n\n💡 vivo手机：在\"已下载的服务\"中找到本应用，打开开关。"
            else -> ""
        }

        androidx.compose.material3.AlertDialog(
            onDismissRequest = { showDialog.value = false },
            icon = {
                Text("🤝", style = MaterialTheme.typography.headlineLarge)
            },
            title = {
                Text(
                    text = "让家人能帮您操作",
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                    style = MaterialTheme.typography.titleLarge
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        text = "开启这个权限后，家人就能远程帮您点击屏幕上的按钮。",
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Text(
                        text = "👉 点击下面的\"去开启\"按钮\n👉 在列表中找到本应用\n👉 打开开关就行了",
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Text(
                        text = "⚠️ 手机可能会提示\"此服务可以监控您的操作\"——这是系统的标准说法，不用担心。只有您允许的家人才能操作，关掉APP就断开了。" + brandHint,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    try {
                        context.startActivity(
                            android.content.Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                        )
                    } catch (_: Exception) {}
                    showDialog.value = false
                }) {
                    Text("去开启", style = MaterialTheme.typography.titleMedium)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDialog.value = false }) {
                    Text("以后再说")
                }
            }
        )
    }
}

@Composable
private fun MainContent(
    modifier: Modifier = Modifier
) {
    val selectedTab = rememberSaveable { mutableStateOf(AppTabs.STREAM) }

    BackHandler(enabled = selectedTab.value != AppTabs.STREAM) { selectedTab.value = AppTabs.STREAM }

    val layoutType = with(currentWindowAdaptiveInfo()) {
        when {
            windowPosture.isTabletop -> NavigationSuiteType.NavigationBar
            windowSizeClass.isWidthAtLeastBreakpoint(WindowSizeClass.WIDTH_DP_MEDIUM_LOWER_BOUND) -> NavigationSuiteType.NavigationRail
            else -> NavigationSuiteType.NavigationBar
        }
    }

    val windowSize = currentWindowSize()
    val contentBoundsInWindow = remember(windowSize) { mutableStateOf(windowSize.toIntRect().toRect()) }

    Surface(
        modifier = modifier.windowInsetsPadding(WindowInsets.safeDrawing),
        color = NavigationSuiteScaffoldDefaults.containerColor,
        contentColor = NavigationSuiteScaffoldDefaults.contentColor
    ) {
        NavigationSuiteScaffoldLayout(
            navigationSuite = {
                when (layoutType) {
                    NavigationSuiteType.NavigationBar -> NavigationBar {
                        AppTabs.entries.forEach { tab ->
                            NavigationBarItem(
                                selected = selectedTab.value == tab,
                                onClick = dropUnlessStarted { selectedTab.value = tab },
                                icon = { Icon(imageVector = if (selectedTab.value == tab) tab.iconSelected else tab.icon, null) },
                                modifier = Modifier.padding(horizontal = 4.dp),
                                label = { Text(text = stringResource(tab.label)) },
                            )
                        }
                    }

                    NavigationSuiteType.NavigationRail -> NavigationRail {
                        Spacer(Modifier.weight(0.5f))
                        AppTabs.entries.forEach { tab ->
                            NavigationRailItem(
                                selected = selectedTab.value == tab,
                                onClick = dropUnlessStarted { selectedTab.value = tab },
                                icon = { Icon(imageVector = if (selectedTab.value == tab) tab.iconSelected else tab.icon, null) },
                                modifier = Modifier.padding(vertical = 4.dp),
                                label = { Text(text = stringResource(tab.label)) }
                            )
                        }
                        Spacer(Modifier.weight(1f))
                    }

                    else -> throw UnsupportedOperationException("Unsupported NavigationSuiteType: $layoutType")
                }
            },
            layoutType = layoutType
        ) {
            AnimatedContent(
                targetState = selectedTab.value,
                modifier = Modifier.onPlaced { contentBoundsInWindow.value = it.boundsInWindow() },
                transitionSpec = {
                    fadeIn(animationSpec = tween(300, delayMillis = 90, easing = EaseIn))
                        .togetherWith(fadeOut(animationSpec = tween(150, easing = EaseOut)))
                },
                label = "TabContent"
            ) { tab ->
                when (tab) {
                    AppTabs.STREAM -> StreamTabContent(contentBoundsInWindow.value, modifier = Modifier.fillMaxSize())
                    AppTabs.SETTINGS -> SettingsTabContent(contentBoundsInWindow.value, modifier = Modifier.fillMaxSize())
                    AppTabs.ABOUT -> AboutTabContent(modifier = Modifier.fillMaxSize())
                    AppTabs.EXIT -> ExitTabContent(modifier = Modifier.fillMaxSize())
                }
            }
        }
    }

    val view = LocalView.current
    if (view.isInEditMode.not()) {
        val statusBarColor = MaterialTheme.colorScheme.background

        val navigationBarColor = if (layoutType != NavigationSuiteType.NavigationBar) MaterialTheme.colorScheme.background
        else NavigationBarDefaults.containerColor

        SideEffect {
            (view.context as ComponentActivity).apply {
                enableEdgeToEdge(statusBarColor = statusBarColor, navigationBarColor = navigationBarColor)
                window.decorView.setBackgroundColor(statusBarColor.toArgb())
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppUpdateRequestUI(
    onConfirmButtonClick: () -> Unit,
    onDismissButtonClick: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismissButtonClick,
        shape = MaterialTheme.shapes.medium,
        dragHandle = null
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
        ) {
            Icon(painter = painterResource(R.drawable.ic_notification_small_24dp), contentDescription = null)
            Text(
                text = stringResource(id = R.string.app_activity_update_dialog_title),
                modifier = Modifier.padding(start = 16.dp, end = 16.dp + 24.dp),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.titleMedium
            )
        }
        Text(
            text = stringResource(id = R.string.app_activity_update_dialog_message),
            modifier = Modifier
                .padding(horizontal = 16.dp)
                .fillMaxWidth()
        )
        Row(
            modifier = Modifier
                .padding(end = 16.dp)
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
        ) {
            TextButton(
                onClick = onDismissButtonClick,
                modifier = Modifier.padding(end = 16.dp)
            ) {
                Text(text = stringResource(id = android.R.string.cancel))
            }
            TextButton(onClick = onConfirmButtonClick) {
                Text(text = stringResource(id = R.string.app_activity_update_dialog_restart))
            }
        }
    }
}

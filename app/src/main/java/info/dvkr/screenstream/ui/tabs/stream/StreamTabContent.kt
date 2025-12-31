package info.dvkr.screenstream.ui.tabs.stream

import android.Manifest
import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.window.core.layout.WindowSizeClass
import info.dvkr.screenstream.AdaptiveBanner
import info.dvkr.screenstream.R
import info.dvkr.screenstream.common.findActivity
import info.dvkr.screenstream.common.isPermissionGranted
import info.dvkr.screenstream.common.shouldShowPermissionRationale
import info.dvkr.screenstream.common.module.StreamingModule
import info.dvkr.screenstream.common.module.StreamingModuleManager
import info.dvkr.screenstream.common.settings.AppSettings
import info.dvkr.screenstream.common.ui.ExpandableCard
import kotlinx.coroutines.CoroutineScope

import kotlinx.coroutines.launch
import org.koin.compose.koinInject

@Composable
internal fun StreamTabContent(
    boundsInWindow: Rect,
    modifier: Modifier = Modifier,
    streamingModulesManager: StreamingModuleManager = koinInject()
) {
    val activeModuleState = streamingModulesManager.activeModuleStateFlow.collectAsStateWithLifecycle()
    val isStreaming = remember(activeModuleState.value) {
        activeModuleState.value?.isStreaming ?: kotlinx.coroutines.flow.flowOf(false)
    }.collectAsStateWithLifecycle(initialValue = false)

    Column(modifier = modifier) {
        val with = with(LocalDensity.current) { boundsInWindow.width.toDp() }
        if (with >= 800.dp) {
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1F), verticalArrangement = Arrangement.Center) {
                    StreamingModuleSelector(
                        streamingModulesManager = streamingModulesManager,
                        enabled = isStreaming.value.not(),
                        modifier = Modifier
                            .padding(top = 8.dp, start = 16.dp, end = 8.dp, bottom = 8.dp)
                            .fillMaxWidth()
                    )
                    AccessibilityShortcutCard(
                        modifier = Modifier
                            .padding(start = 16.dp, end = 8.dp, bottom = 8.dp)
                            .fillMaxWidth()
                    )
                    MicrophonePermissionCard(
                        modifier = Modifier
                            .padding(start = 16.dp, end = 8.dp, bottom = 8.dp)
                            .fillMaxWidth()
                    )
                }
                Column(modifier = Modifier.weight(1F)) {
                    AdaptiveBanner(modifier = Modifier.fillMaxWidth())
                }
            }
        } else {
            Column(modifier = Modifier.fillMaxWidth()) {
                StreamingModuleSelector(
                    streamingModulesManager = streamingModulesManager,
                    enabled = isStreaming.value.not(),
                    modifier = Modifier
                        .padding(top = 8.dp, start = 16.dp, end = 16.dp, bottom = 8.dp)
                        .fillMaxWidth()
                )
                AccessibilityShortcutCard(
                    modifier = Modifier
                        .padding(start = 16.dp, end = 16.dp, bottom = 8.dp)
                        .fillMaxWidth()
                )
                MicrophonePermissionCard(
                    modifier = Modifier
                        .padding(start = 16.dp, end = 16.dp, bottom = 8.dp)
                        .fillMaxWidth()
                )
                AdaptiveBanner(modifier = Modifier.fillMaxWidth())
            }
        }
        activeModuleState.value?.StreamUIContent(modifier = Modifier.fillMaxSize())
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AccessibilityShortcutCard(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    Card(
        modifier = modifier,
        onClick = {
            try {
                context.startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS))
            } catch (e: Exception) {
                // Ignore
            }
        }
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icon_Accessibility,
                contentDescription = null
            )
            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text("快速打开无障碍设置", style = MaterialTheme.typography.titleMedium)
                Text("点击此处去开启辅助功能权限", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MicrophonePermissionCard(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    if (context.isPermissionGranted(Manifest.permission.RECORD_AUDIO)) return

    val activity = remember(context) { context.findActivity() }
    val showRationaleDialog = rememberSaveable { mutableStateOf(false) }
    val showSettingsDialog = rememberSaveable { mutableStateOf(false) }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
        if (isGranted) {
            showRationaleDialog.value = false
            showSettingsDialog.value = false
        } else {
            val showRationale = activity.shouldShowPermissionRationale(Manifest.permission.RECORD_AUDIO)
            showRationaleDialog.value = showRationale
            showSettingsDialog.value = showRationale.not()
        }
    }

    Card(modifier = modifier, onClick = { launcher.launch(Manifest.permission.RECORD_AUDIO) }) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(imageVector = Icon_Microphone, contentDescription = null)
            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text("快速打开麦克风权限", style = MaterialTheme.typography.titleMedium)
                Text("用于采集/传输音频（VR里可一键开启）", style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    if (showRationaleDialog.value) {
        AlertDialog(
            onDismissRequest = {},
            confirmButton = {
                TextButton(
                    onClick = {
                        showRationaleDialog.value = false
                        launcher.launch(Manifest.permission.RECORD_AUDIO)
                    }
                ) { Text(text = stringResource(id = android.R.string.ok)) }
            },
            title = { Text(text = stringResource(id = R.string.app_permission_required_title)) },
            text = { Text(text = "需要麦克风权限才能采集/传输音频") },
            shape = MaterialTheme.shapes.large
        )
    }

    if (showSettingsDialog.value) {
        AlertDialog(
            onDismissRequest = {},
            confirmButton = {
                TextButton(
                    onClick = {
                        showSettingsDialog.value = false
                        runCatching {
                            val i = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                                addCategory(Intent.CATEGORY_DEFAULT)
                                data = "package:${context.packageName}".toUri()
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            }
                            context.startActivity(i)
                        }
                    }
                ) { Text(text = "去设置") }
            },
            title = { Text(text = stringResource(id = R.string.app_permission_required_title)) },
            text = { Text(text = "权限已被永久拒绝，请在系统设置中手动开启麦克风权限") },
            shape = MaterialTheme.shapes.large
        )
    }
}

@Composable
private fun StreamingModuleSelector(
    streamingModulesManager: StreamingModuleManager,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    scope: CoroutineScope = rememberCoroutineScope(),
) {
    val selectedModuleId = streamingModulesManager.selectedModuleIdFlow
        .collectAsStateWithLifecycle(initialValue = AppSettings.Default.STREAMING_MODULE)

    val adaptiveInfo = currentWindowAdaptiveInfo()

    ExpandableCard(
        headerContent = {
            Column(
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .padding(start = 48.dp),
            ) {
                Text(
                    text = stringResource(id = R.string.app_tab_stream_select_mode),
                    style = MaterialTheme.typography.titleMedium
                )
            }
        },
        modifier = modifier,
        contentModifier = Modifier.selectableGroup(),
        initiallyExpanded = adaptiveInfo.windowSizeClass.isHeightAtLeastBreakpoint(WindowSizeClass.HEIGHT_DP_MEDIUM_LOWER_BOUND)
    ) {
        streamingModulesManager.modules.forEach { module ->
            ModuleSelectorRow(
                module = module,
                selectedModuleId = selectedModuleId.value,
                enabled = enabled,
                onModuleSelect = { moduleId -> scope.launch { streamingModulesManager.selectStreamingModule(moduleId) } },
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
private fun ModuleSelectorRow(
    module: StreamingModule,
    selectedModuleId: StreamingModule.Id,
    onModuleSelect: (StreamingModule.Id) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean
) {
    Row(
        modifier = modifier.selectable(
            selected = module.id == selectedModuleId,
            onClick = { onModuleSelect.invoke(module.id) },
            role = Role.RadioButton,
            enabled = enabled
        ),
        verticalAlignment = Alignment.CenterVertically
    ) {
        val openDescriptionDialog = rememberSaveable { mutableStateOf(false) }

        RadioButton(
            selected = module.id == selectedModuleId,
            onClick = null,
            modifier = Modifier.padding(start = 8.dp),
            enabled = enabled
        )

        Text(
            text = stringResource(id = module.nameResource),
            modifier = Modifier
                .padding(start = 16.dp)
                .weight(1F),
            style = MaterialTheme.typography.titleMedium
        )

        IconButton(onClick = { openDescriptionDialog.value = true }) {
            Icon(
                imageVector = Icon_HelpOutline,
                contentDescription = stringResource(id = module.descriptionResource),
                tint = MaterialTheme.colorScheme.primary
            )
        }

        if (openDescriptionDialog.value) {
            AlertDialog(
                onDismissRequest = { openDescriptionDialog.value = false },
                confirmButton = {
                    TextButton(onClick = { openDescriptionDialog.value = false }) {
                        Text(text = stringResource(id = android.R.string.ok))
                    }
                },
                title = {
                    Text(
                        text = stringResource(id = module.nameResource),
                        modifier = Modifier.fillMaxWidth(),
                        textAlign = TextAlign.Center
                    )
                },
                text = {
                    Text(
                        text = stringResource(id = module.detailsResource),
                        modifier = Modifier.verticalScroll(rememberScrollState())
                    )
                },
                shape = MaterialTheme.shapes.large
            )
        }
    }
}

private val Icon_HelpOutline: ImageVector = materialIcon(name = "AutoMirrored.Outlined.HelpOutline", autoMirror = true) {
    materialPath {
        moveTo(11.0f, 18.0f)
        horizontalLineToRelative(2.0f)
        verticalLineToRelative(-2.0f)
        horizontalLineToRelative(-2.0f)
        verticalLineToRelative(2.0f)
        close()
        moveTo(12.0f, 2.0f)
        curveTo(6.48f, 2.0f, 2.0f, 6.48f, 2.0f, 12.0f)
        reflectiveCurveToRelative(4.48f, 10.0f, 10.0f, 10.0f)
        reflectiveCurveToRelative(10.0f, -4.48f, 10.0f, -10.0f)
        reflectiveCurveTo(17.52f, 2.0f, 12.0f, 2.0f)
        close()
        moveTo(12.0f, 20.0f)
        curveToRelative(-4.41f, 0.0f, -8.0f, -3.59f, -8.0f, -8.0f)
        reflectiveCurveToRelative(3.59f, -8.0f, 8.0f, -8.0f)
        reflectiveCurveToRelative(8.0f, 3.59f, 8.0f, 8.0f)
        reflectiveCurveToRelative(-3.59f, 8.0f, -8.0f, 8.0f)
        close()
        moveTo(12.0f, 6.0f)
        curveToRelative(-2.21f, 0.0f, -4.0f, 1.79f, -4.0f, 4.0f)
        horizontalLineToRelative(2.0f)
        curveToRelative(0.0f, -1.1f, 0.9f, -2.0f, 2.0f, -2.0f)
        reflectiveCurveToRelative(2.0f, 0.9f, 2.0f, 2.0f)
        curveToRelative(0.0f, 2.0f, -3.0f, 1.75f, -3.0f, 5.0f)
        horizontalLineToRelative(2.0f)
        curveToRelative(0.0f, -2.25f, 3.0f, -2.5f, 3.0f, -5.0f)
        curveToRelative(0.0f, -2.21f, -1.79f, -4.0f, -4.0f, -4.0f)
        close()
    }
}

private val Icon_Microphone: ImageVector = materialIcon(name = "Filled.Mic") {
    materialPath {
        moveTo(12.0f, 14.0f)
        curveToRelative(1.66f, 0.0f, 3.0f, -1.34f, 3.0f, -3.0f)
        verticalLineTo(5.0f)
        curveToRelative(0.0f, -1.66f, -1.34f, -3.0f, -3.0f, -3.0f)
        reflectiveCurveToRelative(-3.0f, 1.34f, -3.0f, 3.0f)
        verticalLineToRelative(6.0f)
        curveToRelative(0.0f, 1.66f, 1.34f, 3.0f, 3.0f, 3.0f)
        close()

        moveTo(17.3f, 11.0f)
        curveToRelative(0.0f, 3.0f, -2.54f, 5.1f, -5.3f, 5.1f)
        reflectiveCurveTo(6.7f, 14.0f, 6.7f, 11.0f)
        horizontalLineToRelative(-1.7f)
        curveToRelative(0.0f, 3.41f, 2.72f, 6.23f, 6.0f, 6.72f)
        verticalLineTo(21.0f)
        horizontalLineToRelative(2.0f)
        verticalLineToRelative(-3.28f)
        curveToRelative(3.28f, -0.49f, 6.0f, -3.31f, 6.0f, -6.72f)
        horizontalLineToRelative(-1.7f)
        close()
    }
}

private val Icon_Accessibility: ImageVector = materialIcon(name = "Filled.Accessibility") {
    materialPath {
        moveTo(12.0f, 2.0f)
        curveToRelative(1.1f, 0.0f, 2.0f, 0.9f, 2.0f, 2.0f)
        reflectiveCurveToRelative(-0.9f, 2.0f, -2.0f, 2.0f)
        reflectiveCurveToRelative(-2.0f, -0.9f, -2.0f, -2.0f)
        reflectiveCurveToRelative(0.9f, -2.0f, 2.0f, -2.0f)
        close()
        moveTo(21.0f, 9.0f)
        horizontalLineToRelative(-6.0f)
        verticalLineToRelative(13.0f)
        horizontalLineToRelative(-2.0f)
        verticalLineToRelative(-6.0f)
        horizontalLineToRelative(-2.0f)
        verticalLineToRelative(6.0f)
        horizontalLineTo(9.0f)
        verticalLineTo(9.0f)
        horizontalLineTo(3.0f)
        verticalLineTo(7.0f)
        horizontalLineToRelative(18.0f)
        verticalLineToRelative(2.0f)
        close()
    }
}
package info.dvkr.screenstream.input.ui.settings

import android.content.Context
import android.content.Intent
import android.content.res.Resources
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import info.dvkr.screenstream.common.ModuleSettings
import info.dvkr.screenstream.input.InputService
import info.dvkr.screenstream.input.R
import info.dvkr.screenstream.input.settings.InputSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.koin.compose.koinInject

internal object InputGeneralGroup : ModuleSettings.Group {
    override val id: String = "INPUT_GENERAL"
    override val position: Int = 0
    override val items: List<ModuleSettings.Item> = listOf(
        AccessibilityItem,
        EnableInputItem,
        AutoStartHttpItem
    ).sortedBy { it.position }

    @Composable
    override fun TitleUI(modifier: Modifier) {
        Text(
            text = stringResource(R.string.input_module_title),
            modifier = modifier,
            style = MaterialTheme.typography.titleSmall
        )
    }
}

internal object AccessibilityItem : ModuleSettings.Item {
    override val id: String = "INPUT_ACCESSIBILITY"
    override val position: Int = 0
    override val available: Boolean = true

    override fun has(resources: Resources, text: String): Boolean {
        return resources.getString(R.string.input_enable_accessibility).contains(text, ignoreCase = true)
    }

    @Composable
    override fun ItemUI(horizontalPadding: Dp, coroutineScope: CoroutineScope, onDetailShow: () -> Unit) {
        val context = LocalContext.current
        val isConnected = InputService.isConnected()
        
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = horizontalPadding, vertical = 4.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isConnected)
                    MaterialTheme.colorScheme.primaryContainer
                else
                    MaterialTheme.colorScheme.errorContainer
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Icon(
                        imageVector = if (isConnected) Icons.Default.Check else Icons.Default.Close,
                        contentDescription = null
                    )
                    Column {
                        Text(
                            text = if (isConnected) "Accessibility Enabled" else "Accessibility Required",
                            style = MaterialTheme.typography.bodyLarge
                        )
                        if (!isConnected) {
                            Text(
                                text = stringResource(R.string.input_accessibility_not_enabled),
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
                
                if (!isConnected) {
                    FilledTonalButton(
                        onClick = { openAccessibilitySettings(context) }
                    ) {
                        Icon(Icons.Default.Settings, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text(stringResource(R.string.input_enable_accessibility))
                    }
                }
            }
        }
    }
}

internal object EnableInputItem : ModuleSettings.Item {
    override val id: String = "INPUT_ENABLE"
    override val position: Int = 1
    override val available: Boolean = true

    override fun has(resources: Resources, text: String): Boolean {
        return "Remote Control".contains(text, ignoreCase = true)
    }

    @Composable
    override fun ItemUI(horizontalPadding: Dp, coroutineScope: CoroutineScope, onDetailShow: () -> Unit) {
        val inputSettings: InputSettings = koinInject()
        val settings by inputSettings.data.collectAsState()
        
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = horizontalPadding, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Icon(Icons.Default.Phone, contentDescription = null)
                Text("Enable Remote Control")
            }
            Switch(
                checked = settings.inputEnabled,
                onCheckedChange = { enabled ->
                    coroutineScope.launch {
                        inputSettings.updateData { copy(inputEnabled = enabled) }
                    }
                }
            )
        }
    }
}

internal object AutoStartHttpItem : ModuleSettings.Item {
    override val id: String = "INPUT_AUTO_START"
    override val position: Int = 2
    override val available: Boolean = true

    override fun has(resources: Resources, text: String): Boolean {
        return "HTTP Server".contains(text, ignoreCase = true)
    }

    @Composable
    override fun ItemUI(horizontalPadding: Dp, coroutineScope: CoroutineScope, onDetailShow: () -> Unit) {
        val inputSettings: InputSettings = koinInject()
        val settings by inputSettings.data.collectAsState()
        
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = horizontalPadding, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text("Auto Start HTTP Server")
                Text(
                    text = stringResource(R.string.input_server_running, settings.apiPort),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Switch(
                checked = settings.autoStartHttp,
                onCheckedChange = { enabled ->
                    coroutineScope.launch {
                        inputSettings.updateData { copy(autoStartHttp = enabled) }
                    }
                }
            )
        }
    }
}

private fun openAccessibilitySettings(context: Context) {
    val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
    intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
    context.startActivity(intent)
}

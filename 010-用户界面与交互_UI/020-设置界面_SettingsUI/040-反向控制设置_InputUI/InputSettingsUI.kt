package info.dvkr.screenstream.input.ui

import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import info.dvkr.screenstream.input.InputService
import info.dvkr.screenstream.input.R
import info.dvkr.screenstream.input.settings.InputSettings
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

@Composable
public fun InputSettingsUI(
    settingsFlow: StateFlow<InputSettings.Data>,
    onUpdateSettings: suspend (InputSettings.Data.() -> InputSettings.Data) -> Unit,
    modifier: Modifier = Modifier
) {
    val settings by settingsFlow.collectAsState()
    val context = LocalContext.current
    val isAccessibilityEnabled = InputService.isConnected()
    
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Accessibility Status Card
        AccessibilityStatusCard(
            isEnabled = isAccessibilityEnabled,
            onEnableClick = { openAccessibilitySettings(context) }
        )
        
        // Input Control Settings
        if (isAccessibilityEnabled) {
            InputControlSettings(
                settings = settings,
                onUpdateSettings = onUpdateSettings
            )
        }
    }
}

@Composable
private fun AccessibilityStatusCard(
    isEnabled: Boolean,
    onEnableClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isEnabled) 
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
                    imageVector = if (isEnabled) Icons.Default.Check else Icons.Default.Close,
                    contentDescription = null,
                    tint = if (isEnabled) 
                        MaterialTheme.colorScheme.onPrimaryContainer 
                    else 
                        MaterialTheme.colorScheme.onErrorContainer
                )
                Column {
                    Text(
                        text = if (isEnabled) "Accessibility Enabled" else "Accessibility Required",
                        style = MaterialTheme.typography.titleMedium,
                        color = if (isEnabled) 
                            MaterialTheme.colorScheme.onPrimaryContainer 
                        else 
                            MaterialTheme.colorScheme.onErrorContainer
                    )
                    if (!isEnabled) {
                        Text(
                            text = stringResource(R.string.input_accessibility_not_enabled),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }
            
            if (!isEnabled) {
                FilledTonalButton(onClick = onEnableClick) {
                    Icon(Icons.Default.Settings, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text(stringResource(R.string.input_enable_accessibility))
                }
            }
        }
    }
}

@Composable
private fun InputControlSettings(
    settings: InputSettings.Data,
    onUpdateSettings: suspend (InputSettings.Data.() -> InputSettings.Data) -> Unit
) {
    val scope = rememberCoroutineScope()
    
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = stringResource(R.string.input_module_title),
                style = MaterialTheme.typography.titleMedium
            )
            
            // Input Enabled Switch
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Enable Remote Control")
                Switch(
                    checked = settings.inputEnabled,
                    onCheckedChange = { enabled ->
                        scope.launch {
                            onUpdateSettings { copy(inputEnabled = enabled) }
                        }
                    }
                )
            }
            
            HorizontalDivider()
            
            // API Port
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(stringResource(R.string.input_server_port))
                Text(
                    text = settings.apiPort.toString(),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            
            // Server Status
            Text(
                text = stringResource(R.string.input_server_running, settings.apiPort),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            // Auto Start HTTP
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Auto Start HTTP Server")
                Switch(
                    checked = settings.autoStartHttp,
                    onCheckedChange = { enabled ->
                        scope.launch {
                            onUpdateSettings { copy(autoStartHttp = enabled) }
                        }
                    }
                )
            }
        }
    }
}

private fun openAccessibilitySettings(context: Context) {
    val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
    intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
    context.startActivity(intent)
}

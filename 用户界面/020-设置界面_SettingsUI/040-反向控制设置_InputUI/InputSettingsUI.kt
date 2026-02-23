package info.dvkr.screenstream.input.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.widget.Toast
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import info.dvkr.screenstream.input.InputService
import info.dvkr.screenstream.input.R
import info.dvkr.screenstream.input.settings.InputSettings
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File

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

            // Remote Access Token Management
            RemoteAccessCard(context = context, serverPort = settings.apiPort)
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

@Composable
private fun RemoteAccessCard(context: Context, serverPort: Int) {
    val tokenFile = remember { File(context.filesDir, "remote_auth_token") }
    var currentToken by remember { mutableStateOf(readTokenFile(tokenFile)) }
    var showToken by remember { mutableStateOf(false) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Remote Access",
                style = MaterialTheme.typography.titleMedium
            )

            Text(
                text = "Enable token authentication for public internet access",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            // Enable/Disable Toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Auth Token Enabled")
                Switch(
                    checked = currentToken.isNotEmpty(),
                    onCheckedChange = { enabled ->
                        if (enabled) {
                            val newToken = generateRandomToken(16)
                            writeTokenFile(tokenFile, newToken)
                            currentToken = newToken
                        } else {
                            writeTokenFile(tokenFile, "")
                            currentToken = ""
                            showToken = false
                        }
                    }
                )
            }

            if (currentToken.isNotEmpty()) {
                HorizontalDivider()

                // Token Display
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Current Token", style = MaterialTheme.typography.labelMedium)
                        Text(
                            text = if (showToken) currentToken else "••••••••••••••••",
                            style = MaterialTheme.typography.bodyMedium,
                            fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    TextButton(onClick = { showToken = !showToken }) {
                        Text(if (showToken) "Hide" else "Show")
                    }
                }

                // Action Buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedButton(
                        onClick = {
                            copyToClipboard(context, "ScreenStream Token", currentToken)
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Copy Token")
                    }
                    OutlinedButton(
                        onClick = {
                            val newToken = generateRandomToken(16)
                            writeTokenFile(tokenFile, newToken)
                            currentToken = newToken
                            copyToClipboard(context, "ScreenStream Token", newToken)
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Regenerate")
                    }
                }

                // Shareable URL hint
                Text(
                    text = "Share: https://<tunnel-domain>/?auth=$currentToken",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                OutlinedButton(
                    onClick = {
                        copyToClipboard(context, "ScreenStream URL", "?auth=$currentToken")
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Copy Auth URL Suffix")
                }
            }
        }
    }
}

private fun readTokenFile(file: File): String {
    return try { if (file.exists()) file.readText().trim() else "" } catch (_: Exception) { "" }
}

private fun writeTokenFile(file: File, token: String) {
    try {
        if (token.isEmpty()) { if (file.exists()) file.delete() }
        else file.writeText(token)
    } catch (_: Exception) {}
}

private fun generateRandomToken(length: Int): String {
    val chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return (1..length).map { chars.random() }.joinToString("")
}

private fun copyToClipboard(context: Context, label: String, text: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText(label, text))
    Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
}

private fun openAccessibilitySettings(context: Context) {
    val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
    intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
    context.startActivity(intent)
}

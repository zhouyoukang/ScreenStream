package info.dvkr.screenstream.ui.tabs.settings.app.settings.general

import android.content.Context
import android.content.res.Resources
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import info.dvkr.screenstream.common.ModuleSettings
import kotlinx.coroutines.CoroutineScope

internal object StartOnBoot : ModuleSettings.Item {
    override val id: String = "START_ON_BOOT"
    override val position: Int = 5
    override val available: Boolean = true

    override fun has(resources: Resources, text: String): Boolean =
        "Start on Boot".contains(text, ignoreCase = true) ||
                "开机自启".contains(text, ignoreCase = true)

    @Composable
    override fun ItemUI(horizontalPadding: Dp, coroutineScope: CoroutineScope, onDetailShow: () -> Unit) {
        val context = LocalContext.current
        val prefs = remember { context.getSharedPreferences("screenstream_boot", Context.MODE_PRIVATE) }
        var checked by remember { mutableStateOf(prefs.getBoolean("start_on_boot", false)) }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = horizontalPadding + 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.PlayArrow,
                contentDescription = null,
                modifier = Modifier.padding(end = 16.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Start on Boot",
                    modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
                    fontSize = 18.sp,
                    style = MaterialTheme.typography.bodyLarge
                )
                Text(
                    text = "Auto-launch ScreenStream when device boots",
                    modifier = Modifier.padding(top = 2.dp, bottom = 8.dp),
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            Switch(
                checked = checked,
                onCheckedChange = { enabled ->
                    prefs.edit().putBoolean("start_on_boot", enabled).apply()
                    checked = enabled
                }
            )
        }
    }
}

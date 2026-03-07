package info.dvkr.screenstream.mjpeg.ui.settings.general

import android.content.res.Resources
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.minimumInteractiveComponentSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import info.dvkr.screenstream.common.ModuleSettings
import info.dvkr.screenstream.mjpeg.R
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.koin.compose.koinInject

internal object StreamCodec : ModuleSettings.Item {
    override val id: String = MjpegSettings.Key.STREAM_CODEC.name
    override val position: Int = -1
    override val available: Boolean = true

    override fun has(resources: Resources, text: String): Boolean = with(resources) {
        getString(R.string.mjpeg_pref_stream_codec).contains(text, ignoreCase = true) ||
            getString(R.string.mjpeg_pref_stream_codec_summary).contains(text, ignoreCase = true)
    }

    @Composable
    override fun ItemUI(horizontalPadding: Dp, coroutineScope: CoroutineScope, onDetailShow: () -> Unit) {
        val mjpegSettings = koinInject<MjpegSettings>()
        val mjpegSettingsState = mjpegSettings.data.collectAsStateWithLifecycle()
        StreamCodecUI(horizontalPadding, mjpegSettingsState.value.streamCodec, onDetailShow)
    }

    @Composable
    override fun DetailUI(headerContent: @Composable (String) -> Unit) {
        val mjpegSettings = koinInject<MjpegSettings>()
        val mjpegSettingsState = mjpegSettings.data.collectAsStateWithLifecycle()
        val scope = rememberCoroutineScope()
        val options = stringArrayResource(id = R.array.mjpeg_pref_stream_codec_options)
        val currentIndex = codecList.first { it.second == mjpegSettingsState.value.streamCodec }.first

        StreamCodecDetailUI(headerContent, options, currentIndex) { index ->
            val newCodec = codecList[index].second
            if (mjpegSettingsState.value.streamCodec != newCodec) {
                scope.launch { mjpegSettings.updateData { copy(streamCodec = newCodec) } }
            }
        }
    }

    private val codecList = listOf(
        0 to MjpegSettings.Values.STREAM_CODEC_MJPEG,
        1 to MjpegSettings.Values.STREAM_CODEC_H264,
        2 to MjpegSettings.Values.STREAM_CODEC_H265
    )
}

@Composable
private fun StreamCodecUI(
    horizontalPadding: Dp,
    streamCodec: Int,
    onDetailShow: () -> Unit,
) {
    Row(
        modifier = Modifier
            .clickable(role = Role.Button, onClick = onDetailShow)
            .padding(start = horizontalPadding + 16.dp, end = horizontalPadding + 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(imageVector = Icon_VideoSettings, contentDescription = null, modifier = Modifier.padding(end = 16.dp))

        Column(modifier = Modifier.weight(1F)) {
            Text(
                text = stringResource(id = R.string.mjpeg_pref_stream_codec),
                modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
                fontSize = 18.sp,
                style = MaterialTheme.typography.bodyLarge
            )
            Text(
                text = stringResource(id = R.string.mjpeg_pref_stream_codec_summary),
                modifier = Modifier.padding(top = 2.dp, bottom = 8.dp),
                style = MaterialTheme.typography.bodyMedium
            )
        }

        val valueText = when (streamCodec) {
            MjpegSettings.Values.STREAM_CODEC_H264 -> "H.264"
            MjpegSettings.Values.STREAM_CODEC_H265 -> "H.265"
            else -> "MJPEG"
        }

        Text(
            text = valueText,
            modifier = Modifier.defaultMinSize(minWidth = 52.dp),
            color = MaterialTheme.colorScheme.primary,
            textAlign = TextAlign.Center,
            maxLines = 1
        )
    }
}

@Composable
private fun StreamCodecDetailUI(
    headerContent: @Composable (String) -> Unit,
    options: Array<String>,
    selectedIndex: Int,
    onNewOptionIndex: (Int) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        headerContent.invoke(stringResource(id = R.string.mjpeg_pref_stream_codec))

        Column(
            modifier = Modifier
                .widthIn(max = 480.dp)
                .padding(horizontal = 24.dp, vertical = 8.dp)
                .selectableGroup()
                .verticalScroll(rememberScrollState())
        ) {
            options.forEachIndexed { index, text ->
                Row(
                    modifier = Modifier
                        .selectable(
                            selected = selectedIndex == index,
                            onClick = { onNewOptionIndex.invoke(index) },
                            role = Role.RadioButton
                        )
                        .fillMaxWidth()
                        .defaultMinSize(minHeight = 48.dp)
                        .minimumInteractiveComponentSize(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    RadioButton(selected = selectedIndex == index, onClick = null)
                    Text(text = text, modifier = Modifier.padding(start = 16.dp))
                }
            }
        }
    }
}

private val Icon_VideoSettings: ImageVector = materialIcon(name = "Filled.VideoSettings") {
    materialPath {
        moveTo(3.0f, 6.0f)
        horizontalLineToRelative(14.0f)
        verticalLineToRelative(12.0f)
        horizontalLineTo(3.0f)
        close()
        moveTo(21.0f, 7.0f)
        verticalLineToRelative(10.0f)
        lineToRelative(-4.0f, -3.0f)
        verticalLineToRelative(-4.0f)
        close()
    }
}

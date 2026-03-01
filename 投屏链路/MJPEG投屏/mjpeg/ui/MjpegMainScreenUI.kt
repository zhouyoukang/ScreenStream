package info.dvkr.screenstream.mjpeg.ui

import androidx.compose.animation.Crossfade
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.staggeredgrid.LazyVerticalStaggeredGrid
import androidx.compose.foundation.lazy.staggeredgrid.StaggeredGridCells
import androidx.compose.foundation.lazy.staggeredgrid.rememberLazyStaggeredGridState
import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.dropUnlessStarted
import info.dvkr.screenstream.common.ui.DoubleClickProtection
import info.dvkr.screenstream.common.ui.MediaProjectionPermission
import info.dvkr.screenstream.common.ui.get
import info.dvkr.screenstream.mjpeg.R
import info.dvkr.screenstream.mjpeg.internal.MjpegEvent
import info.dvkr.screenstream.mjpeg.internal.MjpegStreamingService
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.ElevatedCard
import androidx.compose.runtime.State
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import info.dvkr.screenstream.mjpeg.ui.main.ClientsCard
import info.dvkr.screenstream.mjpeg.ui.main.ErrorCard
import info.dvkr.screenstream.mjpeg.ui.main.InterfacesCard
import info.dvkr.screenstream.mjpeg.ui.main.PinCard
import info.dvkr.screenstream.mjpeg.ui.main.TrafficCard
import kotlinx.coroutines.flow.StateFlow

@Composable
internal fun MjpegMainScreenUI(
    mjpegStateFlow: StateFlow<MjpegState>,
    sendEvent: (event: MjpegEvent) -> Unit,
    modifier: Modifier = Modifier
) {
    val mjpegState = mjpegStateFlow.collectAsStateWithLifecycle()
    val context = LocalContext.current

    val permissionLauncher = rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted || androidx.core.content.ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.RECORD_AUDIO
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            // Permission granted or already granted
        }
        // Always start stream, even if audio permission denied (audio will just be silent)
        sendEvent(MjpegStreamingService.InternalEvent.StartStream)
    }

    BoxWithConstraints(modifier = modifier) {
        MediaProjectionPermission(
            shouldRequestPermission = mjpegState.value.waitingCastPermission,
            onPermissionGranted = { intent -> if (mjpegState.value.waitingCastPermission) sendEvent(MjpegEvent.StartProjection(intent)) },
            onPermissionDenied = { if (mjpegState.value.waitingCastPermission) sendEvent(MjpegEvent.CastPermissionsDenied) },
            requiredDialogTitle = stringResource(id = R.string.mjpeg_stream_cast_permission_required_title),
            requiredDialogText = stringResource(id = R.string.mjpeg_stream_cast_permission_required)
        )

        val lazyVerticalStaggeredGridState = rememberLazyStaggeredGridState()
        LazyVerticalStaggeredGrid(
            columns = StaggeredGridCells.Fixed(if (this.maxWidth >= 800.dp) 2 else 1),
            modifier = Modifier.fillMaxSize(),
            state = lazyVerticalStaggeredGridState,
            contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 64.dp),
        ) {
            mjpegState.value.error?.let {
                item(key = "ERROR") {
                    ErrorCard(error = it, modifier = Modifier.padding(8.dp), sendEvent = sendEvent)
                }
            }

            if (mjpegState.value.isStreaming && mjpegState.value.cloudRelayRoomCode.isNotEmpty()) {
                item(key = "CLOUD_RELAY") {
                    CloudRelayCard(mjpegState = mjpegState, modifier = Modifier.padding(8.dp))
                }
            }

            item(key = "INTERFACES") {
                InterfacesCard(mjpegState = mjpegState, modifier = Modifier.padding(8.dp))
            }

            item(key = "PIN") { //TODO notify user that this will disconnect all clients
                PinCard(mjpegState = mjpegState, onCreateNewPin = { sendEvent(MjpegEvent.CreateNewPin) }, modifier = Modifier.padding(8.dp))
            }

            item(key = "TRAFFIC") {
                TrafficCard(mjpegState = mjpegState, modifier = Modifier.padding(8.dp))
            }

            item(key = "CLIENTS") {
                ClientsCard(mjpegState = mjpegState, modifier = Modifier.padding(8.dp))
            }
        }

        LaunchedEffect(mjpegState.value.error) {
            if (mjpegState.value.error != null) lazyVerticalStaggeredGridState.animateScrollToItem(0)
        }

        val doubleClickProtection = remember { DoubleClickProtection.get() }

        Button(
            onClick = dropUnlessStarted {
                doubleClickProtection.processClick {
                    if (mjpegState.value.isStreaming) {
                        sendEvent(MjpegEvent.Intentable.StopStream("User action: Button"))
                    } else {
                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                            if (androidx.core.content.ContextCompat.checkSelfPermission(
                                    context,
                                    android.Manifest.permission.RECORD_AUDIO
                                ) != android.content.pm.PackageManager.PERMISSION_GRANTED
                            ) {
                                permissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
                            } else {
                                sendEvent(MjpegStreamingService.InternalEvent.StartStream)
                            }
                        } else {
                            sendEvent(MjpegStreamingService.InternalEvent.StartStream)
                        }
                    }
                }
            },
            modifier = Modifier
                .padding(start = 16.dp, end = 16.dp, bottom = 8.dp)
                .align(alignment = Alignment.BottomCenter),
            enabled = mjpegState.value.isBusy.not(),
            shape = MaterialTheme.shapes.medium,
            contentPadding = PaddingValues(start = 12.dp, top = 12.dp, bottom = 12.dp, end = 16.dp),
            elevation = ButtonDefaults.buttonElevation(
                defaultElevation = 3.0.dp,
                pressedElevation = 3.0.dp,
                focusedElevation = 3.0.dp,
                hoveredElevation = 6.0.dp
            )
        ) {
            Crossfade(targetState = mjpegState.value.isStreaming, label = "StreamingButtonCrossfade") { isStreaming ->
                Icon(imageVector = if (isStreaming) Icon_Stop else Icon_PlayArrow, contentDescription = null)
            }
            Spacer(modifier = Modifier.size(ButtonDefaults.IconSpacing))
            Text(
                text = stringResource(id = if (mjpegState.value.isStreaming) R.string.mjpeg_stream_stop else R.string.mjpeg_stream_start),
                style = MaterialTheme.typography.titleMedium
            )
        }
    }
}

@Composable
private fun CloudRelayCard(
    mjpegState: State<MjpegState>,
    modifier: Modifier = Modifier
) {
    ElevatedCard(modifier = modifier) {
        Column(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "📱 把这个数字告诉家人",
                style = MaterialTheme.typography.titleMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )

            Text(
                text = mjpegState.value.cloudRelayRoomCode,
                fontSize = 48.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                textAlign = TextAlign.Center,
                letterSpacing = 8.sp,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.fillMaxWidth()
            )

            if (mjpegState.value.cloudRelayConnected) {
                Text(
                    text = if (mjpegState.value.cloudRelayViewerCount > 0)
                        "✅ 家人已连接（${mjpegState.value.cloudRelayViewerCount}人在看）"
                    else
                        "🟢 已就绪，等待家人连接...",
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.primary
                )
            } else {
                Text(
                    text = "正在连接服务器...",
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            if (mjpegState.value.cloudRelayViewerUrl.isNotEmpty()) {
                Text(
                    text = "家人打开: aiotvr.xyz/cast",
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

private val Icon_Stop: ImageVector = materialIcon(name = "Filled.Stop") {
    materialPath {
        moveTo(6.0f, 6.0f)
        horizontalLineToRelative(12.0f)
        verticalLineToRelative(12.0f)
        horizontalLineTo(6.0f)
        close()
    }
}

private val Icon_PlayArrow: ImageVector = materialIcon(name = "Filled.PlayArrow") {
    materialPath {
        moveTo(8.0f, 5.0f)
        verticalLineToRelative(14.0f)
        lineToRelative(11.0f, -7.0f)
        close()
    }
}

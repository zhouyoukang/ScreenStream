package info.dvkr.screenstream.input.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.sp
import info.dvkr.screenstream.common.ModuleSettings
import info.dvkr.screenstream.input.R
import info.dvkr.screenstream.input.ui.settings.InputGeneralGroup

internal object InputModuleSettings : ModuleSettings {
    override val id: String = "INPUT"
    override val groups: List<ModuleSettings.Group> =
        listOf(InputGeneralGroup).sortedBy { it.position }

    @Composable
    override fun TitleUI(modifier: Modifier) {
        Text(
            text = stringResource(id = R.string.input_module_title),
            modifier = modifier,
            fontSize = 18.sp,
            style = MaterialTheme.typography.titleMedium
        )
    }
}

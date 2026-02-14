package info.dvkr.screenstream.input.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.core.handlers.ReplaceFileCorruptionHandler
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.preferencesDataStoreFile
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.withContext
import java.io.IOException

internal class InputSettingsImpl(context: Context) : InputSettings {

    private val dataStore: DataStore<Preferences> = PreferenceDataStoreFactory.create(
        corruptionHandler = ReplaceFileCorruptionHandler { ex -> XLog.e(ex); emptyPreferences() },
        produceFile = { context.preferencesDataStoreFile("INPUT_settings") }
    )

    override val data: StateFlow<InputSettings.Data> = dataStore.data
        .map { preferences -> preferences.toInputSettings() }
        .catch { cause ->
            XLog.e(this@InputSettingsImpl.getLog("getCatching"), cause)
            if (cause is IOException) emit(InputSettings.Data()) else throw cause
        }
        .stateIn(
            CoroutineScope(Dispatchers.IO),
            SharingStarted.WhileSubscribed(stopTimeoutMillis = 5000),
            InputSettings.Data()
        )

    override suspend fun updateData(transform: InputSettings.Data.() -> InputSettings.Data) = withContext(NonCancellable + Dispatchers.IO) {
        dataStore.edit { preferences ->
            val newSettings = transform.invoke(preferences.toInputSettings())

            preferences.apply {
                clear()

                if (newSettings.inputEnabled != InputSettings.Default.INPUT_ENABLED)
                    set(InputSettings.Key.INPUT_ENABLED, newSettings.inputEnabled)

                if (newSettings.apiPort != InputSettings.Default.API_PORT)
                    set(InputSettings.Key.API_PORT, newSettings.apiPort)

                if (newSettings.scalingFactor != InputSettings.Default.SCALING_FACTOR)
                    set(InputSettings.Key.SCALING_FACTOR, newSettings.scalingFactor)

                if (newSettings.autoStartHttp != InputSettings.Default.AUTO_START_HTTP)
                    set(InputSettings.Key.AUTO_START_HTTP, newSettings.autoStartHttp)

                if (newSettings.requirePin != InputSettings.Default.REQUIRE_PIN)
                    set(InputSettings.Key.REQUIRE_PIN, newSettings.requirePin)

                if (newSettings.pin != InputSettings.Default.PIN)
                    set(InputSettings.Key.PIN, newSettings.pin)
            }
        }
        Unit
    }

    private fun Preferences.toInputSettings(): InputSettings.Data = InputSettings.Data(
        inputEnabled = this[InputSettings.Key.INPUT_ENABLED] ?: InputSettings.Default.INPUT_ENABLED,
        apiPort = this[InputSettings.Key.API_PORT] ?: InputSettings.Default.API_PORT,
        scalingFactor = this[InputSettings.Key.SCALING_FACTOR] ?: InputSettings.Default.SCALING_FACTOR,
        autoStartHttp = this[InputSettings.Key.AUTO_START_HTTP] ?: InputSettings.Default.AUTO_START_HTTP,
        requirePin = this[InputSettings.Key.REQUIRE_PIN] ?: InputSettings.Default.REQUIRE_PIN,
        pin = this[InputSettings.Key.PIN] ?: InputSettings.Default.PIN,
    )
}

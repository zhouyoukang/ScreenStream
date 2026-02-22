package info.dvkr.screenstream.input.settings

import androidx.compose.runtime.Immutable
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import kotlinx.coroutines.flow.StateFlow

/**
 * Settings interface for Input module
 */
public interface InputSettings {

    public object Key {
        public val INPUT_ENABLED: Preferences.Key<Boolean> = booleanPreferencesKey("INPUT_ENABLED")
        public val API_PORT: Preferences.Key<Int> = intPreferencesKey("INPUT_API_PORT")
        public val SCALING_FACTOR: Preferences.Key<Float> = floatPreferencesKey("INPUT_SCALING_FACTOR")
        public val AUTO_START_HTTP: Preferences.Key<Boolean> = booleanPreferencesKey("INPUT_AUTO_START_HTTP")
        public val REQUIRE_PIN: Preferences.Key<Boolean> = booleanPreferencesKey("INPUT_REQUIRE_PIN")
        public val PIN: Preferences.Key<Int> = intPreferencesKey("INPUT_PIN")
    }

    public object Default {
        public const val INPUT_ENABLED: Boolean = true
        public const val API_PORT: Int = 8084
        public const val SCALING_FACTOR: Float = 1.0f
        public const val AUTO_START_HTTP: Boolean = true
        public const val REQUIRE_PIN: Boolean = false
        public const val PIN: Int = 0
    }

    @Immutable
    public data class Data(
        public val inputEnabled: Boolean = Default.INPUT_ENABLED,
        public val apiPort: Int = 8084,
        public val scalingFactor: Float = Default.SCALING_FACTOR,
        public val autoStartHttp: Boolean = Default.AUTO_START_HTTP,
        public val requirePin: Boolean = Default.REQUIRE_PIN,
        public val pin: Int = Default.PIN,
    )

    public val data: StateFlow<Data>
    public suspend fun updateData(transform: Data.() -> Data)
}

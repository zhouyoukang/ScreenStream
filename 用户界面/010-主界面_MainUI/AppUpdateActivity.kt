package info.dvkr.screenstream

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

public open class AppUpdateActivity : AppCompatActivity() {

    protected val updateFlow: StateFlow<((Boolean) -> Unit)?> = MutableStateFlow(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    }
}

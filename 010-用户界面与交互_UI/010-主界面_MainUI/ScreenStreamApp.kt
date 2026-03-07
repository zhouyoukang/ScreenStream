package info.dvkr.screenstream

import com.elvishew.xlog.LogConfiguration
import info.dvkr.screenstream.common.CommonKoinModule
import info.dvkr.screenstream.input.InputKoinModule
import info.dvkr.screenstream.mjpeg.MjpegKoinModule
import org.koin.core.module.Module

public class ScreenStreamApp : BaseApp() {

    override fun configureLogger(builder: LogConfiguration.Builder) {
    }

    override val streamingModules: Array<Module> = arrayOf(CommonKoinModule, MjpegKoinModule, InputKoinModule)
}

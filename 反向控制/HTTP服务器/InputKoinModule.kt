package info.dvkr.screenstream.input

import info.dvkr.screenstream.input.settings.InputSettings
import info.dvkr.screenstream.input.settings.InputSettingsImpl
import org.koin.core.module.Module
import org.koin.dsl.bind
import org.koin.dsl.module

public val InputKoinModule: Module = module {
    single { InputSettingsImpl(get()) } bind InputSettings::class
    single(createdAtStart = true) {
        val settings: InputSettings = get()
        InputHttpServer(get(), settings.data.value.apiPort).also { server ->
            if (settings.data.value.autoStartHttp) server.start()
        }
    }
}

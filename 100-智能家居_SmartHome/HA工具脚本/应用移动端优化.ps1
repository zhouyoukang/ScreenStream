# 应用移动端优化到现有仪表盘
# 直接在当前仪表盘中添加移动端优化视图

param(
    [string]$Dashboard = "lovelace.dashboard_ui"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   应用移动端优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = Join-Path $PSScriptRoot "..\config\.storage\$Dashboard"

if (-not (Test-Path $storagePath)) {
    Write-Host "错误: 找不到配置文件 $Dashboard" -ForegroundColor Red
    Write-Host "可用的仪表盘:" -ForegroundColor Yellow
    Get-ChildItem (Join-Path $PSScriptRoot "..\config\.storage") -Filter "lovelace.*" | 
        ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor White }
    exit 1
}

Write-Host "读取配置: $Dashboard" -ForegroundColor Yellow

# 读取JSON
$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# 备份
$backupPath = "$storagePath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份至: $backupPath" -ForegroundColor Green

# 创建移动端优化视图
$mobileView = @{
    title = "移动端"
    path = "mobile"
    icon = "mdi:cellphone"
    type = "sections"
    sections = @(
        # 顶部信息卡片
        @{
            type = "grid"
            cards = @(
                @{
                    type = "custom:mushroom-template-card"
                    primary = "{% set hour = now().hour %}{% if hour < 12 %}早上好{% elif hour < 18 %}下午好{% else %}晚上好{% endif %}!"
                    secondary = "欢迎回家"
                    icon = "mdi:hand-wave"
                    icon_color = "amber"
                    layout = "horizontal"
                    fill_container = $true
                    tap_action = @{
                        action = "none"
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,152,0,0.15), rgba(255,193,7,0.05));
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  padding: 12px;
  min-height: 80px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-chips-card"
                    alignment = "center"
                    chips = @(
                        @{
                            type = "weather"
                            entity = "weather.he_feng_tian_qi"
                            show_temperature = $true
                            show_conditions = $true
                        },
                        @{
                            type = "template"
                            icon = "mdi:clock-outline"
                            content = "{{ now().strftime('%H:%M') }}"
                            icon_color = "blue"
                        },
                        @{
                            type = "entity"
                            entity = "sensor.sonoff_total_power_usage"
                            icon = "mdi:flash"
                            icon_color = "{% set power = states('sensor.sonoff_total_power_usage') | float %}{% if power < 300 %}green{% elif power < 600 %}amber{% else %}red{% endif %}"
                            content_info = "state"
                        }
                    )
                    card_mod = @{
                        style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.4);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  margin: 8px 0;
}
"@
                    }
                }
            )
        },
        # 场景快捷控制
        @{
            type = "grid"
            title = "快捷场景"
            cards = @(
                @{
                    type = "custom:mushroom-template-card"
                    primary = "全部关闭"
                    secondary = "关闭所有灯光"
                    icon = "mdi:power"
                    icon_color = "red"
                    layout = "vertical"
                    tap_action = @{
                        action = "call-service"
                        service = "homeassistant.turn_off"
                        target = @{
                            entity_id = @(
                                "switch.sonoff_10022ddc35_1",
                                "switch.sonoff_10022de63b_1",
                                "switch.giot_cn_1116373212_v6oodm_on_p_2_1",
                                "light.philips_strip3_12ad_light"
                            )
                        }
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.2), rgba(244,67,54,0.05));
  backdrop-filter: blur(15px);
  border-radius: 16px;
  border: 1px solid rgba(244,67,54,0.3);
  box-shadow: 0 4px 20px rgba(244,67,54,0.15);
  min-height: 120px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
ha-card:active {
  transform: scale(0.95);
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-template-card"
                    primary = "睡眠模式"
                    secondary = "柔和照明"
                    icon = "mdi:weather-night"
                    icon_color = "purple"
                    layout = "vertical"
                    tap_action = @{
                        action = "call-service"
                        service = "homeassistant.turn_off"
                        target = @{
                            entity_id = @(
                                "switch.sonoff_10022ddc35_1",
                                "switch.sonoff_10022de63b_1"
                            )
                        }
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(156,39,176,0.2), rgba(156,39,176,0.05));
  backdrop-filter: blur(15px);
  border-radius: 16px;
  border: 1px solid rgba(156,39,176,0.3);
  box-shadow: 0 4px 20px rgba(156,39,176,0.15);
  min-height: 120px;
}
"@
                    }
                }
            )
        },
        # 主要灯光
        @{
            type = "grid"
            title = "灯光控制"
            cards = @(
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.sonoff_10022ddc35_1"
                    name = "顶灯一号"
                    icon = "mdi:ceiling-light"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 4px 20px rgba(255,193,7,0.3)
  {% else %}
    0 4px 16px rgba(0,0,0,0.08)
  {% endif %};
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.sonoff_10022de63b_1"
                    name = "顶灯二号"
                    icon = "mdi:ceiling-light"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
                    name = "床底灯"
                    icon = "mdi:lamp"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "light.philips_strip3_12ad_light"
                    name = "灯带"
                    icon = "mdi:led-strip-variant"
                    use_light_color = $true
                    show_color_control = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(135deg, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 255 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 193 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 7 }}, 0.3),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 255 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 193 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 7 }}, 0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                }
            )
        },
        # 电量监控
        @{
            type = "grid"
            title = "电量监控"
            cards = @(
                @{
                    type = "gauge"
                    entity = "sensor.sonoff_total_power_usage"
                    name = "当前总功率"
                    min = 0
                    max = 800
                    needle = $true
                    severity = @{
                        green = 0
                        yellow = 300
                        red = 600
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(33,150,243,0.05));
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(33,150,243,0.2);
  box-shadow: 0 4px 16px rgba(33,150,243,0.1);
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-entity-card"
                    entity = "sensor.river_2_max_total_output_power"
                    name = "移动电源"
                    icon = "mdi:battery-charging"
                    icon_color = "green"
                    layout = "vertical"
                    primary_info = "name"
                    secondary_info = "state"
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.15), rgba(76,175,80,0.05));
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(76,175,80,0.2);
  box-shadow: 0 4px 16px rgba(76,175,80,0.1);
}
"@
                    }
                }
            )
        }
    )
}

# 检查是否已存在移动端视图
$views = $config.data.config.views
$mobileIndex = -1
for ($i = 0; $i -lt $views.Count; $i++) {
    if ($views[$i].path -eq "mobile" -or $views[$i].title -eq "移动端") {
        $mobileIndex = $i
        break
    }
}

if ($mobileIndex -ge 0) {
    $views[$mobileIndex] = $mobileView
    Write-Host "✓ 已更新移动端视图" -ForegroundColor Green
} else {
    $config.data.config.views += $mobileView
    Write-Host "✓ 已添加移动端视图" -ForegroundColor Green
}

# 保存
$config | ConvertTo-Json -Depth 20 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 完成!" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 重启 Home Assistant" -ForegroundColor White
Write-Host "  2. 访问移动端视图`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



param(
    [string]$Dashboard = "lovelace.dashboard_ui"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   应用移动端优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = Join-Path $PSScriptRoot "..\config\.storage\$Dashboard"

if (-not (Test-Path $storagePath)) {
    Write-Host "错误: 找不到配置文件 $Dashboard" -ForegroundColor Red
    Write-Host "可用的仪表盘:" -ForegroundColor Yellow
    Get-ChildItem (Join-Path $PSScriptRoot "..\config\.storage") -Filter "lovelace.*" | 
        ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor White }
    exit 1
}

Write-Host "读取配置: $Dashboard" -ForegroundColor Yellow

# 读取JSON
$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# 备份
$backupPath = "$storagePath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份至: $backupPath" -ForegroundColor Green

# 创建移动端优化视图
$mobileView = @{
    title = "移动端"
    path = "mobile"
    icon = "mdi:cellphone"
    type = "sections"
    sections = @(
        # 顶部信息卡片
        @{
            type = "grid"
            cards = @(
                @{
                    type = "custom:mushroom-template-card"
                    primary = "{% set hour = now().hour %}{% if hour < 12 %}早上好{% elif hour < 18 %}下午好{% else %}晚上好{% endif %}!"
                    secondary = "欢迎回家"
                    icon = "mdi:hand-wave"
                    icon_color = "amber"
                    layout = "horizontal"
                    fill_container = $true
                    tap_action = @{
                        action = "none"
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,152,0,0.15), rgba(255,193,7,0.05));
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  padding: 12px;
  min-height: 80px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-chips-card"
                    alignment = "center"
                    chips = @(
                        @{
                            type = "weather"
                            entity = "weather.he_feng_tian_qi"
                            show_temperature = $true
                            show_conditions = $true
                        },
                        @{
                            type = "template"
                            icon = "mdi:clock-outline"
                            content = "{{ now().strftime('%H:%M') }}"
                            icon_color = "blue"
                        },
                        @{
                            type = "entity"
                            entity = "sensor.sonoff_total_power_usage"
                            icon = "mdi:flash"
                            icon_color = "{% set power = states('sensor.sonoff_total_power_usage') | float %}{% if power < 300 %}green{% elif power < 600 %}amber{% else %}red{% endif %}"
                            content_info = "state"
                        }
                    )
                    card_mod = @{
                        style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.4);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  margin: 8px 0;
}
"@
                    }
                }
            )
        },
        # 场景快捷控制
        @{
            type = "grid"
            title = "快捷场景"
            cards = @(
                @{
                    type = "custom:mushroom-template-card"
                    primary = "全部关闭"
                    secondary = "关闭所有灯光"
                    icon = "mdi:power"
                    icon_color = "red"
                    layout = "vertical"
                    tap_action = @{
                        action = "call-service"
                        service = "homeassistant.turn_off"
                        target = @{
                            entity_id = @(
                                "switch.sonoff_10022ddc35_1",
                                "switch.sonoff_10022de63b_1",
                                "switch.giot_cn_1116373212_v6oodm_on_p_2_1",
                                "light.philips_strip3_12ad_light"
                            )
                        }
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.2), rgba(244,67,54,0.05));
  backdrop-filter: blur(15px);
  border-radius: 16px;
  border: 1px solid rgba(244,67,54,0.3);
  box-shadow: 0 4px 20px rgba(244,67,54,0.15);
  min-height: 120px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
ha-card:active {
  transform: scale(0.95);
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-template-card"
                    primary = "睡眠模式"
                    secondary = "柔和照明"
                    icon = "mdi:weather-night"
                    icon_color = "purple"
                    layout = "vertical"
                    tap_action = @{
                        action = "call-service"
                        service = "homeassistant.turn_off"
                        target = @{
                            entity_id = @(
                                "switch.sonoff_10022ddc35_1",
                                "switch.sonoff_10022de63b_1"
                            )
                        }
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(156,39,176,0.2), rgba(156,39,176,0.05));
  backdrop-filter: blur(15px);
  border-radius: 16px;
  border: 1px solid rgba(156,39,176,0.3);
  box-shadow: 0 4px 20px rgba(156,39,176,0.15);
  min-height: 120px;
}
"@
                    }
                }
            )
        },
        # 主要灯光
        @{
            type = "grid"
            title = "灯光控制"
            cards = @(
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.sonoff_10022ddc35_1"
                    name = "顶灯一号"
                    icon = "mdi:ceiling-light"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 4px 20px rgba(255,193,7,0.3)
  {% else %}
    0 4px 16px rgba(0,0,0,0.08)
  {% endif %};
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.sonoff_10022de63b_1"
                    name = "顶灯二号"
                    icon = "mdi:ceiling-light"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
                    name = "床底灯"
                    icon = "mdi:lamp"
                    use_light_color = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-light-card"
                    entity = "light.philips_strip3_12ad_light"
                    name = "灯带"
                    icon = "mdi:led-strip-variant"
                    use_light_color = $true
                    show_color_control = $true
                    layout = "vertical"
                    card_mod = @{
                        style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(135deg, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 255 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 193 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 7 }}, 0.3),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 255 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 193 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 7 }}, 0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %};
  backdrop-filter: blur(20px);
  border-radius: 16px;
  min-height: 140px;
}
"@
                    }
                }
            )
        },
        # 电量监控
        @{
            type = "grid"
            title = "电量监控"
            cards = @(
                @{
                    type = "gauge"
                    entity = "sensor.sonoff_total_power_usage"
                    name = "当前总功率"
                    min = 0
                    max = 800
                    needle = $true
                    severity = @{
                        green = 0
                        yellow = 300
                        red = 600
                    }
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(33,150,243,0.05));
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(33,150,243,0.2);
  box-shadow: 0 4px 16px rgba(33,150,243,0.1);
}
"@
                    }
                },
                @{
                    type = "custom:mushroom-entity-card"
                    entity = "sensor.river_2_max_total_output_power"
                    name = "移动电源"
                    icon = "mdi:battery-charging"
                    icon_color = "green"
                    layout = "vertical"
                    primary_info = "name"
                    secondary_info = "state"
                    card_mod = @{
                        style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.15), rgba(76,175,80,0.05));
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(76,175,80,0.2);
  box-shadow: 0 4px 16px rgba(76,175,80,0.1);
}
"@
                    }
                }
            )
        }
    )
}

# 检查是否已存在移动端视图
$views = $config.data.config.views
$mobileIndex = -1
for ($i = 0; $i -lt $views.Count; $i++) {
    if ($views[$i].path -eq "mobile" -or $views[$i].title -eq "移动端") {
        $mobileIndex = $i
        break
    }
}

if ($mobileIndex -ge 0) {
    $views[$mobileIndex] = $mobileView
    Write-Host "✓ 已更新移动端视图" -ForegroundColor Green
} else {
    $config.data.config.views += $mobileView
    Write-Host "✓ 已添加移动端视图" -ForegroundColor Green
}

# 保存
$config | ConvertTo-Json -Depth 20 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 完成!" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 重启 Home Assistant" -ForegroundColor White
Write-Host "  2. 访问移动端视图`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



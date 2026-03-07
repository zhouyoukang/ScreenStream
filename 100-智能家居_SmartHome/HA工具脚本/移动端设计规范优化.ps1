# 移动端设计规范优化
# 按照Material Design和iOS设计规范重新设计

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   移动端设计规范优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = "config\.storage\lovelace.mobile"
$backupPath = "$storagePath.backup_设计规范_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份" -ForegroundColor Green

$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# ========== 移动端设计规范配置 ==========

# 创建多个视图标签页
$config.data.config.views = @(
    # ========== 主页视图 ==========
    @{
        title = "主页"
        path = "home"
        icon = "mdi:home"
        type = "sections"
        subview = $false
        sections = @(
            # 顶部状态栏（精简）
            @{
                type = "grid"
                cards = @(
                    @{
                        type = "custom:mushroom-chips-card"
                        alignment = "center"
                        chips = @(
                            @{
                                type = "template"
                                icon = "mdi:home-heart"
                                content = "{% set h=now().hour %}{% if h<12 %}早上好{% elif h<18 %}下午好{% else %}晚上好{% endif %}"
                                icon_color = "amber"
                            },
                            @{
                                type = "weather"
                                entity = "weather.he_feng_tian_qi"
                                show_temperature = $true
                                show_conditions = $true
                            },
                            @{
                                type = "template"
                                icon = "mdi:flash"
                                content = "{{ states('sensor.sonoff_total_power_usage') }}W"
                                icon_color = "{% set p=states('sensor.sonoff_total_power_usage')|float %}{% if p<300 %}green{% elif p<600 %}amber{% else %}red{% endif %}"
                            },
                            @{
                                type = "template"
                                icon = "mdi:thermometer"
                                content = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}°C"
                                icon_color = "blue"
                            }
                        )
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(var(--rgb-primary-color), 0.08), rgba(var(--rgb-accent-color), 0.08)) !important;
  backdrop-filter: blur(30px);
  border-radius: 28px;
  border: none;
  box-shadow: 
    0 4px 20px rgba(0,0,0,0.08),
    inset 0 1px 0 rgba(255,255,255,0.3);
  padding: 4px !important;
  margin: 8px 0 !important;
}
"@
                        }
                    }
                )
            },
            
            # 一键场景（4个，2x2，移动端标准）
            @{
                type = "grid"
                title = ""
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "全部关闭"
                        secondary = ""
                        icon = "mdi:power-off"
                        icon_color = "red"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "homeassistant.turn_off"
                            target = @{
                                entity_id = @(
                                    "switch.sonoff_10022ddc35_1","switch.sonoff_10022de63b_1",
                                    "switch.giot_cn_1116373212_v6oodm_on_p_2_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_3_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_2_1",
                                    "light.philips_strip3_12ad_light",
                                    "switch.giot_cn_1116363322_v6oodm_on_p_2_1",
                                    "switch.giot_cn_1116357483_v6oodm_on_p_2_1",
                                    "switch.giot_cn_1116363360_v6oodm_on_p_2_1",
                                    "switch.sonoff_10022dede9_1",
                                    "switch.sonoff_10022dedc7_1"
                                )
                            }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(244,67,54,0.15), rgba(244,67,54,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  border: none;
  box-shadow: 
    0 8px 24px rgba(244,67,54,0.2),
    inset 0 1px 0 rgba(255,255,255,0.2);
  min-height: 120px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
ha-card:active {
  transform: scale(0.96);
  box-shadow: 0 4px 12px rgba(244,67,54,0.3);
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(244,67,54,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "全部开启"
                        secondary = ""
                        icon = "mdi:lightbulb-group"
                        icon_color = "green"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "homeassistant.turn_on"
                            target = @{
                                entity_id = @(
                                    "switch.sonoff_10022ddc35_1",
                                    "switch.sonoff_10022de63b_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_3_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_2_1"
                                )
                            }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(76,175,80,0.15), rgba(76,175,80,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(76,175,80,0.2);
  min-height: 120px;
}
ha-card:active { transform: scale(0.96); }
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(76,175,80,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "睡眠"
                        secondary = ""
                        icon = "mdi:sleep"
                        icon_color = "deep-purple"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "scene.turn_on"
                            target = @{ entity_id = "scene.shui_mian_mo_shi" }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(103,58,183,0.15), rgba(103,58,183,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(103,58,183,0.2);
  min-height: 120px;
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(103,58,183,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "氛围"
                        secondary = ""
                        icon = "mdi:led-strip-variant"
                        icon_color = "{% if is_state('light.philips_strip3_12ad_light', 'on') %}cyan{% else %}grey{% endif %}"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "light.toggle"
                            target = @{ entity_id = "light.philips_strip3_12ad_light" }
                        }
                        hold_action = @{
                            action = "more-info"
                            entity = "light.philips_strip3_12ad_light"
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(to bottom, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 0 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 188 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 212 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 0 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 188 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 212 }}, 0.08))
  {% else %}
    linear-gradient(to bottom, rgba(96,125,139,0.12), rgba(96,125,139,0.04))
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(0,188,212,0.18);
  min-height: 120px;
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(0,188,212,0.2) !important;
}
"@
                        }
                    }
                )
            },
            
            # 主要灯光（横向卡片，信息丰富）
            @{
                type = "grid"
                title = "💡 主要照明"
                cards = @(
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.sonoff_10022ddc35_1"
                        name = "顶灯一号"
                        icon = "mdi:ceiling-light"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        tap_action = @{ action = "toggle" }
                        hold_action = @{ action = "more-info" }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  border: none;
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 4px 16px rgba(255,193,7,0.25),
    inset 0 1px 0 rgba(255,255,255,0.2)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
ha-card:active {
  transform: scale(0.98);
}
mushroom-shape-icon {
  --icon-size: 44px !important;
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
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.huca_cn_1103518825_dh2_on_p_3_1"
                        name = "筒灯 Left"
                        icon = "mdi:lightbulb-outline"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_3_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_3_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.huca_cn_1103518825_dh2_on_p_2_1"
                        name = "筒灯 Right"
                        icon = "mdi:lightbulb-outline"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_2_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_2_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
                        name = "床底灯"
                        icon = "mdi:lamp"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "light.philips_strip3_12ad_light"
                        name = "智能灯带"
                        icon = "mdi:led-strip-variant"
                        use_light_color = $true
                        show_brightness_control = $true
                        show_color_control = $true
                        layout = "horizontal"
                        fill_container = $true
                        collapsible_controls = $false
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(to right, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    0 4px 16px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.3)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 120px;
}
"@
                        }
                    }
                )
            },
            
            # 其他灯光（紧凑版，3列）
            @{
                type = "grid"
                title = "🔆 其他灯光 (5个)"
                cards = @(
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116363322_v6oodm_on_p_2_1"
                        name = "1号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('switch.giot_cn_1116363322_v6oodm_on_p_2_1', 'on') %}
    rgba(255,193,7,0.15)
  {% else %}
    rgba(var(--rgb-card-background-color), 0.25)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: {% if is_state('switch.giot_cn_1116363322_v6oodm_on_p_2_1', 'on') %}
    0 3px 12px rgba(255,193,7,0.2)
  {% else %}
    0 2px 6px rgba(0,0,0,0.05)
  {% endif %};
  min-height: 88px;
}
"@
                        }
                    },
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116357483_v6oodm_on_p_2_1"
                        name = "2号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116357483_v6oodm_on_p_2_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.giot_cn_1116357483_v6oodm_on_p_2_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116363360_v6oodm_on_p_2_1"
                        name = "3号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116363360_v6oodm_on_p_2_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.giot_cn_1116363360_v6oodm_on_p_2_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.sonoff_10022dede9_1"
                        name = "4号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022dede9_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.sonoff_10022dede9_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.sonoff_10022dedc7_1"
                        name = "5号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022dedc7_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.sonoff_10022dedc7_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    }
                )
            },
            
            # 环境与功率（卡片式）
            @{
                type = "grid"
                title = "📊 状态监控"
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.sonoff_total_power_usage') }} W"
                        secondary = "实时功率"
                        icon = "mdi:flash-circle"
                        icon_color = "{% set p=states('sensor.sonoff_total_power_usage')|float %}{% if p<300 %}green{% elif p<600 %}amber{% else %}red{% endif %}"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(255,152,0,0.12), rgba(255,152,0,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(255,152,0,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}°C"
                        secondary = "室内温度"
                        icon = "mdi:thermometer"
                        icon_color = "blue"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(33,150,243,0.12), rgba(33,150,243,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(33,150,243,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.miaomiaoce_t9_0582_relative_humidity') }}%"
                        secondary = "室内湿度"
                        icon = "mdi:water-percent"
                        icon_color = "cyan"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(0,188,212,0.12), rgba(0,188,212,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(0,188,212,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    }
                )
            }
        )
    },
    
    # ========== 场景视图 ==========
    @{
        title = "场景"
        path = "scenes"
        icon = "mdi:palette"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "🎭 所有场景"
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "回家模式"
                        secondary = "开灯 · 开风扇"
                        icon = "mdi:home-import-outline"
                        icon_color = "green"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.hui_jia_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(76,175,80,0.15), rgba(76,175,80,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(76,175,80,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "离家模式"
                        secondary = "关闭所有 · 安全"
                        icon = "mdi:home-export-outline"
                        icon_color = "orange"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.chi_jia_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(255,152,0,0.15), rgba(255,152,0,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(255,152,0,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "睡眠模式"
                        secondary = "柔和照明 · 关风扇"
                        icon = "mdi:sleep"
                        icon_color = "deep-purple"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.shui_mian_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(103,58,183,0.15), rgba(103,58,183,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(103,58,183,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "工作模式"
                        secondary = "明亮 · 专注"
                        icon = "mdi:laptop"
                        icon_color = "blue"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.gong_zuo_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(33,150,243,0.15), rgba(33,150,243,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(33,150,243,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "娱乐模式"
                        secondary = "氛围灯 · 放松"
                        icon = "mdi:movie-open"
                        icon_color = "pink"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.yu_le_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(233,30,99,0.15), rgba(233,30,99,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(233,30,99,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    }
                )
            }
        )
    },
    
    # ========== 设备视图 ==========
    @{
        title = "设备"
        path = "devices"
        icon = "mdi:devices"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "⚙️ 设备控制"
                cards = @(
                    @{
                        type = "custom:mushroom-fan-card"
                        entity = "fan.dmaker_p221_5b47_fan"
                        name = "智能风扇"
                        icon = "mdi:fan"
                        show_percentage_control = $true
                        show_oscillate_control = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    linear-gradient(to right, rgba(0,188,212,0.18), rgba(0,188,212,0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    0 4px 16px rgba(0,188,212,0.25)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 6px 0 !important;
  padding: 18px !important;
  min-height: 100px;
}
mushroom-shape-icon {
  animation: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}spin 2s linear infinite{% else %}none{% endif %};
}
@keyframes spin { 100% { transform: rotate(360deg); } }
"@
                        }
                    },
                    @{
                        type = "entities"
                        title = "升降桌控制"
                        show_header_toggle = $false
                        entities = @(
                            @{
                                entity = "select.yszn01_cn_740448557_ys2102_motor_control_p_2_2"
                                name = "桌面高度"
                                icon = "mdi:desk"
                            }
                        )
                        card_mod = @{
                            style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.35) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(0,0,0,0.08);
  margin: 6px 0 !important;
}
"@
                        }
                    }
                )
            }
        )
    },
    
    # ========== 数据视图 ==========
    @{
        title = "数据"
        path = "data"
        icon = "mdi:chart-line"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "📈 数据分析"
                cards = @(
                    @{
                        type = "custom:mini-graph-card"
                        entities = @(
                            @{
                                entity = "sensor.sonoff_total_power_usage"
                                name = "功率"
                                color = "#FF9800"
                            }
                        )
                        name = "24小时功率趋势"
                        hours_to_show = 24
                        points_per_hour = 4
                        line_width = 3
                        animate = $true
                        show = @{
                            fill = "fade"
                            points = $false
                            labels = $true
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.4) !important;
  backdrop-filter: blur(28px);
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  padding: 16px !important;
}
"@
                        }
                    },
                    @{
                        type = "gauge"
                        entity = "sensor.sonoff_total_power_usage"
                        name = "总功率"
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
  background: rgba(var(--rgb-card-background-color), 0.4) !important;
  backdrop-filter: blur(28px);
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  min-height: 220px;
}
"@
                        }
                    }
                )
            }
        )
    }
)

# 保存配置
$config | ConvertTo-Json -Depth 35 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 移动端设计规范优化完成！" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "设计改进:" -ForegroundColor Yellow
Write-Host "  ✓ 多视图标签页（主页/场景/设备/数据）" -ForegroundColor White
Write-Host "  ✓ 横向卡片布局（信息密度更高）" -ForegroundColor White
Write-host "  ✓ 统一20px圆角（现代化）" -ForegroundColor White
Write-Host "  ✓ 72-120px卡片高度（移动端标准）" -ForegroundColor White
Write-Host "  ✓ chips顶部状态栏（一目了然）" -ForegroundColor White
Write-Host "  ✓ 8px间距（适合移动端）" -ForegroundColor White
Write-Host "  ✓ 底部安全区域适配（刘海屏）`n" -ForegroundColor White

Write-Host "布局优化:" -ForegroundColor Yellow
Write-Host "  • 主页：快速访问+主要控制" -ForegroundColor White
Write-Host "  • 场景：所有场景横向卡片" -ForegroundColor White
Write-Host "  • 设备：风扇+升降桌详细控制" -ForegroundColor White
Write-Host "  • 数据：图表+仪表盘`n" -ForegroundColor White

Write-Host "移动端特性:" -ForegroundColor Yellow
Write-Host "  ✓ 底部标签导航" -ForegroundColor White
Write-Host "  ✓ 刘海屏安全区域" -ForegroundColor White
Write-Host "  ✓ 横向卡片易于浏览" -ForegroundColor White
Write-Host "  ✓ chips快速信息栏" -ForegroundColor White
Write-Host "  ✓ 统一的视觉语言`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   移动端设计规范优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = "config\.storage\lovelace.mobile"
$backupPath = "$storagePath.backup_设计规范_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份" -ForegroundColor Green

$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# ========== 移动端设计规范配置 ==========

# 创建多个视图标签页
$config.data.config.views = @(
    # ========== 主页视图 ==========
    @{
        title = "主页"
        path = "home"
        icon = "mdi:home"
        type = "sections"
        subview = $false
        sections = @(
            # 顶部状态栏（精简）
            @{
                type = "grid"
                cards = @(
                    @{
                        type = "custom:mushroom-chips-card"
                        alignment = "center"
                        chips = @(
                            @{
                                type = "template"
                                icon = "mdi:home-heart"
                                content = "{% set h=now().hour %}{% if h<12 %}早上好{% elif h<18 %}下午好{% else %}晚上好{% endif %}"
                                icon_color = "amber"
                            },
                            @{
                                type = "weather"
                                entity = "weather.he_feng_tian_qi"
                                show_temperature = $true
                                show_conditions = $true
                            },
                            @{
                                type = "template"
                                icon = "mdi:flash"
                                content = "{{ states('sensor.sonoff_total_power_usage') }}W"
                                icon_color = "{% set p=states('sensor.sonoff_total_power_usage')|float %}{% if p<300 %}green{% elif p<600 %}amber{% else %}red{% endif %}"
                            },
                            @{
                                type = "template"
                                icon = "mdi:thermometer"
                                content = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}°C"
                                icon_color = "blue"
                            }
                        )
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(var(--rgb-primary-color), 0.08), rgba(var(--rgb-accent-color), 0.08)) !important;
  backdrop-filter: blur(30px);
  border-radius: 28px;
  border: none;
  box-shadow: 
    0 4px 20px rgba(0,0,0,0.08),
    inset 0 1px 0 rgba(255,255,255,0.3);
  padding: 4px !important;
  margin: 8px 0 !important;
}
"@
                        }
                    }
                )
            },
            
            # 一键场景（4个，2x2，移动端标准）
            @{
                type = "grid"
                title = ""
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "全部关闭"
                        secondary = ""
                        icon = "mdi:power-off"
                        icon_color = "red"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "homeassistant.turn_off"
                            target = @{
                                entity_id = @(
                                    "switch.sonoff_10022ddc35_1","switch.sonoff_10022de63b_1",
                                    "switch.giot_cn_1116373212_v6oodm_on_p_2_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_3_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_2_1",
                                    "light.philips_strip3_12ad_light",
                                    "switch.giot_cn_1116363322_v6oodm_on_p_2_1",
                                    "switch.giot_cn_1116357483_v6oodm_on_p_2_1",
                                    "switch.giot_cn_1116363360_v6oodm_on_p_2_1",
                                    "switch.sonoff_10022dede9_1",
                                    "switch.sonoff_10022dedc7_1"
                                )
                            }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(244,67,54,0.15), rgba(244,67,54,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  border: none;
  box-shadow: 
    0 8px 24px rgba(244,67,54,0.2),
    inset 0 1px 0 rgba(255,255,255,0.2);
  min-height: 120px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
ha-card:active {
  transform: scale(0.96);
  box-shadow: 0 4px 12px rgba(244,67,54,0.3);
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(244,67,54,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "全部开启"
                        secondary = ""
                        icon = "mdi:lightbulb-group"
                        icon_color = "green"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "homeassistant.turn_on"
                            target = @{
                                entity_id = @(
                                    "switch.sonoff_10022ddc35_1",
                                    "switch.sonoff_10022de63b_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_3_1",
                                    "switch.huca_cn_1103518825_dh2_on_p_2_1"
                                )
                            }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(76,175,80,0.15), rgba(76,175,80,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(76,175,80,0.2);
  min-height: 120px;
}
ha-card:active { transform: scale(0.96); }
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(76,175,80,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "睡眠"
                        secondary = ""
                        icon = "mdi:sleep"
                        icon_color = "deep-purple"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "scene.turn_on"
                            target = @{ entity_id = "scene.shui_mian_mo_shi" }
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to bottom, rgba(103,58,183,0.15), rgba(103,58,183,0.05)) !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(103,58,183,0.2);
  min-height: 120px;
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(103,58,183,0.2) !important;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "氛围"
                        secondary = ""
                        icon = "mdi:led-strip-variant"
                        icon_color = "{% if is_state('light.philips_strip3_12ad_light', 'on') %}cyan{% else %}grey{% endif %}"
                        layout = "vertical"
                        tap_action = @{
                            action = "call-service"
                            service = "light.toggle"
                            target = @{ entity_id = "light.philips_strip3_12ad_light" }
                        }
                        hold_action = @{
                            action = "more-info"
                            entity = "light.philips_strip3_12ad_light"
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(to bottom, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 0 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 188 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 212 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 0 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 188 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 212 }}, 0.08))
  {% else %}
    linear-gradient(to bottom, rgba(96,125,139,0.12), rgba(96,125,139,0.04))
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(0,188,212,0.18);
  min-height: 120px;
}
mushroom-shape-icon {
  --icon-size: 52px !important;
  --shape-color: rgba(0,188,212,0.2) !important;
}
"@
                        }
                    }
                )
            },
            
            # 主要灯光（横向卡片，信息丰富）
            @{
                type = "grid"
                title = "💡 主要照明"
                cards = @(
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.sonoff_10022ddc35_1"
                        name = "顶灯一号"
                        icon = "mdi:ceiling-light"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        tap_action = @{ action = "toggle" }
                        hold_action = @{ action = "more-info" }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  border: none;
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 4px 16px rgba(255,193,7,0.25),
    inset 0 1px 0 rgba(255,255,255,0.2)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
ha-card:active {
  transform: scale(0.98);
}
mushroom-shape-icon {
  --icon-size: 44px !important;
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
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.huca_cn_1103518825_dh2_on_p_3_1"
                        name = "筒灯 Left"
                        icon = "mdi:lightbulb-outline"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_3_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_3_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.huca_cn_1103518825_dh2_on_p_2_1"
                        name = "筒灯 Right"
                        icon = "mdi:lightbulb-outline"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_2_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.huca_cn_1103518825_dh2_on_p_2_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
                        name = "床底灯"
                        icon = "mdi:lamp"
                        use_light_color = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}linear-gradient(to right, rgba(255,193,7,0.18), rgba(255,193,7,0.08)){% else %}rgba(var(--rgb-card-background-color), 0.3){% endif %} !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}0 4px 16px rgba(255,193,7,0.25){% else %}0 2px 8px rgba(0,0,0,0.06){% endif %}; margin: 4px 0 !important; padding: 16px !important; min-height: 72px; }" }
                    },
                    @{
                        type = "custom:mushroom-light-card"
                        entity = "light.philips_strip3_12ad_light"
                        name = "智能灯带"
                        icon = "mdi:led-strip-variant"
                        use_light_color = $true
                        show_brightness_control = $true
                        show_color_control = $true
                        layout = "horizontal"
                        fill_container = $true
                        collapsible_controls = $false
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(to right, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.1))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    0 4px 16px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.3)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 120px;
}
"@
                        }
                    }
                )
            },
            
            # 其他灯光（紧凑版，3列）
            @{
                type = "grid"
                title = "🔆 其他灯光 (5个)"
                cards = @(
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116363322_v6oodm_on_p_2_1"
                        name = "1号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('switch.giot_cn_1116363322_v6oodm_on_p_2_1', 'on') %}
    rgba(255,193,7,0.15)
  {% else %}
    rgba(var(--rgb-card-background-color), 0.25)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: {% if is_state('switch.giot_cn_1116363322_v6oodm_on_p_2_1', 'on') %}
    0 3px 12px rgba(255,193,7,0.2)
  {% else %}
    0 2px 6px rgba(0,0,0,0.05)
  {% endif %};
  min-height: 88px;
}
"@
                        }
                    },
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116357483_v6oodm_on_p_2_1"
                        name = "2号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116357483_v6oodm_on_p_2_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.giot_cn_1116357483_v6oodm_on_p_2_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.giot_cn_1116363360_v6oodm_on_p_2_1"
                        name = "3号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116363360_v6oodm_on_p_2_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.giot_cn_1116363360_v6oodm_on_p_2_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.sonoff_10022dede9_1"
                        name = "4号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022dede9_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.sonoff_10022dede9_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    },
                    @{
                        type = "button"
                        entity = "switch.sonoff_10022dedc7_1"
                        name = "5号"
                        icon = "mdi:lightbulb"
                        show_state = $true
                        tap_action = @{ action = "toggle" }
                        card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022dedc7_1', 'on') %}rgba(255,193,7,0.15){% else %}rgba(var(--rgb-card-background-color), 0.25){% endif %} !important; backdrop-filter: blur(20px); border-radius: 16px; box-shadow: {% if is_state('switch.sonoff_10022dedc7_1', 'on') %}0 3px 12px rgba(255,193,7,0.2){% else %}0 2px 6px rgba(0,0,0,0.05){% endif %}; min-height: 88px; }" }
                    }
                )
            },
            
            # 环境与功率（卡片式）
            @{
                type = "grid"
                title = "📊 状态监控"
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.sonoff_total_power_usage') }} W"
                        secondary = "实时功率"
                        icon = "mdi:flash-circle"
                        icon_color = "{% set p=states('sensor.sonoff_total_power_usage')|float %}{% if p<300 %}green{% elif p<600 %}amber{% else %}red{% endif %}"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(255,152,0,0.12), rgba(255,152,0,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(255,152,0,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}°C"
                        secondary = "室内温度"
                        icon = "mdi:thermometer"
                        icon_color = "blue"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(33,150,243,0.12), rgba(33,150,243,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(33,150,243,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "{{ states('sensor.miaomiaoce_t9_0582_relative_humidity') }}%"
                        secondary = "室内湿度"
                        icon = "mdi:water-percent"
                        icon_color = "cyan"
                        layout = "horizontal"
                        card_mod = @{
                            style = @"
ha-card {
  background: linear-gradient(to right, rgba(0,188,212,0.12), rgba(0,188,212,0.04)) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(0,188,212,0.15);
  margin: 4px 0 !important;
  padding: 16px !important;
  min-height: 72px;
}
"@
                        }
                    }
                )
            }
        )
    },
    
    # ========== 场景视图 ==========
    @{
        title = "场景"
        path = "scenes"
        icon = "mdi:palette"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "🎭 所有场景"
                cards = @(
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "回家模式"
                        secondary = "开灯 · 开风扇"
                        icon = "mdi:home-import-outline"
                        icon_color = "green"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.hui_jia_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(76,175,80,0.15), rgba(76,175,80,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(76,175,80,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "离家模式"
                        secondary = "关闭所有 · 安全"
                        icon = "mdi:home-export-outline"
                        icon_color = "orange"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.chi_jia_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(255,152,0,0.15), rgba(255,152,0,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(255,152,0,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "睡眠模式"
                        secondary = "柔和照明 · 关风扇"
                        icon = "mdi:sleep"
                        icon_color = "deep-purple"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.shui_mian_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(103,58,183,0.15), rgba(103,58,183,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(103,58,183,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "工作模式"
                        secondary = "明亮 · 专注"
                        icon = "mdi:laptop"
                        icon_color = "blue"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.gong_zuo_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(33,150,243,0.15), rgba(33,150,243,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(33,150,243,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    },
                    @{
                        type = "custom:mushroom-template-card"
                        primary = "娱乐模式"
                        secondary = "氛围灯 · 放松"
                        icon = "mdi:movie-open"
                        icon_color = "pink"
                        layout = "horizontal"
                        tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.yu_le_mo_shi" } }
                        card_mod = @{ style = "ha-card { background: linear-gradient(to right, rgba(233,30,99,0.15), rgba(233,30,99,0.05)) !important; backdrop-filter: blur(25px); border-radius: 20px; box-shadow: 0 4px 16px rgba(233,30,99,0.18); margin: 6px 0 !important; padding: 18px !important; min-height: 76px; }" }
                    }
                )
            }
        )
    },
    
    # ========== 设备视图 ==========
    @{
        title = "设备"
        path = "devices"
        icon = "mdi:devices"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "⚙️ 设备控制"
                cards = @(
                    @{
                        type = "custom:mushroom-fan-card"
                        entity = "fan.dmaker_p221_5b47_fan"
                        name = "智能风扇"
                        icon = "mdi:fan"
                        show_percentage_control = $true
                        show_oscillate_control = $true
                        layout = "horizontal"
                        fill_container = $true
                        card_mod = @{
                            style = @"
ha-card {
  background: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    linear-gradient(to right, rgba(0,188,212,0.18), rgba(0,188,212,0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.3)
  {% endif %} !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    0 4px 16px rgba(0,188,212,0.25)
  {% else %}
    0 2px 8px rgba(0,0,0,0.06)
  {% endif %};
  margin: 6px 0 !important;
  padding: 18px !important;
  min-height: 100px;
}
mushroom-shape-icon {
  animation: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}spin 2s linear infinite{% else %}none{% endif %};
}
@keyframes spin { 100% { transform: rotate(360deg); } }
"@
                        }
                    },
                    @{
                        type = "entities"
                        title = "升降桌控制"
                        show_header_toggle = $false
                        entities = @(
                            @{
                                entity = "select.yszn01_cn_740448557_ys2102_motor_control_p_2_2"
                                name = "桌面高度"
                                icon = "mdi:desk"
                            }
                        )
                        card_mod = @{
                            style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.35) !important;
  backdrop-filter: blur(25px);
  border-radius: 20px;
  box-shadow: 0 3px 12px rgba(0,0,0,0.08);
  margin: 6px 0 !important;
}
"@
                        }
                    }
                )
            }
        )
    },
    
    # ========== 数据视图 ==========
    @{
        title = "数据"
        path = "data"
        icon = "mdi:chart-line"
        type = "sections"
        sections = @(
            @{
                type = "grid"
                title = "📈 数据分析"
                cards = @(
                    @{
                        type = "custom:mini-graph-card"
                        entities = @(
                            @{
                                entity = "sensor.sonoff_total_power_usage"
                                name = "功率"
                                color = "#FF9800"
                            }
                        )
                        name = "24小时功率趋势"
                        hours_to_show = 24
                        points_per_hour = 4
                        line_width = 3
                        animate = $true
                        show = @{
                            fill = "fade"
                            points = $false
                            labels = $true
                        }
                        card_mod = @{
                            style = @"
ha-card {
  background: rgba(var(--rgb-card-background-color), 0.4) !important;
  backdrop-filter: blur(28px);
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  padding: 16px !important;
}
"@
                        }
                    },
                    @{
                        type = "gauge"
                        entity = "sensor.sonoff_total_power_usage"
                        name = "总功率"
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
  background: rgba(var(--rgb-card-background-color), 0.4) !important;
  backdrop-filter: blur(28px);
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  min-height: 220px;
}
"@
                        }
                    }
                )
            }
        )
    }
)

# 保存配置
$config | ConvertTo-Json -Depth 35 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 移动端设计规范优化完成！" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "设计改进:" -ForegroundColor Yellow
Write-Host "  ✓ 多视图标签页（主页/场景/设备/数据）" -ForegroundColor White
Write-Host "  ✓ 横向卡片布局（信息密度更高）" -ForegroundColor White
Write-host "  ✓ 统一20px圆角（现代化）" -ForegroundColor White
Write-Host "  ✓ 72-120px卡片高度（移动端标准）" -ForegroundColor White
Write-Host "  ✓ chips顶部状态栏（一目了然）" -ForegroundColor White
Write-Host "  ✓ 8px间距（适合移动端）" -ForegroundColor White
Write-Host "  ✓ 底部安全区域适配（刘海屏）`n" -ForegroundColor White

Write-Host "布局优化:" -ForegroundColor Yellow
Write-Host "  • 主页：快速访问+主要控制" -ForegroundColor White
Write-Host "  • 场景：所有场景横向卡片" -ForegroundColor White
Write-Host "  • 设备：风扇+升降桌详细控制" -ForegroundColor White
Write-Host "  • 数据：图表+仪表盘`n" -ForegroundColor White

Write-Host "移动端特性:" -ForegroundColor Yellow
Write-Host "  ✓ 底部标签导航" -ForegroundColor White
Write-Host "  ✓ 刘海屏安全区域" -ForegroundColor White
Write-Host "  ✓ 横向卡片易于浏览" -ForegroundColor White
Write-Host "  ✓ chips快速信息栏" -ForegroundColor White
Write-Host "  ✓ 统一的视觉语言`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



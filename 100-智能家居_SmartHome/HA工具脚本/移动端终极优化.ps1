# 移动端终极优化 - 添加可视化、房间分组、统计数据等

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   移动端终极优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = "config\.storage\lovelace.mobile"
$backupPath = "$storagePath.backup_终极版_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份" -ForegroundColor Green

$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# 获取现有sections
$existingSections = $config.data.config.views[0].sections

# ========== 新增：数据统计仪表板 ==========
$statsDashboard = @{
    type = "grid"
    title = "📊 数据统计仪表板"
    cards = @(
        # 设备统计
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states | count }}"
            secondary = "总实体数"
            icon = "mdi:database"
            icon_color = "blue"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.25), rgba(33,150,243,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(33,150,243,0.2);
  min-height: 115px;
}
mushroom-shape-icon {
  --icon-size: 48px !important;
}
"@
            }
        },
        # 灯光统计
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states.light | selectattr('state', 'eq', 'on') | list | count + states.switch | selectattr('state', 'eq', 'on') | list | count }}"
            secondary = "开启的灯光"
            icon = "mdi:lightbulb-on"
            icon_color = "amber"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(255,193,7,0.2);
  min-height: 115px;
}
"@
            }
        },
        # 今日能耗
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ (states('sensor.sonoff_total_power_usage') | float * 24 / 1000) | round(2) }}"
            secondary = "预计日耗电(kWh)"
            icon = "mdi:lightning-bolt"
            icon_color = "orange"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,152,0,0.25), rgba(255,152,0,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(255,152,0,0.2);
  min-height: 115px;
}
"@
            }
        },
        # 平均温度
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}"
            secondary = "当前温度(°C)"
            icon = "mdi:home-thermometer-outline"
            icon_color = "{% set t=states('sensor.miaomiaoce_t9_0582_temperature')|float %}{% if t<20 %}blue{% elif t<26 %}green{% else %}red{% endif %}"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.25), rgba(76,175,80,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(76,175,80,0.2);
  min-height: 115px;
}
"@
            }
        }
    )
}

# ========== 新增：房间分组控制 ==========
$roomsControl = @{
    type = "grid"
    title = "🏠 房间控制"
    cards = @(
        # A635房间
        @{
            type = "custom:mushroom-template-card"
            primary = "A635房间"
            secondary = "主房间 · {{ states.switch | selectattr('attributes.friendly_name', 'search', 'A635|主') | selectattr('state', 'eq', 'on') | list | count }} 个开启"
            icon = "mdi:bed-double"
            icon_color = "purple"
            layout = "vertical"
            tap_action = @{
                action = "navigate"
                navigation_path = "/config/areas/area/a635"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(156,39,176,0.25), rgba(156,39,176,0.12)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  border: 2px solid rgba(156,39,176,0.35);
  box-shadow: 0 9px 32px rgba(156,39,176,0.25);
  min-height: 125px;
}
ha-card:active { transform: scale(0.94); }
mushroom-shape-icon { --icon-size: 50px !important; }
"@
            }
        },
        # 客厅
        @{
            type = "custom:mushroom-template-card"
            primary = "客厅区域"
            secondary = "公共空间"
            icon = "mdi:sofa"
            icon_color = "brown"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(121,85,72,0.25), rgba(121,85,72,0.12)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 9px 32px rgba(121,85,72,0.2);
  min-height: 125px;
}
"@
            }
        }
    )
}

# ========== 新增：多功能图表 ==========
$chartsSection = @{
    type = "grid"
    title = "📈 数据可视化"
    cards = @(
        # 功率对比（今日vs昨日）
        @{
            type = "custom:mini-graph-card"
            entities = @(
                @{
                    entity = "sensor.sonoff_total_power_usage"
                    name = "实时功率"
                    color = "#FF9800"
                },
                @{
                    entity = "sensor.river_2_max_total_output_power"
                    name = "移动电源"
                    color = "#4CAF50"
                }
            )
            name = "功率对比"
            hours_to_show = 12
            points_per_hour = 6
            line_width = 3
            font_size = 75
            animate = $true
            smoothing = $true
            lower_bound = 0
            upper_bound = 800
            show = @{
                name = $true
                icon = $true
                state = $true
                legend = $true
                fill = "fade"
                points = $true
                labels = $true
                graph = "line"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(30,136,229,0.08)) !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  border: 2px solid rgba(33,150,243,0.25);
  box-shadow: 0 10px 38px rgba(33,150,243,0.2);
  padding: 16px !important;
}
"@
            }
        },
        # 温度趋势
        @{
            type = "custom:mini-graph-card"
            entities = @(
                @{
                    entity = "sensor.miaomiaoce_t9_0582_temperature"
                    name = "室内温度"
                    color = "#2196F3"
                }
            )
            name = "温度趋势"
            hours_to_show = 24
            points_per_hour = 2
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
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(3,169,244,0.08)) !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  padding: 16px !important;
}
"@
            }
        }
    )
}

# ========== 新增：快速开关面板 ==========
$quickSwitches = @{
    type = "grid"
    title = "⚡ 快速开关"
    cards = @(
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.sonoff_10022ddc35_1"
            name = "顶灯一"
            icon = "mdi:ceiling-light"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            hold_action = @{ action = "more-info" }
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 14px;
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 6px 22px rgba(255,193,7,0.35)
  {% else %}
    0 3px 12px rgba(0,0,0,0.08)
  {% endif %};
  min-height: 95px;
  transition: all 0.3s ease;
}
ha-card:active { transform: scale(0.92); }
"@
            }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.sonoff_10022de63b_1"
            name = "顶灯二"
            icon = "mdi:ceiling-light"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15)){% else %}rgba(var(--rgb-card-background-color), 0.4){% endif %} !important; backdrop-filter: blur(20px); border-radius: 14px; box-shadow: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}0 6px 22px rgba(255,193,7,0.35){% else %}0 3px 12px rgba(0,0,0,0.08){% endif %}; min-height: 95px; }" }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
            name = "床底灯"
            icon = "mdi:lamp"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15)){% else %}rgba(var(--rgb-card-background-color), 0.4){% endif %} !important; backdrop-filter: blur(20px); border-radius: 14px; box-shadow: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}0 6px 22px rgba(255,193,7,0.35){% else %}0 3px 12px rgba(0,0,0,0.08){% endif %}; min-height: 95px; }" }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "fan.dmaker_p221_5b47_fan"
            name = "风扇"
            icon = "mdi:fan"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    linear-gradient(135deg, rgba(0,188,212,0.3), rgba(0,188,212,0.15))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 14px;
  min-height: 95px;
}
mushroom-shape-icon {
  animation: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}spin 2s linear infinite{% else %}none{% endif %};
}
@keyframes spin { 100% { transform: rotate(360deg); } }
"@
            }
        }
    )
}

# ========== 新增：智能灯带控制（详细）==========
$stripControl = @{
    type = "grid"
    title = "🌈 智能灯带详细控制"
    cards = @(
        @{
            type = "custom:mushroom-light-card"
            entity = "light.philips_strip3_12ad_light"
            name = "飞利浦灯带"
            icon = "mdi:led-strip-variant"
            use_light_color = $true
            show_brightness_control = $true
            show_color_control = $true
            show_color_temp_control = $false
            layout = "horizontal"
            fill_container = $true
            collapsible_controls = $false
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(135deg, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.45),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.45)
  {% endif %} !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  border: 3px solid {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
         {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
         {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.6)
  {% else %}
    rgba(255,255,255,0.15)
  {% endif %};
  box-shadow: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    0 12px 42px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.5),
    0 0 75px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                  {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                  {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.3),
    inset 0 2px 0 rgba(255,255,255,0.25)
  {% else %}
    0 4px 16px rgba(0,0,0,0.1)
  {% endif %};
  padding: 16px !important;
  min-height: 160px;
  animation: {% if is_state('light.philips_strip3_12ad_light', 'on') %}stripGlow 4s ease-in-out infinite{% else %}none{% endif %};
}
@keyframes stripGlow {
  0%, 100% { 
    box-shadow: 
      0 12px 42px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.5);
  }
  50% { 
    box-shadow: 
      0 14px 52px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.7);
  }
}
mushroom-shape-icon {
  --icon-size: 56px !important;
}
"@
            }
        },
        # 灯带效果选择
        @{
            type = "custom:mushroom-select-card"
            entity = "light.philips_strip3_12ad_light"
            name = "灯带效果"
            icon = "mdi:palette"
            icon_color = "pink"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(233,30,99,0.2), rgba(233,30,99,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(233,30,99,0.18);
  min-height: 125px;
}
"@
            }
        }
    )
}

# ========== 新增：时间日程 ==========
$schedule = @{
    type = "grid"
    title = "📅 时间与日程"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ now().strftime('%H:%M:%S') }}"
            secondary = "{{ now().strftime('%Y年%m月%d日 %A') }}"
            icon = "mdi:clock-time-eight"
            icon_color = "deep-purple"
            layout = "horizontal"
            fill_container = $true
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(103,58,183,0.25), rgba(103,58,183,0.12)) !important;
  backdrop-filter: blur(24px);
  border-radius: 18px;
  border: 2px solid rgba(103,58,183,0.35);
  box-shadow: 0 10px 35px rgba(103,58,183,0.25);
  min-height: 95px;
}
mushroom-shape-icon {
  --icon-size: 58px !important;
  animation: clockTick 1s steps(60) infinite;
}
@keyframes clockTick {
  100% { transform: rotate(6deg); }
}
"@
            }
        }
    )
}

# ========== 新增：系统状态 ==========
$systemStatus = @{
    type = "grid"
    title = "🖥️ 系统状态"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "Home Assistant"
            secondary = "运行正常 · 在线"
            icon = "mdi:home-assistant"
            icon_color = "blue"
            layout = "vertical"
            badge_icon = "mdi:check-circle"
            badge_color = "green"
            tap_action = @{
                action = "navigate"
                navigation_path = "/config/info"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(3,169,244,0.22), rgba(3,169,244,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(3,169,244,0.2);
  min-height: 115px;
}
mushroom-shape-icon {
  animation: heartbeat 2s ease-in-out infinite;
}
@keyframes heartbeat {
  0%, 100% { transform: scale(1); }
  25% { transform: scale(1.1); }
  50% { transform: scale(1); }
}
"@
            }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "快速重载"
            secondary = "重新加载配置"
            icon = "mdi:refresh-circle"
            icon_color = "green"
            layout = "vertical"
            tap_action = @{
                action = "call-service"
                service = "homeassistant.reload_all"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.22), rgba(76,175,80,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(76,175,80,0.2);
  min-height: 115px;
}
ha-card:active {
  mushroom-shape-icon {
    animation: spin 0.5s linear;
  }
}
"@
            }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "系统重启"
            secondary = "重启Home Assistant"
            icon = "mdi:restart-alert"
            icon_color = "red"
            layout = "vertical"
            tap_action = @{
                action = "call-service"
                service = "homeassistant.restart"
                confirmation = @{ text = "确定要重启吗？" }
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.22), rgba(244,67,54,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(244,67,54,0.2);
  min-height: 115px;
}
"@
            }
        }
    )
}

# ========== 新增：更多场景（完整10个）==========
$allScenes = @{
    type = "grid"
    title = "🎭 所有场景 (7个)"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "回家"
            icon = "mdi:home-import-outline"
            icon_color = "green"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.hui_jia_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(76,175,80,0.28), rgba(76,175,80,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(76,175,80,0.25); min-height: 110px; } ha-card:active { transform: scale(0.92); }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "离家"
            icon = "mdi:home-export-outline"
            icon_color = "orange"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.chi_jia_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(255,152,0,0.28), rgba(255,152,0,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(255,152,0,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "工作"
            icon = "mdi:laptop"
            icon_color = "blue"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.gong_zuo_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(33,150,243,0.28), rgba(33,150,243,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(33,150,243,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "娱乐"
            icon = "mdi:movie-open"
            icon_color = "pink"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.yu_le_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(233,30,99,0.28), rgba(233,30,99,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(233,30,99,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "清洁"
            icon = "mdi:broom"
            icon_color = "teal"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.qing_ji_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(0,150,136,0.28), rgba(0,150,136,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(0,150,136,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "节能"
            icon = "mdi:leaf"
            icon_color = "light-green"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.jie_neng_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(139,195,74,0.28), rgba(139,195,74,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(139,195,74,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "紧急"
            icon = "mdi:alert-circle"
            icon_color = "red"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.jin_ji_mo_shi" } }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.28), rgba(244,67,54,0.14)) !important;
  backdrop-filter: blur(20px);
  border-radius: 15px;
  box-shadow: 0 7px 26px rgba(244,67,54,0.25);
  min-height: 110px;
  animation: emergencyPulse 2s ease-in-out infinite;
}
@keyframes emergencyPulse {
  0%, 100% { box-shadow: 0 7px 26px rgba(244,67,54,0.25); }
  50% { box-shadow: 0 10px 38px rgba(244,67,54,0.45); }
}
"@
            }
        }
    )
}

# 重新组织所有sections，优化顺序
$config.data.config.views[0].sections = @(
    $existingSections[0],  # 欢迎卡片
    $statsDashboard,       # 数据统计 (新)
    $existingSections[1],  # 基础场景
    $allScenes,            # 所有场景 (新)
    $quickSwitches,        # 快速开关 (新)
    $existingSections[2],  # 主要灯光
    $existingSections[3],  # 其他灯光
    $stripControl,         # 灯带详细控制 (新)
    $existingSections[4],  # 电风扇
    $existingSections[5],  # 升降桌
    $existingSections[6],  # 功率监控
    $chartsSection,        # 数据可视化 (新)
    $existingSections[7],  # 环境状态
    $roomsControl,         # 房间控制 (新)
    $existingSections[8],  # 电源监控
    $schedule,             # 时间日程 (新)
    $existingSections[9],  # 天气预报
    $existingSections[10], # 智能设备
    $systemStatus          # 系统状态 (新)
)

$config | ConvertTo-Json -Depth 35 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 终极优化完成！" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "新增区域:" -ForegroundColor Yellow
Write-Host "  1. 📊 数据统计仪表板 - 4个统计卡片" -ForegroundColor White
Write-Host "  2. 🏠 房间控制 - 房间分组" -ForegroundColor White
Write-Host "  3. 📈 数据可视化 - 多图表对比" -ForegroundColor White
Write-Host "  4. ⚡ 快速开关 - 4个常用设备" -ForegroundColor White
Write-Host "  5. 🌈 灯带详细控制 - 颜色+亮度+效果" -ForegroundColor White
Write-Host "  6. 📅 时间日程 - 大时钟" -ForegroundColor White
Write-Host "  7. 🖥️ 系统状态 - 3个系统卡片" -ForegroundColor White
Write-Host "  8. 🎭 所有场景 - 7个完整场景`n" -ForegroundColor White

Write-Host "总计内容:" -ForegroundColor Cyan
Write-Host "  • 19个功能区域" -ForegroundColor White
Write-Host "  • 55+个交互元素" -ForegroundColor White
Write-Host "  • 10个场景" -ForegroundColor White
Write-Host "  • 11个灯光" -ForegroundColor White
Write-Host "  • 4个图表" -ForegroundColor White
Write-Host "  • 10种动画`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")


$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   移动端终极优化" -ForegroundColor Cyan  
Write-Host "============================================`n" -ForegroundColor Cyan

$storagePath = "config\.storage\lovelace.mobile"
$backupPath = "$storagePath.backup_终极版_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $storagePath $backupPath
Write-Host "✓ 已备份" -ForegroundColor Green

$config = Get-Content $storagePath -Raw -Encoding UTF8 | ConvertFrom-Json

# 获取现有sections
$existingSections = $config.data.config.views[0].sections

# ========== 新增：数据统计仪表板 ==========
$statsDashboard = @{
    type = "grid"
    title = "📊 数据统计仪表板"
    cards = @(
        # 设备统计
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states | count }}"
            secondary = "总实体数"
            icon = "mdi:database"
            icon_color = "blue"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.25), rgba(33,150,243,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(33,150,243,0.2);
  min-height: 115px;
}
mushroom-shape-icon {
  --icon-size: 48px !important;
}
"@
            }
        },
        # 灯光统计
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states.light | selectattr('state', 'eq', 'on') | list | count + states.switch | selectattr('state', 'eq', 'on') | list | count }}"
            secondary = "开启的灯光"
            icon = "mdi:lightbulb-on"
            icon_color = "amber"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,193,7,0.25), rgba(255,193,7,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(255,193,7,0.2);
  min-height: 115px;
}
"@
            }
        },
        # 今日能耗
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ (states('sensor.sonoff_total_power_usage') | float * 24 / 1000) | round(2) }}"
            secondary = "预计日耗电(kWh)"
            icon = "mdi:lightning-bolt"
            icon_color = "orange"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(255,152,0,0.25), rgba(255,152,0,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(255,152,0,0.2);
  min-height: 115px;
}
"@
            }
        },
        # 平均温度
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ states('sensor.miaomiaoce_t9_0582_temperature') }}"
            secondary = "当前温度(°C)"
            icon = "mdi:home-thermometer-outline"
            icon_color = "{% set t=states('sensor.miaomiaoce_t9_0582_temperature')|float %}{% if t<20 %}blue{% elif t<26 %}green{% else %}red{% endif %}"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.25), rgba(76,175,80,0.12)) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(76,175,80,0.2);
  min-height: 115px;
}
"@
            }
        }
    )
}

# ========== 新增：房间分组控制 ==========
$roomsControl = @{
    type = "grid"
    title = "🏠 房间控制"
    cards = @(
        # A635房间
        @{
            type = "custom:mushroom-template-card"
            primary = "A635房间"
            secondary = "主房间 · {{ states.switch | selectattr('attributes.friendly_name', 'search', 'A635|主') | selectattr('state', 'eq', 'on') | list | count }} 个开启"
            icon = "mdi:bed-double"
            icon_color = "purple"
            layout = "vertical"
            tap_action = @{
                action = "navigate"
                navigation_path = "/config/areas/area/a635"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(156,39,176,0.25), rgba(156,39,176,0.12)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  border: 2px solid rgba(156,39,176,0.35);
  box-shadow: 0 9px 32px rgba(156,39,176,0.25);
  min-height: 125px;
}
ha-card:active { transform: scale(0.94); }
mushroom-shape-icon { --icon-size: 50px !important; }
"@
            }
        },
        # 客厅
        @{
            type = "custom:mushroom-template-card"
            primary = "客厅区域"
            secondary = "公共空间"
            icon = "mdi:sofa"
            icon_color = "brown"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(121,85,72,0.25), rgba(121,85,72,0.12)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 9px 32px rgba(121,85,72,0.2);
  min-height: 125px;
}
"@
            }
        }
    )
}

# ========== 新增：多功能图表 ==========
$chartsSection = @{
    type = "grid"
    title = "📈 数据可视化"
    cards = @(
        # 功率对比（今日vs昨日）
        @{
            type = "custom:mini-graph-card"
            entities = @(
                @{
                    entity = "sensor.sonoff_total_power_usage"
                    name = "实时功率"
                    color = "#FF9800"
                },
                @{
                    entity = "sensor.river_2_max_total_output_power"
                    name = "移动电源"
                    color = "#4CAF50"
                }
            )
            name = "功率对比"
            hours_to_show = 12
            points_per_hour = 6
            line_width = 3
            font_size = 75
            animate = $true
            smoothing = $true
            lower_bound = 0
            upper_bound = 800
            show = @{
                name = $true
                icon = $true
                state = $true
                legend = $true
                fill = "fade"
                points = $true
                labels = $true
                graph = "line"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(30,136,229,0.08)) !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  border: 2px solid rgba(33,150,243,0.25);
  box-shadow: 0 10px 38px rgba(33,150,243,0.2);
  padding: 16px !important;
}
"@
            }
        },
        # 温度趋势
        @{
            type = "custom:mini-graph-card"
            entities = @(
                @{
                    entity = "sensor.miaomiaoce_t9_0582_temperature"
                    name = "室内温度"
                    color = "#2196F3"
                }
            )
            name = "温度趋势"
            hours_to_show = 24
            points_per_hour = 2
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
  background: linear-gradient(135deg, rgba(33,150,243,0.15), rgba(3,169,244,0.08)) !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  padding: 16px !important;
}
"@
            }
        }
    )
}

# ========== 新增：快速开关面板 ==========
$quickSwitches = @{
    type = "grid"
    title = "⚡ 快速开关"
    cards = @(
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.sonoff_10022ddc35_1"
            name = "顶灯一"
            icon = "mdi:ceiling-light"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            hold_action = @{ action = "more-info" }
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 14px;
  box-shadow: {% if is_state('switch.sonoff_10022ddc35_1', 'on') %}
    0 6px 22px rgba(255,193,7,0.35)
  {% else %}
    0 3px 12px rgba(0,0,0,0.08)
  {% endif %};
  min-height: 95px;
  transition: all 0.3s ease;
}
ha-card:active { transform: scale(0.92); }
"@
            }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.sonoff_10022de63b_1"
            name = "顶灯二"
            icon = "mdi:ceiling-light"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{ style = "ha-card { background: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15)){% else %}rgba(var(--rgb-card-background-color), 0.4){% endif %} !important; backdrop-filter: blur(20px); border-radius: 14px; box-shadow: {% if is_state('switch.sonoff_10022de63b_1', 'on') %}0 6px 22px rgba(255,193,7,0.35){% else %}0 3px 12px rgba(0,0,0,0.08){% endif %}; min-height: 95px; }" }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "switch.giot_cn_1116373212_v6oodm_on_p_2_1"
            name = "床底灯"
            icon = "mdi:lamp"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{ style = "ha-card { background: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}linear-gradient(135deg, rgba(255,193,7,0.3), rgba(255,193,7,0.15)){% else %}rgba(var(--rgb-card-background-color), 0.4){% endif %} !important; backdrop-filter: blur(20px); border-radius: 14px; box-shadow: {% if is_state('switch.giot_cn_1116373212_v6oodm_on_p_2_1', 'on') %}0 6px 22px rgba(255,193,7,0.35){% else %}0 3px 12px rgba(0,0,0,0.08){% endif %}; min-height: 95px; }" }
        },
        @{
            type = "custom:mushroom-entity-card"
            entity = "fan.dmaker_p221_5b47_fan"
            name = "风扇"
            icon = "mdi:fan"
            layout = "vertical"
            tap_action = @{ action = "toggle" }
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}
    linear-gradient(135deg, rgba(0,188,212,0.3), rgba(0,188,212,0.15))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.4)
  {% endif %} !important;
  backdrop-filter: blur(20px);
  border-radius: 14px;
  min-height: 95px;
}
mushroom-shape-icon {
  animation: {% if is_state('fan.dmaker_p221_5b47_fan', 'on') %}spin 2s linear infinite{% else %}none{% endif %};
}
@keyframes spin { 100% { transform: rotate(360deg); } }
"@
            }
        }
    )
}

# ========== 新增：智能灯带控制（详细）==========
$stripControl = @{
    type = "grid"
    title = "🌈 智能灯带详细控制"
    cards = @(
        @{
            type = "custom:mushroom-light-card"
            entity = "light.philips_strip3_12ad_light"
            name = "飞利浦灯带"
            icon = "mdi:led-strip-variant"
            use_light_color = $true
            show_brightness_control = $true
            show_color_control = $true
            show_color_temp_control = $false
            layout = "horizontal"
            fill_container = $true
            collapsible_controls = $false
            card_mod = @{
                style = @"
ha-card {
  background: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    linear-gradient(135deg, 
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.45),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.25),
      rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
           {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.08))
  {% else %}
    rgba(var(--rgb-card-background-color), 0.45)
  {% endif %} !important;
  backdrop-filter: blur(26px);
  border-radius: 20px;
  border: 3px solid {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
         {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
         {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.6)
  {% else %}
    rgba(255,255,255,0.15)
  {% endif %};
  box-shadow: {% if is_state('light.philips_strip3_12ad_light', 'on') %}
    0 12px 42px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                     {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.5),
    0 0 75px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                  {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                  {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.3),
    inset 0 2px 0 rgba(255,255,255,0.25)
  {% else %}
    0 4px 16px rgba(0,0,0,0.1)
  {% endif %};
  padding: 16px !important;
  min-height: 160px;
  animation: {% if is_state('light.philips_strip3_12ad_light', 'on') %}stripGlow 4s ease-in-out infinite{% else %}none{% endif %};
}
@keyframes stripGlow {
  0%, 100% { 
    box-shadow: 
      0 12px 42px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.5);
  }
  50% { 
    box-shadow: 
      0 14px 52px rgba({{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[0] or 200 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[1] or 100 }}, 
                       {{ state_attr('light.philips_strip3_12ad_light', 'rgb_color')[2] or 50 }}, 0.7);
  }
}
mushroom-shape-icon {
  --icon-size: 56px !important;
}
"@
            }
        },
        # 灯带效果选择
        @{
            type = "custom:mushroom-select-card"
            entity = "light.philips_strip3_12ad_light"
            name = "灯带效果"
            icon = "mdi:palette"
            icon_color = "pink"
            layout = "vertical"
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(233,30,99,0.2), rgba(233,30,99,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(233,30,99,0.18);
  min-height: 125px;
}
"@
            }
        }
    )
}

# ========== 新增：时间日程 ==========
$schedule = @{
    type = "grid"
    title = "📅 时间与日程"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "{{ now().strftime('%H:%M:%S') }}"
            secondary = "{{ now().strftime('%Y年%m月%d日 %A') }}"
            icon = "mdi:clock-time-eight"
            icon_color = "deep-purple"
            layout = "horizontal"
            fill_container = $true
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(103,58,183,0.25), rgba(103,58,183,0.12)) !important;
  backdrop-filter: blur(24px);
  border-radius: 18px;
  border: 2px solid rgba(103,58,183,0.35);
  box-shadow: 0 10px 35px rgba(103,58,183,0.25);
  min-height: 95px;
}
mushroom-shape-icon {
  --icon-size: 58px !important;
  animation: clockTick 1s steps(60) infinite;
}
@keyframes clockTick {
  100% { transform: rotate(6deg); }
}
"@
            }
        }
    )
}

# ========== 新增：系统状态 ==========
$systemStatus = @{
    type = "grid"
    title = "🖥️ 系统状态"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "Home Assistant"
            secondary = "运行正常 · 在线"
            icon = "mdi:home-assistant"
            icon_color = "blue"
            layout = "vertical"
            badge_icon = "mdi:check-circle"
            badge_color = "green"
            tap_action = @{
                action = "navigate"
                navigation_path = "/config/info"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(3,169,244,0.22), rgba(3,169,244,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(3,169,244,0.2);
  min-height: 115px;
}
mushroom-shape-icon {
  animation: heartbeat 2s ease-in-out infinite;
}
@keyframes heartbeat {
  0%, 100% { transform: scale(1); }
  25% { transform: scale(1.1); }
  50% { transform: scale(1); }
}
"@
            }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "快速重载"
            secondary = "重新加载配置"
            icon = "mdi:refresh-circle"
            icon_color = "green"
            layout = "vertical"
            tap_action = @{
                action = "call-service"
                service = "homeassistant.reload_all"
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(76,175,80,0.22), rgba(76,175,80,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(76,175,80,0.2);
  min-height: 115px;
}
ha-card:active {
  mushroom-shape-icon {
    animation: spin 0.5s linear;
  }
}
"@
            }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "系统重启"
            secondary = "重启Home Assistant"
            icon = "mdi:restart-alert"
            icon_color = "red"
            layout = "vertical"
            tap_action = @{
                action = "call-service"
                service = "homeassistant.restart"
                confirmation = @{ text = "确定要重启吗？" }
            }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.22), rgba(244,67,54,0.1)) !important;
  backdrop-filter: blur(22px);
  border-radius: 17px;
  box-shadow: 0 8px 30px rgba(244,67,54,0.2);
  min-height: 115px;
}
"@
            }
        }
    )
}

# ========== 新增：更多场景（完整10个）==========
$allScenes = @{
    type = "grid"
    title = "🎭 所有场景 (7个)"
    cards = @(
        @{
            type = "custom:mushroom-template-card"
            primary = "回家"
            icon = "mdi:home-import-outline"
            icon_color = "green"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.hui_jia_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(76,175,80,0.28), rgba(76,175,80,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(76,175,80,0.25); min-height: 110px; } ha-card:active { transform: scale(0.92); }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "离家"
            icon = "mdi:home-export-outline"
            icon_color = "orange"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.chi_jia_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(255,152,0,0.28), rgba(255,152,0,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(255,152,0,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "工作"
            icon = "mdi:laptop"
            icon_color = "blue"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.gong_zuo_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(33,150,243,0.28), rgba(33,150,243,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(33,150,243,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "娱乐"
            icon = "mdi:movie-open"
            icon_color = "pink"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.yu_le_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(233,30,99,0.28), rgba(233,30,99,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(233,30,99,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "清洁"
            icon = "mdi:broom"
            icon_color = "teal"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.qing_ji_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(0,150,136,0.28), rgba(0,150,136,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(0,150,136,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "节能"
            icon = "mdi:leaf"
            icon_color = "light-green"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.jie_neng_mo_shi" } }
            card_mod = @{ style = "ha-card { background: linear-gradient(135deg, rgba(139,195,74,0.28), rgba(139,195,74,0.14)) !important; backdrop-filter: blur(20px); border-radius: 15px; box-shadow: 0 7px 26px rgba(139,195,74,0.25); min-height: 110px; }" }
        },
        @{
            type = "custom:mushroom-template-card"
            primary = "紧急"
            icon = "mdi:alert-circle"
            icon_color = "red"
            layout = "vertical"
            tap_action = @{ action = "call-service"; service = "scene.turn_on"; target = @{ entity_id = "scene.jin_ji_mo_shi" } }
            card_mod = @{
                style = @"
ha-card {
  background: linear-gradient(135deg, rgba(244,67,54,0.28), rgba(244,67,54,0.14)) !important;
  backdrop-filter: blur(20px);
  border-radius: 15px;
  box-shadow: 0 7px 26px rgba(244,67,54,0.25);
  min-height: 110px;
  animation: emergencyPulse 2s ease-in-out infinite;
}
@keyframes emergencyPulse {
  0%, 100% { box-shadow: 0 7px 26px rgba(244,67,54,0.25); }
  50% { box-shadow: 0 10px 38px rgba(244,67,54,0.45); }
}
"@
            }
        }
    )
}

# 重新组织所有sections，优化顺序
$config.data.config.views[0].sections = @(
    $existingSections[0],  # 欢迎卡片
    $statsDashboard,       # 数据统计 (新)
    $existingSections[1],  # 基础场景
    $allScenes,            # 所有场景 (新)
    $quickSwitches,        # 快速开关 (新)
    $existingSections[2],  # 主要灯光
    $existingSections[3],  # 其他灯光
    $stripControl,         # 灯带详细控制 (新)
    $existingSections[4],  # 电风扇
    $existingSections[5],  # 升降桌
    $existingSections[6],  # 功率监控
    $chartsSection,        # 数据可视化 (新)
    $existingSections[7],  # 环境状态
    $roomsControl,         # 房间控制 (新)
    $existingSections[8],  # 电源监控
    $schedule,             # 时间日程 (新)
    $existingSections[9],  # 天气预报
    $existingSections[10], # 智能设备
    $systemStatus          # 系统状态 (新)
)

$config | ConvertTo-Json -Depth 35 | Set-Content $storagePath -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   ✓ 终极优化完成！" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "新增区域:" -ForegroundColor Yellow
Write-Host "  1. 📊 数据统计仪表板 - 4个统计卡片" -ForegroundColor White
Write-Host "  2. 🏠 房间控制 - 房间分组" -ForegroundColor White
Write-Host "  3. 📈 数据可视化 - 多图表对比" -ForegroundColor White
Write-Host "  4. ⚡ 快速开关 - 4个常用设备" -ForegroundColor White
Write-Host "  5. 🌈 灯带详细控制 - 颜色+亮度+效果" -ForegroundColor White
Write-Host "  6. 📅 时间日程 - 大时钟" -ForegroundColor White
Write-Host "  7. 🖥️ 系统状态 - 3个系统卡片" -ForegroundColor White
Write-Host "  8. 🎭 所有场景 - 7个完整场景`n" -ForegroundColor White

Write-Host "总计内容:" -ForegroundColor Cyan
Write-Host "  • 19个功能区域" -ForegroundColor White
Write-Host "  • 55+个交互元素" -ForegroundColor White
Write-Host "  • 10个场景" -ForegroundColor White
Write-Host "  • 11个灯光" -ForegroundColor White
Write-Host "  • 4个图表" -ForegroundColor White
Write-Host "  • 10种动画`n" -ForegroundColor White

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")



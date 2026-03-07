# Machine Learning Scene Suggestion - Cycle #4 Round #3
# Uses pattern recognition to suggest optimal scenes

import json
from datetime import datetime, timedelta
from collections import defaultdict

class SceneSuggester:
    """ML-based scene suggestion engine"""
    
    def __init__(self, hass):
        self.hass = hass
        self.usage_history = defaultdict(list)
        self.patterns = {}
        
    def record_scene_activation(self, scene_name, context=None):
        """Record when a scene is activated"""
        timestamp = datetime.now()
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        
        record = {
            'scene': scene_name,
            'hour': hour,
            'day': day_of_week,
            'temperature': self.get_temperature(),
            'power_usage': self.get_power(),
            'devices_on': self.count_devices_on(),
            'timestamp': timestamp.isoformat()
        }
        
        self.usage_history[scene_name].append(record)
        self.analyze_patterns()
    
    def analyze_patterns(self):
        """Analyze usage patterns to build prediction model"""
        for scene, records in self.usage_history.items():
            if len(records) < 5:  # Need minimum data
                continue
            
            # Time-based patterns
            common_hours = defaultdict(int)
            for record in records:
                common_hours[record['hour']] += 1
            
            # Find most common hour
            most_common_hour = max(common_hours, key=common_hours.get)
            
            # Day patterns
            common_days = defaultdict(int)
            for record in records:
                common_days[record['day']] += 1
            
            self.patterns[scene] = {
                'common_hours': dict(common_hours),
                'common_days': dict(common_days),
                'most_common_hour': most_common_hour,
                'avg_temperature': self.avg([r['temperature'] for r in records]),
                'avg_power': self.avg([r['power_usage'] for r in records]),
                'frequency': len(records)
            }
    
    def suggest_scene(self, context=None):
        """Suggest optimal scene based on current context"""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        current_temp = self.get_temperature()
        current_power = self.get_power()
        
        suggestions = []
        
        for scene, pattern in self.patterns.items():
            score = 0
            reasons = []
            
            # Time match
            if current_hour == pattern['most_common_hour']:
                score += 50
                reasons.append(f"Usually activate at {current_hour}:00")
            elif current_hour in pattern['common_hours']:
                score += 30
                reasons.append(f"Sometimes activate at this time")
            
            # Day match
            if current_day in pattern['common_days']:
                score += 20
                reasons.append("Common on this day of week")
            
            # Temperature similarity
            temp_diff = abs(current_temp - pattern['avg_temperature'])
            if temp_diff < 3:
                score += 15
                reasons.append("Similar temperature conditions")
            
            # Power usage similarity
            power_diff = abs(current_power - pattern['avg_power'])
            if power_diff < 100:
                score += 10
                reasons.append("Similar power usage pattern")
            
            if score > 40:  # Threshold for suggestion
                suggestions.append({
                    'scene': scene,
                    'score': score,
                    'confidence': min(score / 100, 1.0),
                    'reasons': reasons
                })
        
        # Sort by score
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        
        return suggestions[:3]  # Top 3 suggestions
    
    def get_temperature(self):
        """Get current temperature"""
        try:
            state = self.hass.states.get('sensor.miaomiaoc_temperature')
            return float(state.state) if state else 25.0
        except:
            return 25.0
    
    def get_power(self):
        """Get current power usage"""
        try:
            state = self.hass.states.get('sensor.sonoff_total_power_usage')
            return float(state.state) if state else 0.0
        except:
            return 0.0
    
    def count_devices_on(self):
        """Count how many devices are currently on"""
        count = 0
        for entity_id in self.hass.states.entity_ids():
            state = self.hass.states.get(entity_id)
            if state and state.state == 'on':
                count += 1
        return count
    
    @staticmethod
    def avg(numbers):
        """Calculate average"""
        return sum(numbers) / len(numbers) if numbers else 0

# Service registration
def setup(hass, config):
    """Set up the ML scene suggester"""
    suggester = SceneSuggester(hass)
    
    def handle_suggest(call):
        """Handle suggestion service call"""
        suggestions = suggester.suggest_scene()
        
        # Send notification with suggestions
        if suggestions:
            top_suggestion = suggestions[0]
            message = f"建议激活: {top_suggestion['scene']}\n"
            message += f"置信度: {top_suggestion['confidence']*100:.0f}%\n"
            message += "原因:\n" + "\n".join(f"- {r}" for r in top_suggestion['reasons'])
            
            hass.services.call('notify', 'mobile_app', {
                'title': '🤖 智能场景建议',
                'message': message,
                'data': {
                    'actions': [
                        {'action': f'ACTIVATE_{top_suggestion["scene"].upper()}', 'title': '激活'},
                        {'action': 'IGNORE', 'title': '忽略'}
                    ]
                }
            })
    
    def handle_record(call):
        """Handle scene activation recording"""
        scene_name = call.data.get('scene')
        suggester.record_scene_activation(scene_name)
    
    # Register services
    hass.services.register('ml_suggester', 'suggest', handle_suggest)
    hass.services.register('ml_suggester', 'record', handle_record)
    
    return True

# Usage in automation:
# service: ml_suggester.suggest
# service: ml_suggester.record
#   data:
#     scene: "breakfast_mode"

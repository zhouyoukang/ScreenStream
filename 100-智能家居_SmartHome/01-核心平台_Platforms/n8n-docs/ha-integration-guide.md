# 🏠 Home Assistant n8n Integration Guide

## Overview

This comprehensive guide will help you integrate your Home Assistant instance with n8n for powerful device control and automation. The integration provides:

- **Device Discovery**: Automatic detection of all Home Assistant devices
- **Device Control**: Turn devices ON/OFF, adjust settings, and control multiple devices
- **Status Monitoring**: Real-time device state retrieval and monitoring
- **Error Handling**: Robust error handling for network issues and invalid requests
- **Testing Framework**: Comprehensive testing suite to validate functionality

## 🚀 Quick Start

### Prerequisites

1. **Home Assistant** running and accessible (typically on port 8123)
2. **n8n** installed and running (typically on port 5678)
3. **Home Assistant Long-Lived Access Token** (see setup instructions below)
4. **Node.js** installed for running scripts and tests

### 1. Generate Home Assistant Access Token

1. Open Home Assistant web interface
2. Go to **Profile** → **Long-Lived Access Tokens**
3. Click **Create Token**
4. Give it a name (e.g., "n8n Integration")
5. Copy the generated token (you won't see it again!)

### 2. Configure Integration

Edit `tests/test-config.js` with your settings:

```javascript
module.exports = {
  homeAssistant: {
    baseUrl: 'http://your-ha-ip:8123',  // Your Home Assistant URL
    token: 'your-long-lived-access-token-here',
    timeout: 10000
  },
  n8n: {
    baseUrl: 'http://localhost:5678',
    username: 'admin',
    password: 'admin123',
    timeout: 30000
  }
};
```

### 3. Run Setup Script

```bash
# Run the automated setup
node scripts/setup-ha-integration.js

# Or run step by step
node scripts/setup-ha-integration.js --config-only  # Validate config only
```

### 4. Import n8n Workflow

1. Start n8n: `npm start`
2. Open n8n web interface (http://localhost:5678)
3. Import the workflow: `workflows/ha-device-control.json`
4. Activate the workflow

## 📋 Detailed Setup Instructions

### Step 1: Device Discovery

Discover all available devices in your Home Assistant:

```bash
# Discover devices and save to test data
node scripts/utilities/ha-device-discovery.js

# Use custom Home Assistant URL and token
node scripts/utilities/ha-device-discovery.js --url http://192.168.1.100:8123 --token your-token
```

This will create:
- `tests/test-data/ha-device-discovery.json` - Full device data
- `tests/test-data/ha-device-mapping.json` - Device mapping for n8n
- `tests/test-data/ha-controllable-devices.json` - Controllable devices only

### Step 2: Test Device Control

Test basic device control functionality:

```bash
# Run comprehensive device control tests
node tests/integration/test-ha-device-control.js

# Run quick connectivity tests only
node tests/integration/test-ha-device-control.js --quick

# Skip multi-device tests
node tests/integration/test-ha-device-control.js --no-multi
```

### Step 3: Test API Client

Use the Home Assistant API client directly:

```bash
# Test connection
node scripts/utilities/ha-api-client.js test

# Get all device states
node scripts/utilities/ha-api-client.js states

# Get specific device state
node scripts/utilities/ha-api-client.js state switch.living_room

# Control devices
node scripts/utilities/ha-api-client.js on light.bedroom
node scripts/utilities/ha-api-client.js off switch.kitchen
node scripts/utilities/ha-api-client.js toggle fan.living_room

# Comprehensive device test
node scripts/utilities/ha-api-client.js test-device switch.living_room
```

## 🔧 Using the Integration

### n8n Webhook Endpoints

Once the workflow is imported and active, you can control devices via HTTP requests:

#### Get Device Status

```bash
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_status",
    "entity_id": "switch.living_room",
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'
```

#### Control Device

```bash
# Turn device ON
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control",
    "entity_id": "light.bedroom",
    "command": "on",
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'

# Turn device OFF
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control",
    "entity_id": "switch.kitchen",
    "command": "off",
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'

# Toggle device
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control",
    "entity_id": "fan.living_room",
    "command": "toggle",
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'
```

#### Advanced Light Control

```bash
# Set light brightness
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control",
    "entity_id": "light.bedroom",
    "command": "on",
    "brightness": 128,
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'

# Set light color
curl -X POST "http://localhost:5678/webhook/ha-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control",
    "entity_id": "light.rgb_strip",
    "command": "on",
    "rgb_color": [255, 0, 0],
    "ha_url": "http://localhost:8123",
    "ha_token": "your-token"
  }'
```

### Response Format

#### Successful Status Response

```json
{
  "success": true,
  "action": "get_status",
  "entity_id": "switch.living_room",
  "friendly_name": "Living Room Switch",
  "current_state": "on",
  "last_changed": "2025-09-28T13:45:00.000Z",
  "last_updated": "2025-09-28T13:45:00.000Z",
  "available": true,
  "attributes": {
    "friendly_name": "Living Room Switch"
  },
  "timestamp": "2025-09-28T13:45:30.000Z"
}
```

#### Successful Control Response

```json
{
  "success": true,
  "action": "control",
  "entity_id": "light.bedroom",
  "command": "on",
  "friendly_name": "Bedroom Light",
  "previous_state": "off",
  "current_state": "on",
  "state_changed": true,
  "timestamp": "2025-09-28T13:45:30.000Z",
  "message": "Device light.bedroom on command executed successfully"
}
```

#### Error Response

```json
{
  "success": false,
  "action": "control",
  "entity_id": "invalid.device",
  "error": "Device not found",
  "timestamp": "2025-09-28T13:45:30.000Z"
}
```

## 🧪 Testing and Validation

### Run All Tests

```bash
# Run comprehensive test suite
npm run test:integration

# Run specific Home Assistant tests
node tests/integration/test-ha-device-control.js
node tests/integration/test-ha-connection.js
```

### Test Reports

Tests automatically generate detailed reports:
- `tests/ha-device-control-test-report.json` - Device control test results
- `tests/ha-integration-setup-report.json` - Setup validation results
- `tests/test-data/ha-device-discovery.json` - Device discovery results

### Monitoring and Debugging

Enable debug mode for detailed logging:

```bash
DEBUG=true node scripts/utilities/ha-api-client.js test
DEBUG=true node tests/integration/test-ha-device-control.js
```

## 🔧 Configuration Options

### Environment Variables

You can override configuration using environment variables:

```bash
export HA_URL="http://192.168.1.100:8123"
export HA_TOKEN="your-long-lived-access-token"
export N8N_URL="http://localhost:5678"
export DEBUG="true"
```

### Custom Configuration

Create a custom configuration file:

```javascript
// custom-config.js
module.exports = {
  homeAssistant: {
    baseUrl: process.env.HA_URL || 'http://192.168.1.100:8123',
    token: process.env.HA_TOKEN || 'your-token',
    timeout: 15000
  },
  n8n: {
    baseUrl: process.env.N8N_URL || 'http://localhost:5678',
    timeout: 30000
  }
};
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Connection Refused
```
Error: connect ECONNREFUSED 127.0.0.1:8123
```
**Solution**: Ensure Home Assistant is running and accessible at the configured URL.

#### 2. Unauthorized (401)
```
Error: HTTP 401: Unauthorized
```
**Solution**: Check your Home Assistant token. Generate a new long-lived access token.

#### 3. Device Not Found (404)
```
Error: Device switch.nonexistent not found
```
**Solution**: Run device discovery to get correct entity IDs: `node scripts/utilities/ha-device-discovery.js`

#### 4. Timeout Errors
```
Error: Request timeout
```
**Solution**: Increase timeout in configuration or check network connectivity.

### Debug Steps

1. **Test Home Assistant directly**:
   ```bash
   curl -H "Authorization: Bearer your-token" http://localhost:8123/api/
   ```

2. **Validate configuration**:
   ```bash
   node scripts/setup-ha-integration.js --config-only
   ```

3. **Run connectivity tests**:
   ```bash
   node scripts/utilities/ha-api-client.js test
   ```

4. **Check device discovery**:
   ```bash
   node scripts/utilities/ha-device-discovery.js
   ```

## 📚 API Reference

### HAApiClient Methods

- `testConnection()` - Test Home Assistant connectivity
- `getStates()` - Get all device states
- `getDeviceState(entityId)` - Get specific device state
- `turnOn(entityId, params)` - Turn device on
- `turnOff(entityId, params)` - Turn device off
- `toggle(entityId, params)` - Toggle device state
- `setLightBrightness(entityId, brightness)` - Set light brightness
- `setLightColor(entityId, rgb, colorName)` - Set light color
- `batchControl(operations)` - Control multiple devices
- `testDevice(entityId)` - Comprehensive device test

### Device Discovery Methods

- `discover()` - Full device discovery process
- `testConnection()` - Test HA connection
- `retrieveDeviceStates()` - Get all device states
- `categorizeDevices(states)` - Categorize devices by type
- `generateDeviceMapping()` - Create device mapping for n8n

## 🔄 Integration Workflow

1. **Discovery**: Find all available devices
2. **Validation**: Test connectivity and device control
3. **Configuration**: Set up n8n workflows
4. **Testing**: Validate complete integration
5. **Monitoring**: Ongoing health checks and error handling

## 📈 Next Steps

After successful integration:

1. **Create Custom Workflows**: Build automation workflows in n8n
2. **Add Scheduling**: Set up time-based device control
3. **Integrate with Other Services**: Connect to external APIs and services
4. **Monitor Performance**: Set up logging and monitoring
5. **Expand Device Support**: Add support for more device types

---

**Need Help?** Check the troubleshooting section or run the setup script with `--help` for more options.

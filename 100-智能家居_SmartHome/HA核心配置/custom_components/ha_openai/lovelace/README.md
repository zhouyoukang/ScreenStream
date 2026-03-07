# HomeAssistant OpenAI API Conversation Card

This directory contains a custom Lovelace card configuration for interacting with the HomeAssistant OpenAI API.

## Usage

### Adding the Conversation Card

1. Open the Home Assistant dashboard editor
2. Click "Add Card" in the bottom right corner
3. Select "Manual" card
4. Copy and paste the YAML code from the `ha_openai_conversation_card.yaml` file
5. Click "Save"

> **Note**: This card uses the `custom:text-input-row` and `custom:vertical-stack-in-card` custom card components. If you don't have these installed, please install them via HACS.

### Using the Conversation Entity

You can also use the conversation entity directly in automations, scripts, or other integrations:

- Entity ID: `conversation.ha_openai`
- To send a message, you can use the UI or call the appropriate conversation service
- The response will be stored in the entity's `last_response` attribute

Example automation:

```yaml
automation:
  - alias: "Get Weather Summary via HomeAssistant OpenAI API"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: conversation.process
        target:
          entity_id: conversation.ha_openai
        data:
          text: "Summarize today's weather in one sentence"
      - delay:
          seconds: 3
      - service: notify.mobile_app_my_phone
        data:
          title: "Today's Weather Summary"
          message: "{{ state_attr('conversation.ha_openai', 'last_response') }}"
```

## Entity Attributes

The conversation entity has the following attributes:

- `last_message`: The last message sent
- `last_response`: The last response received
- `agent_id`: The conversation agent ID used
- `timestamp`: The timestamp of the last update
- `conversation_id`: The current conversation ID

## Using the API

The integration also provides an OpenAI-compatible API endpoint that you can use with any client that supports the OpenAI API format. The API is available at:

```
http://your-homeassistant:8337/v1/chat/completions
```

You can use this with OpenAI client libraries by setting the base URL and using your Home Assistant long-lived access token as the API key. 
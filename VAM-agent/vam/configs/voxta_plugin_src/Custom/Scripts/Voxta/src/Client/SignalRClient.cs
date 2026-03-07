using System;
using System.Collections.Generic;
using System.Text;
using SimpleJSON;

public class SignalRClient : IDisposable
{
    private const char _signalREndChar = (char)0x1e;

    private readonly StringBuilder _signalRSplittingBuffer = new StringBuilder();

    private readonly WebSocketClient _ws;

    public bool Connected => _ws.Connected;

    public SignalRClient(WebSocketClient ws)
    {
        _ws = ws;
    }


    public void Connect()
    {
        _ws.Connect();
    }

    public IEnumerable<string> ReadResponse()
    {
        foreach (var response in _ws.ReadResponse())
        {
            if (string.IsNullOrEmpty(response)) continue;

            // If we don't have the end character, we don't have a complete response
            if (response[response.Length - 1] != _signalREndChar)
            {
                _signalRSplittingBuffer.Append(response);
                continue;
            }

            // Build the complete response
            var fullResponse = response;
            if(_signalRSplittingBuffer.Length > 0)
            {
                _signalRSplittingBuffer.Append(fullResponse);
                fullResponse = _signalRSplittingBuffer.ToString();
                _signalRSplittingBuffer.Length = 0;
            }

            var startChar = 0;
            do
            {
                var indexOfEndChar = fullResponse.IndexOf(_signalREndChar, startChar);
                var length = indexOfEndChar - startChar;
                if (indexOfEndChar == -1) break;
                if (length > 1)
                {
                    var chunk = fullResponse.Substring(startChar, length);
                    yield return chunk;
                }
                startChar = indexOfEndChar + 1;
            } while (startChar < fullResponse.Length - 1);


        }
    }

    public JSONNode ParseJson(string response)
    {
        var json = JSON.Parse(response).AsObject;
        if (json == null)
            throw new NullReferenceException($"Voxta: Failed to deserialize JSON. JSON:\n{response}");

        // Sample JSON: {"type":1,"target":"ReceiveMessage","arguments":[DATA]}
        // Message types: https://learn.microsoft.com/en-us/javascript/api/@microsoft/signalr/messagetype?view=signalr-js-latest

        var type = json["type"].Value;
        switch (type)
        {
            case "6":
                // Ping
                _ws.SendMessage(response + _signalREndChar);
                return null;
            case "1":
            {
                // Invocation
                var target = json["target"].Value;
                if(target != "ReceiveMessage")
                {
                    throw new NotSupportedException($"Voxta: Unexpected message target: {target}, received: {json}");
                }
                var arguments = json["arguments"].AsArray;
                if(arguments.Count != 1)
                {
                    throw new NotSupportedException($"Voxta: Unexpected message arguments count, received: {json}");
                }

                return arguments[0];
            }
            case "3":
                var error = json["error"].Value;
                if(!string.IsNullOrEmpty(error))
                    throw new ApplicationException("Voxta: SignalR error: " + error);
                return null;
            default:
                throw new NotSupportedException($"Unexpected SignalR type: {response}");
        }
    }

    public void SendSignalRProtocolHandshake()
    {
        _ws.SendMessage("{\"protocol\":\"json\",\"version\":1}" + _signalREndChar);
    }

    public void SendSignalRMessage(string message)
    {
        var value = "{\"arguments\":[" + message + "],\"target\":\"SendMessage\",\"type\":1}";
        _ws.SendMessage(value + _signalREndChar);
    }

    public void Disconnect()
    {
        _ws.Disconnect();
    }

    public void Dispose()
    {
        _ws.Dispose();
    }
}

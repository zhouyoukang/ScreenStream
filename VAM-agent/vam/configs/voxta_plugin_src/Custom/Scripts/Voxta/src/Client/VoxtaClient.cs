// #define LOG_JSON
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using MVR.FileManagementSecure;
using SimpleJSON;
using UnityEngine.Events;

[SuppressMessage("ReSharper", "AccessToModifiedClosure")]
public sealed class VoxtaClient : IDisposable
{
    public const string ClientName = "Voxta.VirtAMate";

    public class AppTrigger
    {
        public string Name;
        public string[] Arguments;
    }

    public class MissingResource
    {
        public string Id;
        public string Kind;
        public string Version;
        public string Status;
    }

    public class DeployResourceResult
    {
        public bool Success;
        public string Error;

        public string Id;
        public string Version;
        public string Status;
    }

    public class ChatStarted
    {
        public string SessionId;
        public string ChatId;
        public CharacterInfo[] Characters;
    }

    public class CharacterInfo
    {
        public string Id;
        public string Name;
    }

    public class MessageStart
    {
        public string SessionId;
        public string MessageId;
        public string SenderId;
    }

    public class MessageChunk
    {
        public string SessionId;
        public string MessageId;
        public string Text;
        public string AudioUrl;
        public int StartIndex;
        public int EndIndex;
        public string SenderId;
        public bool IsNarration;
        public int? AudioGapMs;
    }

    public class MessageEnd
    {
        public string SessionId;
        public string MessageId;
        public string SenderId;
    }

    public class ServerUpdatedMessage
    {
        public string Text;
        public string Role;
    }

    public readonly StringUnityEvent OnStatusChanged = new StringUnityEvent();
    public readonly BooleanUnityEvent OnConnected = new BooleanUnityEvent();

    public readonly StringUnityEvent OnUserNameAvailable = new StringUnityEvent();
    public readonly CharactersListUnityEvent OnCharactersListReceived = new CharactersListUnityEvent();
    public readonly ScenariosListUnityEvent OnScenariosListReceived = new ScenariosListUnityEvent();
    public readonly ChatsListUnityEvent OnChatsListReceived = new ChatsListUnityEvent();
    public readonly ChatStartedUnityEvent OnChatStartedReceived = new ChatStartedUnityEvent();
    public readonly StringUnityEvent OnChatClosedReceived = new StringUnityEvent();
    public readonly ReplyChunkUnityEvent OnReplyGeneratingReceived = new ReplyChunkUnityEvent();
    public readonly ReplyStartUnityEvent OnReplyStartReceived = new ReplyStartUnityEvent();
    public readonly ReplyChunkUnityEvent OnReplyChunkReceived = new ReplyChunkUnityEvent();
    public readonly ReplyEndUnityEvent OnReplyEndReceived = new ReplyEndUnityEvent();
    public readonly UnityEvent OnServerSpeechRecognitionStart = new UnityEvent();
    public readonly StringUnityEvent OnServerSpeechRecognitionPartial = new StringUnityEvent();
    public readonly StringUnityEvent OnServerSpeechRecognitionEnd = new StringUnityEvent();
    public readonly StringUnityEvent OnActionReceived = new StringUnityEvent();
    public readonly StringArrayUnityEvent OnScenarioFlagsReceived = new StringArrayUnityEvent();
    public readonly AppTriggerUnityEvent OnAppTriggerReceived = new AppTriggerUnityEvent();
    public readonly MissingResourcesUnityEvent OnMissingResourcesReceived = new MissingResourcesUnityEvent();
    public readonly DeployResourceResultUnityEvent OnDeployResourceResultReceived = new DeployResourceResultUnityEvent();
    public readonly MessageUpdatedUnityEvent OnMessageUpdatedReceived = new MessageUpdatedUnityEvent();
    public readonly UnityEvent OnInterruptSpeech = new UnityEvent();
    public readonly StringUnityEvent OnError = new StringUnityEvent();
    public readonly StringUnityEvent OnChatFlow = new StringUnityEvent();

    private readonly ThreadSafeScheduler _scheduler;
    private readonly ThreadSafeLogger _logger;

    public bool IsConnected { get; private set; }

    private readonly SignalRClient _ws;

    public string SessionId;

    private Thread _thread;
    private bool _cancellation;

    public VoxtaClient(IVoxtaCredentials credentials, ThreadSafeScheduler scheduler, ThreadSafeLogger logger)
    {
        if(!credentials.IsValid())
            throw new InvalidOperationException("Invalid host and/or credentials");
        _scheduler = scheduler;
        _logger = logger;
        _ws = new SignalRClient(new WebSocketClient(new IPEndPoint(credentials.Address, credentials.Port), credentials.APIKey));
    }

    public void Connect()
    {
        if (_thread != null) throw new InvalidOperationException("Client was not properly disposed");
        _thread = new Thread(HandleConnectionThread);
        _thread.Start();
    }

    private void HandleConnectionThread()
    {
        while (!_cancellation)
        {
            try
            {
                _scheduler.Enqueue(() => OnStatusChanged.Invoke("Connecting..."));
                _ws.Connect();
                _ws.SendSignalRProtocolHandshake();
                var confirm = _ws.ReadResponse().ToArray().FirstOrDefault();
                if (confirm != "{}") throw new InvalidOperationException("Invalid handshake response, the server is not using SignalR: " + confirm);
                _ws.SendSignalRMessage(new JSONClass
                {
                    ["$type"] = "authenticate",
                    ["client"] = ClientName,
                    ["clientVersion"] = VoxtaVersion.VirtAMatePluginVersion,
                    ["scope"] = new JSONArray
                    {
                        "role:app"
                    },
                    ["capabilities"] = new JSONClass
                    {
                        ["audioOutput"] = "LocalFile",
                        ["audioFolder"] = FileManagerSecure.GetFullPath("Custom\\Sounds\\Voxta").Replace("\\", "\\\\"),
                        ["acceptedAudioContentTypes"] = new JSONArray { "audio/x-wav" }
                    }
                }.ToString());

                _scheduler.Enqueue(() =>
                {
                    OnStatusChanged.Invoke("Authenticating");
                });

                while (!_cancellation && _ws.Connected)
                {
                    // Receive the response from the remote device.
                    foreach (var response in _ws.ReadResponse())
                    {
                        JSONNode json;
                        try
                        {
                            json = _ws.ParseJson(response);
                        }
                        catch (Exception exc)
                        {
                            var error = $"Voxta: Failed to parse JSON. Error: {exc.Message}. JSON:\n{response}";
                            _scheduler.Enqueue(() => SuperController.LogError(error));
                            continue;
                        }

                        if (json == null)
                            continue;

                        ReceiveMessage(json);
                    }
                }
            }
            catch (SocketException e)
            {
                if (_cancellation) return;
                _scheduler.Enqueue(() =>
                {
                    CloseConnection();
                    OnStatusChanged.Invoke(e.Message);
                });
                Thread.Sleep(500);
            }
            catch (Exception e)
            {
                if (_cancellation) return;
                _scheduler.Enqueue(() =>
                {
                    SuperController.LogError($"Voxta: Error while trying to connect to server: {e}");
                    CloseConnection();
                    OnStatusChanged.Invoke(e.Message);
                });
                return;
            }
        }
        _scheduler.Enqueue(CloseConnection);
        _scheduler.Enqueue(() => OnStatusChanged.Invoke("Connection canceled..."));
    }

    private void ReceiveMessage(JSONNode json)
    {
        var type = json["$type"].Value;

        #if (LOG_JSON)
        _logger.Log(() => "Receive: " + json.ToString());
        #endif

        var messageId = json["messageId"].Value;
        var logMsgId = GetMessageIdEnd(messageId);

        switch (type)
        {
            case "welcome":
            {
                var voxtaServerVersion = json["voxtaServerVersion"].Value;
                var apiVersion = json["apiVersion"].Value;
                if (apiVersion != VoxtaVersion.RequiredVoxtaApiVersion)
                {
                    _logger.Error(() => $"Voxta: Server API version is not supported. Expected: {VoxtaVersion.RequiredVoxtaApiVersion}, got: {apiVersion} (Voxta Server version: {voxtaServerVersion}). Make sure you have updated Voxta Server to version {VoxtaVersion.ExpectedVoxtaServerVersion}, or update both the Voxta plugin for Virt-A-Mate and Voxta Server to the latest version.");
                }

                var user = json["user"].AsObject;
                var username = user != null ? user["name"].Value : "";
                if (username != "") _scheduler.Enqueue(() => OnUserNameAvailable.Invoke(username));
                _scheduler.Enqueue(() =>
                {
                    OnStatusChanged.Invoke("Connected");
                    IsConnected = true;
                    OnConnected.Invoke(true);
                });
                break;
            }
            case "charactersListLoaded":
            {
                var characters = json["characters"]
                    .AsArray.Childs
                    .Select(x => new CharacterItem
                    {
                        Id = x["id"].Value,
                        Name = x["name"].Value,
                        CreatorNotes = x["creatorNotes"].Value,
                        PackageId = x["packageId"].Value,
                        PackageName = x["packageName"].Value,
                        PackageVersion = x["packageVersion"].Value,
                    })
                    .ToList();
                _scheduler.Enqueue(() => OnCharactersListReceived.Invoke(characters));
                break;
            }
            case "chatsListLoaded":
            {
                var chats = json["chats"]
                    .AsArray.Childs
                    .Select(x => new ChatItem
                    {
                        Id = x["id"].Value,
                        Created = x["created"].Value,
                    })
                    .ToList();
                _scheduler.Enqueue(() => OnChatsListReceived.Invoke(chats));
                break;
            }
            case "stagesListLoaded":
            {
                _logger.Error(() => "Stages are not supported, this response was unexpected. Make sure you have updated both Voxta Server and the Voxta plugin for Virt-A-Mate.");
                break;
            }
            case "scenariosListLoaded":
            {
                var scenarios = json["scenarios"]
                    .AsArray.Childs
                    .Select(x => new ScenarioItem
                    {
                        Id = x["id"].Value,
                        Name = x["name"].Value,
                        Roles = x["roles"].AsArray?.Childs.Select(y => new ScenarioInfoRole
                        {
                            Name = y["name"].Value,
                            Description = y["description"].Value,
                            DefaultCharacterId = y["defaultCharacterId"].Value,
                        }).ToArray() ?? new ScenarioInfoRole[0],
                        PackageId = x["packageId"].Value,
                        PackageName = x["packageName"].Value,
                        PackageVersion = x["packageVersion"].Value,
                        Client = x["client"].Value,
                    })
                    .ToList();
                _scheduler.Enqueue(() => OnScenariosListReceived.Invoke(scenarios));
                break;
            }
            case "chatInProgress":
                _scheduler.Enqueue(() => SuperController.LogError("Voxta: There is already a chat in progress"));
                break;
            case "chatStarted":
            {
                var chatId = json["chatId"].Value;
                SessionId = json["sessionId"].Value;
                var context = json["context"];
                var updatedFlags = context["flags"].AsArray.Childs.Select(x => x["name"].Value).ToArray();
                var updatedFlagsStr = _logger.Enabled ? string.Join(", ", updatedFlags) : null;
                _logger.Log(() => $"<- Flags updated: {updatedFlagsStr}");

                var chatStarted = new ChatStarted
                {
                    SessionId = SessionId,
                    ChatId = chatId,
                    Characters = context["characters"].AsArray.Childs.Select(x => new CharacterInfo
                    {
                        Id = x["id"].Value,
                        Name = x["name"].Value,
                    }).ToArray(),
                };

                _scheduler.Enqueue(() => OnChatStartedReceived.Invoke(chatStarted));
                _scheduler.Enqueue(() => OnScenarioFlagsReceived.Invoke(updatedFlags));

                var services = json["services"].AsObject;
                if (services != null)
                {
                    var tts = services["textToSpeech"].AsObject;
                    if (tts == null || string.IsNullOrEmpty(tts["serviceName"].Value))
                        _logger.Error(() => "Text-to-speech service is disabled, you won't hear the characters speaking");
                    var stt = services["speechToText"].AsObject;
                    if (stt == null || string.IsNullOrEmpty(stt["serviceName"].Value))
                        _logger.Error(() => "Speech-to-text service is disabled, you won't be able to speak to the characters");
                    var actionInference = services["actionInference"].AsObject;
                    if (actionInference == null || string.IsNullOrEmpty(actionInference["serviceName"].Value))
                        _logger.Error(() => "Action inference service is disabled, the characters won't be able to make actions");
                }

                break;
            }
            case "chatConfiguration":
                break;
            case "chatClosed":
                SessionId = null;
                _scheduler.Enqueue(() => OnChatClosedReceived.Invoke(json["chatId"]));
                break;
            case "replyGenerating":
            {
                var sessionId = json["sessionId"].Value;
                var senderId = json["senderId"].Value;
                var isNarration = json["isNarration"].AsBool;
                var chunk = new MessageChunk
                {
                    SessionId = sessionId,
                    MessageId = messageId,
                    SenderId = senderId,
                    AudioUrl = json["thinkingSpeechUrl"].Value,
                    IsNarration = isNarration,
                };
                _logger.Log(() => $"<- {{{logMsgId}}} generating (by {senderId})");
                _scheduler.Enqueue(() => OnReplyGeneratingReceived.Invoke(chunk));
                break;
            }
            case "replyStart":
            {
                var sessionId = json["sessionId"].Value;
                var senderId = json["senderId"].Value;
                var start = new MessageStart
                {
                    SessionId = sessionId,
                    MessageId = messageId,
                    SenderId = senderId,
                };
                _logger.Log(() => $"<- {{{logMsgId}}} start");
                _scheduler.Enqueue(() => OnReplyStartReceived.Invoke(start));
                break;
            }
            case "replyChunk":
            {
                var sessionId = json["sessionId"].Value;
                var senderId = json["senderId"].Value;
                var text = json["text"].Value;
                var startIndex = json["startIndex"].AsInt;
                var endIndex = json["endIndex"].AsInt;
                var isNarration = json["isNarration"].AsBool;
                var audioGapMs = json["audioGapMs"].AsInt;
                var chunk = new MessageChunk
                {
                    SessionId = sessionId,
                    MessageId = messageId,
                    SenderId = senderId,
                    Text = text,
                    AudioUrl = json["audioUrl"].Value,
                    StartIndex = startIndex,
                    EndIndex = endIndex,
                    IsNarration = isNarration,
                    AudioGapMs = audioGapMs,
                };
                var excerpt = _logger.Enabled ? Excerpt(text) : null;
                _logger.Log(() => $"<- {{{logMsgId}}} chunk [{startIndex}..{endIndex}]: {excerpt}");
                _scheduler.Enqueue(() => OnReplyChunkReceived.Invoke(chunk));
                break;
            }
            case "replyEnd":
            {
                var sessionId = json["sessionId"].Value;
                var senderId = json["senderId"].Value;
                var end = new MessageEnd
                {
                    SessionId = sessionId,
                    MessageId = messageId,
                    SenderId = senderId,
                };
                _logger.Log(() => $"<- {{{logMsgId}}} end");
                _scheduler.Enqueue(() => OnReplyEndReceived.Invoke(end));
                break;
            }
            case "replyCancelled":
                break;
            case "speechRecognitionStart":
                _scheduler.Enqueue(() => OnServerSpeechRecognitionStart.Invoke());
                break;
            case "speechRecognitionPartial":
                var partialText = json["text"].Value;
                if (partialText == "null") partialText = "";
                _scheduler.Enqueue(() => OnServerSpeechRecognitionPartial.Invoke(partialText));
                break;
            case "speechRecognitionEnd":
                var finalText = json["text"].Value;
                if (!string.IsNullOrEmpty(finalText) && finalText != "null")
                    _scheduler.Enqueue(() => OnServerSpeechRecognitionEnd.Invoke(finalText));
                else
                    _scheduler.Enqueue(() => OnServerSpeechRecognitionPartial.Invoke(""));
                break;
            case "speechPlaybackStart":
            {
                _logger.Log(() => $"<- {{{logMsgId}}} playback start");
                break;
            }
            case "speechPlaybackComplete":
            {
                _logger.Log(() => $"<- {{{logMsgId}}} playback complete");
                break;
            }
            case "action":
            {
                var value = json["value"].Value;
                if (!string.IsNullOrEmpty(value))
                {
                    _logger.Log(() => $"<- Action: {value}");
                    _scheduler.Enqueue(() => OnActionReceived.Invoke(value));
                }
                break;
            }
            case "appTrigger":
            {
                var name = json["name"].Value;
                var arguments = json["arguments"].AsArray.Childs.Select(x => x.Value).ToArray();
                var appTrigger = new AppTrigger { Name = name, Arguments = arguments };
                var argStr = _logger.Enabled ? string.Join(", ", arguments) : null;
                _logger.Log(() => $"<- App trigger: {name}({argStr})");
                _scheduler.Enqueue(() => OnAppTriggerReceived.Invoke(appTrigger));
                break;
            }
            case "contextUpdated":
            {
                var updatedFlags = json["flags"].AsArray.Childs.Select(x => x["name"].Value).ToArray();
                var updatedFlagsStr = _logger.Enabled ? string.Join(", ", updatedFlags) : null;
                _logger.Log(() => $"<- Flags updated: {updatedFlagsStr}");
                _scheduler.Enqueue(() => OnScenarioFlagsReceived.Invoke(updatedFlags));
                break;
            }
            case "chatFlow":
            {
                var state = json["state"].Value;
                _logger.Log(() => $"<- Chat flow: {state}");
                _scheduler.Enqueue(() => OnChatFlow.Invoke(state));
                break;
            }
            case "error":
            case "chatSessionError":
            {
                var message = json["message"].Value;
                var code = json["code"].Value;
                var serviceName = json["serviceName"].Value;
                if (!string.IsNullOrEmpty(code))
                    _logger.Error(() => $"Server error: {code} (Service: {serviceName}, Details: {message})");
                else
                    _logger.Error(() => $"Server error: {message}");
                _scheduler.Enqueue(() => OnError.Invoke(message));
                break;
            }
            case "missingResourcesError":
            {
                var x = json["resources"].AsArray;
                var missingResources = new MissingResource[x.Count];
                for (var i = 0; i < x.Count; i++)
                {
                    var resourceJson = x[i].AsObject;
                    var missingResource = new MissingResource
                    {
                        Id = resourceJson["id"].Value,
                        Kind = resourceJson["kind"].Value,
                        Version = resourceJson["version"].Value,
                        Status = resourceJson["status"].Value,
                    };
                    missingResources[i] = missingResource;
                }
                _scheduler.Enqueue(() => OnMissingResourcesReceived.Invoke(missingResources));
                break;
            }
            case "recordingStatus":
            {
                var recordingStr = _logger.Enabled ? json["enabled"].Value : null;
                _logger.Log(() => $"<- Recording: {recordingStr}");
                break;
            }
            case "interruptSpeech":
                _scheduler.Enqueue(() => OnInterruptSpeech.Invoke());
                break;
            case "update":
            {
                var update = new ServerUpdatedMessage
                {
                    Text = json["text"].Value,
                    Role = json["role"].Value,
                };
                _scheduler.Enqueue(() => OnMessageUpdatedReceived.Invoke(update));
                break;
            }
            case "configuration":
            {
                var configurations = json["configurations"].AsArray;
                if (configurations == null)
                {
                    // Obsolete (older format before 2025-08)
                    var services = json["services"].AsObject;
                    var tts = services["TextToSpeech"].AsObject;
                    if (!tts["enabled"].AsBool)
                        _logger.Error(() => "Text-to-speech service is disabled on the server, you won't hear the characters speaking");
                    var stt = services["SpeechToText"].AsObject;
                    if (!stt["enabled"].AsBool)
                        _logger.Error(() => "Speech-to-text service is disabled on the server, you won't be able to speak to the characters");
                    var actionInference = services["ActionInference"].AsObject;
                    if (!actionInference["enabled"].AsBool)
                        _logger.Error(() => "Action inference service is disabled on the server, the characters won't be able to make actions");
                }
                break;
            }
            case "chatLoading":
            case "memoryUpdated":
            case "chatParticipantsUpdated":
            case "chatsSessionsUpdated":
            case "chatPaused":
            case "audioFrame":
            case "wakeWordStatus":
            case "listResourcesResult":
                break;
            case "recordingRequest":
            {
                _logger.Error(() => $"<- Recording request received but VaM does not support client app recording capability.");
                break;
            }
            case "visionCaptureRequest":
            {
                _logger.Error(() => $"<- Vision capture request received but VaM does not support client app vision capture capability.");
                break;
            }
            case "deployResourceResult":
            {
                var result = new DeployResourceResult
                {
                    Success = json["success"].AsBool,
                    Error = json["error"].Value,
                    Id = json["id"].Value,
                    Version = json["version"].Value,
                    Status = json["status"].Value,
                };
                _scheduler.Enqueue(() => OnDeployResourceResultReceived.Invoke(result));
                break;
            }

            case "moduleRuntimeInstances":
            {
                _logger.Log(() => "Voxta: Server is initializing modules...");
                break;
            }
            case "downloadProgress":
            {
                _logger.Log(() => "Voxta: Resource download in progress...");
                break;
            }
            case "inspectorEnabled":
            case "inspectorScriptExecuted":
            case "inspectorActionExecuted":
            case "inspectorScenarioEventExecuted":
                break;

            default:
                _logger.Error(() => $"Unknown message type: {type}, maybe the plugin version is out of date?");
                break;
        }
    }

    public void LoadScenarios()
    {
        Send("{ \"$type\": \"loadScenariosList\" }");
    }

    public void LoadCharacters()
    {
        Send("{ \"$type\": \"loadCharactersList\" }");
    }

    public void LoadChats(string scenarioId, string characterId)
    {
        var json = new JSONClass
        {
            ["$type"] = "loadChatsList",
            ["characterId"] = characterId,
        };
        if (!string.IsNullOrEmpty(scenarioId))
            json["scenarioId"] = scenarioId;
        Send(json.ToString());
    }

    public void UpdateContext(JSONArray actions, string context, string contextKey)
    {
        if(!IsSessionValid()) return;
        var json = new JSONClass
        {
            ["$type"] = "updateContext",
            ["sessionId"] = SessionId,
            ["contextKey"] = contextKey,
        };
        if (context != null)
        {
            _logger.Log(() => $"Update Context: {context} ({contextKey})");
            if (context == "")
                json["contexts"] = new JSONArray();
            else
                json["contexts"] = new JSONArray { new JSONClass { { "text", context } } };
        }

        if (actions != null)
        {
            _logger.Log(() => $"Update Actions: {actions}");
            json["actions"] = actions;
        }

        Send(json.ToString());
    }

    public void SendChatMessage(string text, bool doReply, bool doCharacterActionInference)
    {
        if(!IsSessionValid()) return;
        var excerpt = _logger.Enabled ? Excerpt(text) : null;
        _logger.Log(() => $"-> Send: {excerpt}");
        var json = new JSONClass
        {
            ["$type"] = "send",
            ["sessionId"] = SessionId,
            ["text"] = text,
            ["doReply"] = doReply.ToString(CultureInfo.InvariantCulture),
            ["doCharacterActionInference"] = doCharacterActionInference.ToString(CultureInfo.InvariantCulture),
        };
        Send(json.ToString());
    }

    public void SendRequestCharacterSpeechMessage(string text)
    {
        if(!IsSessionValid()) return;
        _logger.Log(() => $"-> Speech request: {text}");
        Send(new JSONClass
        {
            ["$type"] = "characterSpeechRequest",
            ["sessionId"] = SessionId,
            ["text"] = text,
        }.ToString());
    }

    public void StartChat(JSONClass json)
    {
        SessionId = null;
        // TODO: Use BassImporter to make this work
        // acceptedAudioContentTypes.Add("audio/mpeg");

        json["$type"] = "startChat";
        Send(json.ToString());
    }

    public void StopChat()
    {
        Send("{ \"$type\": \"stopChat\" }");
    }

    public void SpeechPlaybackStart(MessageChunk chunk, float duration)
    {
        if(chunk.SessionId != SessionId) return;
        var messageId = chunk.MessageId;
        var logMsgId = GetMessageIdEnd(messageId);
        var excerpt = _logger.Enabled ? Excerpt(chunk.Text) : null;
        _logger.Log(() => $"-> {{{logMsgId}}} Speech ({duration:0.00}s): {excerpt}");
        Send("{ \"$type\": \"speechPlaybackStart\", \"sessionId\": \"" + SessionId + "\", \"messageId\": \"" + messageId + "\", \"startIndex\": " + chunk.StartIndex + ", \"endIndex\": " + chunk.EndIndex + ", \"duration\": " + duration.ToString("0.000") + ", \"isNarration\": \"" + chunk.IsNarration + "\" }");
    }

    public void SpeechPlaybackComplete(string messageId)
    {
        if (string.IsNullOrEmpty(SessionId)) return;
        var logMsgId = GetMessageIdEnd(messageId);
        _logger.Log(() => $"-> {{{logMsgId}}} Speech complete");
        Send("{ \"$type\": \"speechPlaybackComplete\", \"sessionId\": \"" + SessionId + "\", \"messageId\": \"" + messageId + "\" }");
    }

    public void SendRevertLastSentMessage()
    {
        if (string.IsNullOrEmpty(SessionId)) return;
        Send("{ \"$type\": \"revert\", \"sessionId\": \"" + SessionId + "\" }");
    }

    public void SendDeleteChat(string chatId)
    {
        _logger.Log(() => $"Delete chat {chatId}");
        Send("{ \"$type\": \"deleteChat\", \"chatId\": \"" + chatId + "\" }");
    }

    public void SendDeployResource(MissingResource resource, string name, byte[] bytes)
    {
        var json = new JSONClass
        {
            ["$type"] = "deployResource",
            ["id"] = resource.Id,
            ["data"] = new JSONClass
            {
                ["$type"] = "base64",
                ["name"] = name,
                ["base64Data"] = Convert.ToBase64String(bytes),
            },
        };
        Send(json.ToString());
    }

    public void SendSetFlags(string val)
    {
        if (string.IsNullOrEmpty(SessionId)) return;
        var splitFlags = val.Split(',').Select(x => x.Trim()).Where(x => x != "").ToArray();
        var setFlags = new JSONArray();
        foreach(var splitFlag in splitFlags)
            setFlags.Add(splitFlag);
        var setFlagsStr = setFlags.ToString();
        _logger.Log(() => $"-> Flags: {setFlagsStr}");
        Send("{ \"$type\": \"updateContext\", \"sessionId\": \"" + SessionId + "\", \"setFlags\": " + setFlagsStr + " }");
    }

    private void Send(string value)
    {
        if (_cancellation) return;
        if (!_ws.Connected) throw new InvalidOperationException("Socket is not connected");
        #if (LOG_JSON)
        _logger.Log(() => "Send: " + value);
        #endif
        _ws.SendSignalRMessage(value);
    }

    private bool IsSessionValid()
    {
        if (!string.IsNullOrEmpty(SessionId)) return true;
        _logger.Log(() => "Voxta: Message dropped because there is no active session.");
        return false;
    }

    public void Disconnect()
    {
        if (_cancellation) return;
        _cancellation = true;
        OnStatusChanged.Invoke("User disconnected");

        var sw = new Stopwatch();
        sw.Start();

        CloseConnection();

        if(sw.ElapsedMilliseconds > 500) SuperController.LogError($"Voxta: Took {sw.ElapsedMilliseconds}ms to send the close frame");
        sw.Reset();
        sw.Start();

        if (_thread != null)
        {
            if(!_thread.Join(2000))
                _thread.Abort();
            _thread = null;
        }

        if(sw.ElapsedMilliseconds > 500) SuperController.LogError($"Voxta: Took {sw.ElapsedMilliseconds}ms to complete the close handshake and release the thread");
    }

    private void CloseConnection()
    {
        IsConnected = false;

        if (_ws?.Connected == true)
        {
            try
            {
                _ws.Disconnect();
            }
            catch
            {
                // ignored
            }
        }

        OnConnected.Invoke(false);
        OnStatusChanged.Invoke("Disconnected");
    }

    private string Excerpt(string value, int maxLength = 50)
    {
        if (!_logger.Enabled) return null;
        if (value == null)
            return null;
        if (value.Length <= maxLength)
            return value;
        return value.Substring(0, maxLength) + "...";
    }

    private string GetMessageIdEnd(string value)
    {
        if (!_logger.Enabled) return null;
        if (value == null) return null;
        if (value == "") return null;
        return value.Substring(value.Length - 4);
    }

    public void Dispose()
    {
        _ws.Dispose();
    }

    public interface IResourceItem
    {
        string Id { get; }
        string Name { get; }
        string PackageId { get; }
        string PackageName { get; }
        string PackageVersion { get; set; }
    }

    public class CharacterItem : IResourceItem
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string CreatorNotes { get; set; }
        public string PackageId { get; set; }
        public string PackageName { get; set; }
        public string PackageVersion { get; set; }
    }

    public class ScenarioItem : IResourceItem
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public ScenarioInfoRole[] Roles { get; set; }
        public string Client { get; set; }
        public string PackageId { get; set; }
        public string PackageName { get; set; }
        public string PackageVersion { get; set; }
    }

    public class ScenarioInfoRole
    {
        public string Name;
        public string Description;
        public string DefaultCharacterId;
    }

    public struct ChatItem
    {
        public string Id;
        public string Created;
    }

    public class StringUnityEvent : UnityEvent<string> { }
    public class BooleanUnityEvent : UnityEvent<bool> { }
    public class CharactersListUnityEvent : UnityEvent<List<CharacterItem>> { }
    public class ScenariosListUnityEvent : UnityEvent<List<ScenarioItem>> { }
    public class ChatsListUnityEvent : UnityEvent<List<ChatItem>> { }
    public class ChatStartedUnityEvent : UnityEvent<ChatStarted> { }
    public class JsonUnityEvent : UnityEvent<JSONClass> { }
    public class StringArrayUnityEvent : UnityEvent<string[]> { }
    public class ReplyStartUnityEvent : UnityEvent<MessageStart> { }
    public class ReplyChunkUnityEvent : UnityEvent<MessageChunk> { }
    public class ReplyEndUnityEvent : UnityEvent<MessageEnd> { }
    public class AppTriggerUnityEvent : UnityEvent<AppTrigger> { }
    public class MissingResourcesUnityEvent : UnityEvent<MissingResource[]> { }
    public class DeployResourceResultUnityEvent : UnityEvent<DeployResourceResult> { }
    public class MessageUpdatedUnityEvent : UnityEvent<ServerUpdatedMessage> { }
}

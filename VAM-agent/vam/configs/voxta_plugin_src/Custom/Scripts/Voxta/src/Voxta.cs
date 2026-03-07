using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using MVR.FileManagementSecure;
using SimpleJSON;
using UnityEngine;

public class Voxta : MVRScript
{
    private static class States
    {
        public const string Off = "off";
        public const string Idle = "idle";
        public const string Listening = "listening";
        public const string Thinking = "thinking";
        public const string Speaking = "speaking";
    }

    private VoxtaClient _client;
    private bool _initialized;

    private UI _ui;

    private readonly ThreadSafeScheduler _scheduler;
    private readonly ThreadSafeLogger _logger;

    private readonly VoxtaCredentials _credentials = new VoxtaCredentials();

    private readonly JSONStorableBool _activeJSON = new JSONStorableBool("Active", false);

    private readonly JSONStorableStringChooser _character1JSON = new JSONStorableStringChooser("Character ID", new List<string>(), "", "Select Character");
    private readonly JSONStorableString _character1RoleJSON = new JSONStorableString("Character Role 1", "");
    private readonly JSONStorableString _character1NameJSON = new JSONStorableString("Character Name 1", "");
    private readonly JSONStorableStringChooser _character2JSON = new JSONStorableStringChooser("Character 2", new List<string>(), "", "Select Character");
    private readonly JSONStorableString _character2RoleJSON = new JSONStorableString("Character Role 2", "");
    private readonly JSONStorableString _character2NameJSON = new JSONStorableString("Character Name 2", "");
    private readonly JSONStorableStringChooser _character3JSON = new JSONStorableStringChooser("Character 3", new List<string>(), "", "Select Character");
    private readonly JSONStorableString _character3RoleJSON = new JSONStorableString("Character Role 3", "");
    private readonly JSONStorableString _character3NameJSON = new JSONStorableString("Character Name 3", "");

    private readonly JSONStorableStringChooser _scenarioJSON = new JSONStorableStringChooser("Scenario ID", new List<string>(), "", "Select Scenario");
    private readonly JSONStorableString _scenarioNameJSON = new JSONStorableString("Scenario Name", "");
    private readonly JSONStorableStringChooser _chatJSON = new JSONStorableStringChooser("Chat ID", new List<string>(), "", "Select Chat");

    private readonly JSONStorableUrl _packagePathJSON = new JSONStorableUrl("Package Path", "");
    private readonly JSONStorableString _packageIdJSON = new JSONStorableString("Package ID", "");
    private readonly JSONStorableString _packageVersionJSON = new JSONStorableString("Package Version", "");

    private readonly JSONStorableBool _connectedJSON = new JSONStorableBool("Connected", false) { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _lastErrorJSON = new JSONStorableString("Last Error", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableBool _errorJSON = new JSONStorableBool("Error", false) { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _statusJSON = new JSONStorableString("Status", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableBool _readyJSON = new JSONStorableBool("Ready", false) { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _userNameJSON = new JSONStorableString("User Name", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _userMessageJSON = new JSONStorableString("LastUserMessage", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _characterMessageJSON = new JSONStorableString("LastCharacterMessage", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _setFlags = new JSONStorableString("SetFlags", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _flags = new JSONStorableString("Flags", "") { isStorable = false, isRestorable = false };

    private readonly JSONStorableStringChooser _stateJSON = new JSONStorableStringChooser("State", new List<string>
    {
        States.Off,
        States.Idle,
        States.Listening,
        States.Thinking,
        States.Speaking,
    }, States.Off, "Last State") { isStorable = false, isRestorable = false };
    private readonly JSONStorableBool _autoSendRecognizedSpeech = new JSONStorableBool("AutoSendRecognizedSpeech", true);
    private readonly JSONStorableString _triggerMessage = new JSONStorableString("TriggerMessage", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _requestCharacterSpeech = new JSONStorableString("RequestCharacterSpeech", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _currentAction = new JSONStorableString("CurrentAction", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _actionsListJSON = new JSONStorableString("ActionsList", "");
    private readonly JSONStorableString _actionsList1JSON = new JSONStorableString("ActionsList (Slot 1)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _actionsList2JSON = new JSONStorableString("ActionsList (Slot 2)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _actionsList3JSON = new JSONStorableString("ActionsList (Slot 3)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _actionsList4JSON = new JSONStorableString("ActionsList (Slot 4)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _contextJSON = new JSONStorableString("Context", "");
    private readonly JSONStorableString _context1JSON = new JSONStorableString("Context (Slot 1)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _context2JSON = new JSONStorableString("Context (Slot 2)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _context3JSON = new JSONStorableString("Context (Slot 3)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableString _context4JSON = new JSONStorableString("Context (Slot 4)", "") { isStorable = false, isRestorable = false };
    private readonly JSONStorableBool _characterCanSpeak = new JSONStorableBool("CharacterCanSpeak", true);
    private readonly JSONStorableBool _enableLogsJSON = new JSONStorableBool("Enable Logs", false) { isStorable = false, isRestorable = false };

    private AudioAtomTarget _audioAtomTarget1;
    private AudioAtomTarget _audioAtomTarget2;
    private AudioAtomTarget _audioAtomTarget3;
    private AudioAtomTarget _audioAtomNarrator;
    private SpeechPlayback _speechPlayback;

    private SubtitlesAtomTarget _subtitles;

    private JSONStorableAction _deleteCurrentChat;
    private JSONStorableAction _startNewChat;
    private JSONStorableAction _revertLastSentMessage;
    private JSONStorableAction _clearContext;
    private JSONStorableAction _enableLipSyncAction;
    private JSONArray _actions = new JSONArray();
    private JSONArray _actions1 = new JSONArray();
    private JSONArray _actions2 = new JSONArray();
    private JSONArray _actions3 = new JSONArray();
    private JSONArray _actions4 = new JSONArray();

    private bool _restored;
    private string _varPrefix = "";

    private SimpleTrigger _onChatLoadingSessionTrigger;
    private SimpleTrigger _onChatSessionTrigger;
    private SimpleTrigger _onStateChangedTrigger;
    private SimpleTrigger _onSpeakTrigger;
    private SimpleTrigger _isSpeakingTrigger;
    private SimpleTrigger _onActionTrigger;
    private List<VoxtaClient.ScenarioItem> _scenarios;
    private List<VoxtaClient.CharacterItem> _characters;
    private readonly List<VoxtaClient.MissingResource> _pendingResources = new List<VoxtaClient.MissingResource>();
    private readonly List<string> _pendingFlags = new List<string>();

    public Voxta()
    {
        _scheduler = new ThreadSafeScheduler();
        _logger = new ThreadSafeLogger(_scheduler, _enableLogsJSON);
    }

    public override void Init()
    {
        if (Input.GetKey(KeyCode.LeftControl) && Input.GetKey(KeyCode.LeftShift) && Input.GetKey(KeyCode.LeftAlt))
            _enableLogsJSON.val = true;

        // Not var: Saves/scene/Voxta
        // Var: AcidBubbles.SceneName.1:/Saves/scene/Voxta
        var indexOfVarDelimiter = SuperController.singleton.currentLoadDir != null ? SuperController.singleton.currentLoadDir.IndexOf(":/", StringComparison.Ordinal) : -1;
        _varPrefix = indexOfVarDelimiter != -1 ? SuperController.singleton.currentLoadDir?.Substring(0, indexOfVarDelimiter + 2) ?? "" : "";

        _deleteCurrentChat = new JSONStorableAction("Delete Current Chat", DeleteCurrentChat);
        _startNewChat = new JSONStorableAction("Start New Chat", StartNewChat);
        _revertLastSentMessage = new JSONStorableAction("Revert Last Sent Message", () =>
        {
            if (!_activeJSON.val || !_readyJSON.val)
                return;
            _client.SendRevertLastSentMessage();
        });

        _enableLipSyncAction = new JSONStorableAction("EnableLipSync", EnableLipSync);

        _clearContext = new JSONStorableAction("Clear Context", () =>
        {
            _contextJSON.val = "";
            _context1JSON.val = "";
            _context2JSON.val = "";
            _context3JSON.val = "";
            _context4JSON.val = "";
            _actionsListJSON.val = "";
            _actionsList1JSON.val = "";
            _actionsList2JSON.val = "";
            _actionsList3JSON.val = "";
            _actionsList4JSON.val = "";
        });

        _stateJSON.setCallbackFunction = val =>
        {
            Invoke(nameof(InvokeOnStateChangedTrigger), 0);
        };

        _onChatSessionTrigger = new SimpleTrigger("Chat Started", "Chat Closed");
        _onChatLoadingSessionTrigger = new SimpleTrigger("Chat Loading Start", "Chat Loading End");
        _onStateChangedTrigger = new SimpleTrigger("On State Changed", null);
        _onSpeakTrigger = new SimpleTrigger("On Speak", null);
        _isSpeakingTrigger = new SimpleTrigger("On Speech Start", "On Speech End");
        _onActionTrigger = new SimpleTrigger("On Action", null);

        _setFlags.setCallbackFunction = val =>
        {
            _setFlags.valNoCallback = "";
            if (!_activeJSON.val)
                return;
            if (!_readyJSON.val)
            {
                _pendingFlags.Add(val);
                return;
            }
            _client.SendSetFlags(val);
        };

        _speechPlayback = new SpeechPlayback(this, _credentials, _logger);
        _speechPlayback.OnPlaybackStarting.AddListener(speech =>
        {
            _isSpeakingTrigger.Trigger.active = true;
            if (string.IsNullOrEmpty(speech.Chunk.Text)) return;
            _characterMessageJSON.val = speech.Chunk.Text;
            _stateJSON.val = States.Speaking;
            if (speech.Chunk.SenderId == _character1JSON.val)
            {
                _subtitles.Show(_character1NameJSON.val, speech.Chunk.Text);
            }
            else if (speech.Chunk.SenderId == _character2JSON.val)
            {
                _subtitles.Show(_character2NameJSON.val, speech.Chunk.Text);
            }
            else if (speech.Chunk.SenderId == _character3JSON.val)
            {
                _subtitles.Show(_character3NameJSON.val, speech.Chunk.Text);
            }
            else
            {
                _subtitles.Show("", speech.Chunk.Text);
            }
            InvokeOnSpeakTrigger();
            if (_readyJSON.val)
                _client.SpeechPlaybackStart(speech.Chunk, speech.Duration);
        });
        _speechPlayback.OnPlaybackCompleted.AddListener(messageId =>
        {
            _stateJSON.val = States.Idle;
            _isSpeakingTrigger.Trigger.active = false;
            if (_readyJSON.val)
                _client.SpeechPlaybackComplete(messageId);
        });

        _audioAtomTarget1 = new AudioAtomTarget(this);
        _audioAtomTarget2 = new AudioAtomTarget(this, "EXPERIMENTAL_Secondary");
        _audioAtomTarget3 = new AudioAtomTarget(this, "EXPERIMENTAL_Tertiary");
        _audioAtomNarrator = new AudioAtomTarget(this, "Narrator");

        _subtitles = new SubtitlesAtomTarget(this);

        _credentials.OnChanged.AddListener(ReconnectToServer);

        _readyJSON.setCallbackFunction = val =>
        {
            if (!val)
            {
                _isSpeakingTrigger.Trigger.active = false;
                _speechPlayback.Interrupt();
                _audioAtomTarget1.AudioSource?.Stop();
                _audioAtomTarget2.AudioSource?.Stop();
                _audioAtomTarget3.AudioSource?.Stop();
                _audioAtomNarrator.AudioSource?.Stop();
                _stateJSON.val = States.Off;
                _flags.valNoCallback = "";
                _client.SessionId = null;
            }
            else
            {
                _onChatLoadingSessionTrigger.SetActive(false);
            }
            _onChatSessionTrigger.SetActive(val);
        };

        _scenarioJSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            _chatJSON.val = "";
            if (val == "")
            {
                _scenarioNameJSON.val = "";
            }
            else
            {
                var scenario = _scenarios?.FirstOrDefault(s => s.Id == val);
                if (scenario == null)
                {
                    SuperController.LogError($"Voxta: Scenario {val} not found in list");
                    _scenarioNameJSON.val = val;
                }
                else
                {
                    _scenarioNameJSON.val = scenario.Name;

                }
            }

            _activeJSON.val = false;
            AssignRolesFromScenario(val);
            RefreshChatsList();
            RefreshPackageLink();
        };

        _character1JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;

            if (val == "")
            {
                _character1NameJSON.val = "";
            }
            else
            {
                var character = _characters?.FirstOrDefault(s => s.Id == val);
                if (character == null)
                {
                    SuperController.LogError($"Voxta: Character {val} not found in list");
                    _character1NameJSON.val = val;
                }
                else
                {
                    _character1NameJSON.val = character.Name;
                }
            }

            _activeJSON.val = false;
            RefreshChatsList();
            RefreshPackageLink();
        };

        _character2JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;

            if (val == "")
            {
                _character2NameJSON.val = "";
            }
            else
            {
                var character = _characters?.FirstOrDefault(s => s.Id == val);
                if (character == null)
                {
                    SuperController.LogError($"Voxta: Character {val} not found in list");
                    _character2NameJSON.val = val;
                }
                else
                {
                    _character2NameJSON.val = character.Name;
                }
            }
        };

        _character3JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;

            if (val == "")
            {
                _character3NameJSON.val = "";
            }
            else
            {
                var character = _characters?.FirstOrDefault(s => s.Id == val);
                if (character == null)
                {
                    SuperController.LogError($"Voxta: Character {val} not found in list");
                    _character3NameJSON.val = val;
                }
                else
                {
                    _character3NameJSON.val = character.Name;
                }
            }
        };

        _chatJSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            _activeJSON.val = false;
        };

        _triggerMessage.setCallbackFunction = val =>
        {
            _triggerMessage.valNoCallback = "";
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            val = val.Trim();
            if (val == "") return;
            if (val[0] != '/')
            {
                _speechPlayback.Interrupt();
                _audioAtomTarget1.AudioSource?.Stop();
                _audioAtomTarget2.AudioSource?.Stop();
                _audioAtomTarget3.AudioSource?.Stop();
                _audioAtomNarrator.AudioSource?.Stop();
                if (val[0] != '[')
                {
                    _userMessageJSON.val = val;
                }
            }
            _client.SendChatMessage(val, _characterCanSpeak.val, true);
        };

        _requestCharacterSpeech.setCallbackFunction = val =>
        {
            _requestCharacterSpeech.valNoCallback = "";
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.SendRequestCharacterSpeechMessage(val.Trim());
        };

        _contextJSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.UpdateContext(null, val.Trim(), "VaM/Base");
        };

        _context1JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.UpdateContext(null, val.Trim(), "VaM/Slot1");
        };

        _context2JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.UpdateContext(null, val.Trim(), "VaM/Slot2");
        };

        _context3JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.UpdateContext(null, val.Trim(), "VaM/Slot3");
        };

        _context4JSON.setCallbackFunction = val =>
        {
            if (!_initialized) return;
            if (!_readyJSON.val) return;
            _client.UpdateContext(null, val.Trim(), "VaM/Slot4");
        };

        _activeJSON.setCallbackFunction = val =>
        {
            _errorJSON.val = false;
            if (!_initialized) return;

            _speechPlayback.Interrupt();
            _audioAtomTarget1.AudioSource?.Stop();
            _audioAtomTarget2.AudioSource?.Stop();
            _audioAtomTarget3.AudioSource?.Stop();
            _audioAtomNarrator.AudioSource?.Stop();
            _readyJSON.val = false;
            _onChatLoadingSessionTrigger.SetActive(false);
            if (!_client.IsConnected) return;
            if (val)
                TryStartChat();
            else
                _client.StopChat();
        };

        _actionsListJSON.setCallbackFunction = val =>
        {
            _actions = ActionsParser.Parse(val);
            if (!_initialized) return;
            if (!_client.IsConnected) return;
            _client.UpdateContext(_actions, null, "VaM/Base");
        };

        _actionsList1JSON.setCallbackFunction = val =>
        {
            _actions1 = ActionsParser.Parse(val);
            if (!_initialized) return;
            if (!_client.IsConnected) return;
            _client.UpdateContext(_actions1, null, "VaM/Slot1");
        };

        _actionsList2JSON.setCallbackFunction = val =>
        {
            _actions2 = ActionsParser.Parse(val);
            if (!_initialized) return;
            if (!_client.IsConnected) return;
            _client.UpdateContext(_actions2, null, "VaM/Slot2");
        };

        _actionsList3JSON.setCallbackFunction = val =>
        {
            _actions3 = ActionsParser.Parse(val);
            if (!_initialized) return;
            if (!_client.IsConnected) return;
            _client.UpdateContext(_actions3, null, "VaM/Slot3");
        };

        _actionsList4JSON.setCallbackFunction = val =>
        {
            _actions4 = ActionsParser.Parse(val);
            if (!_initialized) return;
            if (!_client.IsConnected) return;
            _client.UpdateContext(_actions4, null, "VaM/Slot4");
        };

        _credentials.Initialize();
        _audioAtomTarget1.Initialize(containingAtom.GetStorableByID("HeadAudioSource") as AudioSourceControl);
        _audioAtomTarget2.Initialize(null);
        _audioAtomTarget3.Initialize(null);
        _audioAtomNarrator.Initialize(null);

        _subtitles.Initialize();

        RegisterAction(new JSONStorableAction("# Voxta Main Controls:", () => { }));
        RegisterBool(_activeJSON);
        RegisterAction(new JSONStorableAction("# Voxta Actions:", () => { }));
        RegisterString(_triggerMessage);
        RegisterString(_requestCharacterSpeech);
        RegisterString(_setFlags);
        RegisterAction(new JSONStorableAction("# Voxta Context and Actions:", () => { }));
        RegisterString(_contextJSON);
        RegisterString(_context1JSON);
        RegisterString(_context2JSON);
        RegisterString(_context3JSON);
        RegisterString(_context4JSON);
        RegisterString(_actionsListJSON);
        RegisterString(_actionsList1JSON);
        RegisterString(_actionsList2JSON);
        RegisterString(_actionsList3JSON);
        RegisterString(_actionsList4JSON);
        RegisterAction(_clearContext);
        RegisterAction(new JSONStorableAction("# Voxta State:", () => { }));
        RegisterBool(_connectedJSON);
        RegisterBool(_errorJSON);
        RegisterString(_userNameJSON);
        RegisterString(_lastErrorJSON);
        RegisterStringChooser(_stateJSON);
        RegisterString(_flags);
        RegisterString(_currentAction);
        RegisterString(_userMessageJSON);
        RegisterString(_characterMessageJSON);
        RegisterAction(new JSONStorableAction("# Voxta Options:", () => { }));
        RegisterBool(_autoSendRecognizedSpeech);
        RegisterBool(_characterCanSpeak);
        RegisterAction(new JSONStorableAction("# Voxta Chat Parameters:", () => { }));
        RegisterStringChooser(_character1JSON);
        RegisterString(_character1RoleJSON);
        RegisterString(_character1NameJSON);
        _audioAtomTarget1.RegisterStorables();
        RegisterStringChooser(_character2JSON);
        RegisterString(_character2RoleJSON);
        RegisterString(_character2NameJSON);
        _audioAtomTarget2.RegisterStorables();
        RegisterStringChooser(_character3JSON);
        RegisterString(_character3RoleJSON);
        RegisterString(_character3NameJSON);
        _audioAtomTarget3.RegisterStorables();
        RegisterStringChooser(_scenarioJSON);
        RegisterString(_scenarioNameJSON);
        _audioAtomNarrator.RegisterStorables();
        _subtitles.RegisterStorables();
        RegisterStringChooser(_chatJSON);
        RegisterAction(new JSONStorableAction("==== Voxta Advanced", () => { }));
        RegisterBool(_enableLogsJSON);
        RegisterAction(_deleteCurrentChat);
        RegisterAction(_startNewChat);
        RegisterAction(_revertLastSentMessage);
        RegisterString(_packageIdJSON);
        RegisterString(_packageVersionJSON);
        RegisterUrl(_packagePathJSON);

        SuperController.singleton.onAtomUIDRenameHandlers += OnAtomRename;

        SuperController.singleton.StartCoroutine(DeferredInit());
    }

    private void EnableLipSync()
    {
        Atom personAtom = GetContainingAtom();
        if (personAtom == null) return;

        // Turn OFF Jaw Drive from Audio
        JSONStorable jawControlStorable = personAtom.GetStorableByID("JawControl");
        if (jawControlStorable != null)
        {
            JSONStorableBool jawDriveParam = jawControlStorable.GetBoolJSONParam("driveXRotationFromAudioSource");
            if (jawDriveParam != null)
            {
                jawDriveParam.val = false;
            }
            JSONStorableFloat jawRotationParam = jawControlStorable.GetFloatJSONParam("targetRotationX");
            if (jawRotationParam != null)
            {
                jawRotationParam.val = 0.0f;
            }
        }

        // Turn ON LipSync
        JSONStorable lipSyncStorable = personAtom.GetStorableByID("LipSync");
        if (lipSyncStorable != null)
        {
            JSONStorableBool lipSyncEnabledParam = lipSyncStorable.GetBoolJSONParam("enabled");
            if (lipSyncEnabledParam != null)
            {
                lipSyncEnabledParam.val = true;
            }
        }
    }

    private void DeleteCurrentChat()
    {
        if (_chatJSON.val == "")
            return;
        _activeJSON.val = false;
        var chatId = _chatJSON.val;
        _chatJSON.val = "";
        if (!string.IsNullOrEmpty(chatId))
        {
            _client.SendDeleteChat(chatId);
            _chatJSON.val = "";
            var index = _chatJSON.choices.IndexOf(chatId);
            if (index != -1)
            {
                _chatJSON.choices.RemoveAt(index);
                _chatJSON.choices = new List<string>(_chatJSON.choices);
                _chatJSON.displayChoices.RemoveAt(index);
                _chatJSON.displayChoices = new List<string>(_chatJSON.displayChoices);
            }
        }
    }

    private void StartNewChat()
    {
        DeleteCurrentChat();
        Invoke(nameof(Activate), 0.1f);
    }

    private void Activate()
    {
        _activeJSON.val = true;
    }

    private void AssignRolesFromScenario(string val)
    {
        var roles = _scenarios?.FirstOrDefault(s => s.Id == val)?.Roles;
        if (roles != null && roles.Length > 0)
        {
            var role = roles[0];
            _character1RoleJSON.val = role.Name;
            if (!string.IsNullOrEmpty(role.DefaultCharacterId))
                _character1JSON.val = role.DefaultCharacterId;

            if (roles.Length > 1)
            {
                var role2 = roles[1];
                _character2RoleJSON.val = role2.Name;
                if(!string.IsNullOrEmpty(role2.DefaultCharacterId))
                    _character2JSON.val = role2.DefaultCharacterId;

                if (roles.Length > 2)
                {
                    var role3 = roles[2];
                    _character3RoleJSON.val = role3.Name;
                    if (!string.IsNullOrEmpty(role3.DefaultCharacterId))
                        _character3JSON.val = role3.DefaultCharacterId;
                }
            }
            else
            {
                _character2RoleJSON.val = "";
            }
        }
        else
        {
            _character1RoleJSON.val = "";
        }
    }

    private void OnAtomRename(string before, string after)
    {
        _onChatSessionTrigger?.OnAtomRename();
        _onChatLoadingSessionTrigger.OnAtomRename();
        _onStateChangedTrigger?.OnAtomRename();
        _onSpeakTrigger?.OnAtomRename();
        _isSpeakingTrigger?.OnAtomRename();
        _onActionTrigger?.OnAtomRename();
        _audioAtomTarget1.OnAtomRename();
        _audioAtomTarget2.OnAtomRename();
        _audioAtomTarget3.OnAtomRename();
        _audioAtomNarrator.OnAtomRename();
        _subtitles.OnAtomRename();
    }

    private IEnumerator DeferredInit()
    {
        yield return new WaitForEndOfFrame();

        if (this == null) yield break;

        if (!_restored) containingAtom.RestoreFromLast(this);

        while (SuperController.singleton.isLoading)
            yield return 0;

        _initialized = true;

        OnEnable();

        SuperController.singleton.BroadcastMessage("OnActionsProviderAvailable", this, SendMessageOptions.DontRequireReceiver);
    }

    public override void InitUI()
    {
        base.InitUI();
        if (UITransform == null) return;
        _onChatSessionTrigger.Trigger.triggerActionsParent = UITransform;
        _onChatLoadingSessionTrigger.Trigger.triggerActionsParent = UITransform;
        _onStateChangedTrigger.Trigger.triggerActionsParent = UITransform;
        _onSpeakTrigger.Trigger.triggerActionsParent = UITransform;
        _isSpeakingTrigger.Trigger.triggerActionsParent = UITransform;
        _onActionTrigger.Trigger.triggerActionsParent = UITransform;
        SuperController.singleton.StartCoroutine(VamAssets.LoadUIAssets());

        _ui = new UI(this);

        // Left Side

        _ui.CreateTitle("Host");
        _ui.CreateTextInput(_credentials.AddressJSON);
        _ui.CreateTitle("API Key (Required when a password is set)", fontSize: 24, fontBold: false);
        _ui.CreateTextInput(_credentials.APIKeyJSON);
        _ui.CreateTitle("Connection Status", fontSize: 24, fontBold: false);
        _ui.CreateTextField(_statusJSON);

        _ui.CreateSpacer();
        _ui.CreateTitle("Activate Voxta");
        CreateToggle(_activeJSON);
        var readyUI = CreateToggle(_readyJSON);
        readyUI.toggle.interactable = false;
        readyUI.label = "Chat Session Ready";
        CreateButton("Enable Lip Sync").button.onClick.AddListener(() => _enableLipSyncAction.actionCallback());
        var statePopup = CreateScrollablePopup(_stateJSON);
        statePopup.popup.sliderControl.interactable = false;
        statePopup.popup.topButton.interactable = false;

        _ui.CreateSpacer();
        _ui.CreateTitle("Chat");
        _ui.CreatePopup(_chatJSON, popupPanelHeight: 600);
        CreateButton("Start New Chat", false).button.onClick.AddListener(StartNewChat);
        CreateButton("Delete Current Chat").button.onClick.AddListener(DeleteCurrentChat);
        CreateButton("Revert Last Sent Message").button.onClick.AddListener(() => _revertLastSentMessage.actionCallback.Invoke());

        _ui.CreateSpacer();
        _ui.CreateTitle("Speech");
        _ui.CreateToggle(_autoSendRecognizedSpeech).label = "Automatically Send User Speech";
        _ui.CreateToggle(_characterCanSpeak).label = "Character Can Speak / Reply";

        _ui.CreateSpacer();
        _ui.CreateTitle("Triggers");
        CreateButton("On Chat Loading Trigger").button.onClick.AddListener(() =>
        {
            _onChatLoadingSessionTrigger.Trigger.OpenTriggerActionsPanel();
        });
        CreateButton("On Chat Session Active Trigger").button.onClick.AddListener(() =>
        {
            _onChatSessionTrigger.Trigger.OpenTriggerActionsPanel();
        });
        CreateButton("On State Changed Trigger").button.onClick.AddListener(() =>
        {
            _onStateChangedTrigger.Trigger.OpenTriggerActionsPanel();
        });
        CreateButton("On Speak Trigger").button.onClick.AddListener(() =>
        {
            _onSpeakTrigger.Trigger.OpenTriggerActionsPanel();
        });
        CreateButton("Is Speaking Trigger").button.onClick.AddListener(() =>
        {
            _isSpeakingTrigger.Trigger.OpenTriggerActionsPanel();
        });
        CreateButton("On Action Trigger").button.onClick.AddListener(() =>
        {
            _onActionTrigger.Trigger.OpenTriggerActionsPanel();
        });

        _ui.CreateSpacer(false);
        _ui.CreateTitle("Package", false);
        _ui.CreateTitle("Package ID", false, 24, false);
        var packageIdUIText = _ui.CreateTextInput(_packageIdJSON, false);
        packageIdUIText.UItext.fontSize = 22;
        _ui.CreateTitle("Requested Package Version (Min)", false, 24, false);
        _ui.CreateTextInput(_packageVersionJSON, false);
        _ui.CreateTitle("Package Path", false, 24, false);
        var packagePathUIText = _ui.CreateTextInput(_packagePathJSON, false);
        packagePathUIText.UItext.fontSize = 16;

        _ui.CreateSpacer();
        _ui.CreateTitle("Links");

        #if(VAM_GT_1_22_0_7)
        var helpButton = CreateButton("[Browser] Online help");
        helpButton.buttonColor = Color.white;
        helpButton.button.onClick.AddListener(() => SuperController.OpenURL("https://doc.voxta.ai/"));

        var discordButton = CreateButton("[Browser] Discord");
        discordButton.textColor = new Color(0.44705f, 0.53725f, 0.85490f);
        discordButton.buttonColor = Color.white;
        discordButton.button.onClick.AddListener(() => SuperController.OpenURL("https://discord.gg/voxta"));

        var patreonBtn = CreateButton("[Browser] Patreon");
        patreonBtn.textColor = new Color(0.97647f, 0.40784f, 0.32941f);
        patreonBtn.buttonColor = Color.white;
        patreonBtn.button.onClick.AddListener(() => SuperController.OpenURL("https://www.patreon.com/Voxta"));
        #else
        _ui.CreateTextField(new JSONStorableString("__OnlineHelp", "https://doc.voxta.ai"));
        _ui.CreateTextField(new JSONStorableString("__Discord", "https://discord.gg/voxta"));
        _ui.CreateTextField(new JSONStorableString("__Patreon", "https://www.patreon.com/Voxta"));
        #endif

        _ui.CreateSpacer();
        _ui.CreateTitle("Advanced");
        _ui.CreateToggle(_enableLogsJSON);

        // Right Side

        _ui.CreateTitle("Chat Parameters", true);
        CreateButton("Refresh All Lists", true).button.onClick.AddListener(() =>
        {
            if (!_client.IsConnected) return;
            _scheduler.Enqueue(RefreshRemoteLists);
        });

        _ui.CreateSpacer(true);
        _ui.CreatePopup(_scenarioJSON, true, popupPanelHeight: 900);

        _ui.CreateSpacer(true);
        var mainCharacterTitle = _ui.CreateTitle("Main Character", true);
        _ui.CreatePopup(_character1JSON, true, popupPanelHeight: 780);
        _ui.CreatePopup(_audioAtomTarget1.AudioAtomJSON, true);
        _ui.CreatePopup(_audioAtomTarget1.AudioStorableJSON, true);

        _ui.CreateSpacer(true);
        var character2Title = _ui.CreateTitle("Character #2", true);
        _ui.CreatePopup(_character2JSON, true, popupPanelHeight: 640);
        _ui.CreateUpwardsPopup(_audioAtomTarget2.AudioAtomJSON, true);
        _ui.CreateUpwardsPopup(_audioAtomTarget2.AudioStorableJSON, true);

        _ui.CreateSpacer(true);
        var character3Title = _ui.CreateTitle("Character #3", true);
        _ui.CreatePopup(_character3JSON, true, popupPanelHeight: 500);
        _ui.CreateUpwardsPopup(_audioAtomTarget3.AudioAtomJSON, true);
        _ui.CreateUpwardsPopup(_audioAtomTarget3.AudioStorableJSON, true);

        _ui.CreateSpacer(true);
        _ui.CreateTitle("Narrator", true);
        _ui.CreateUpwardsPopup(_audioAtomNarrator.AudioAtomJSON, true);
        _ui.CreateUpwardsPopup(_audioAtomNarrator.AudioStorableJSON, true);

        _ui.CreateSpacer(true);
        _ui.CreateTitle("Subtitles", true);
        _ui.CreateUpwardsPopup(_subtitles.SubtitlesAtomJSON, true);
        _ui.CreateUpwardsPopup(_subtitles.SubtitlesStorableJSON, true);
        _ui.CreateUpwardsPopup(_subtitles.SubtitlesParamJSON, true);
        // Uncomment if useful
        // _ui.CreateUpwardsPopup(_subtitles.SubtitlesActionJSON, true);

        _ui.CreateSpacer(true);
        _ui.CreateTitle("Prompt Context", true);
        _ui.CreateTitle("Flags", true, 24, false);
        _ui.CreateTextField(_flags, true);
        _ui.CreateTitle("Set Flags", true, 24, false);
        _ui.CreateTextInput(_setFlags, true);
        _ui.CreateTitle("Conversation Context (Base, 1, 2, 3, 4)", true, 24, false);
        _ui.CreateTextInput(_contextJSON, true);
        _ui.CreateTextInput(_context1JSON, true);
        _ui.CreateTextInput(_context2JSON, true);
        _ui.CreateTextInput(_context3JSON, true);
        _ui.CreateTextInput(_context4JSON, true);
        _ui.CreateTitle("Available Actions List (Base)", true, 24, false);
        _ui.CreateMultilineTextInput(_actionsListJSON, true);
        _ui.CreateTitle("Last Action", true, fontSize: 22);
        _ui.CreateTextField(_currentAction, true);
        _ui.CreateTitle("Tools", true, fontSize: 22);
        CreateButton("Clear Actions & Context", true).button.onClick.AddListener(() => _clearContext.actionCallback.Invoke());
        CreateButton("Create Sample Actions", true).button.onClick.AddListener(() =>
        {
            _actionsListJSON.val = "action: nod\nwhen: Whenever {{ char }} agrees or approves.\n\naction: shake_head\nwhen: Whenever {{ char }} refuses or disapproves.";
        });

        // Dynamic
        _character1RoleJSON.setCallbackFunction = val =>
        {
            mainCharacterTitle.text.text = val != "" ? "Main Character: " + val : "Main Character";
        };

        _character2RoleJSON.setCallbackFunction = val =>
        {
            character2Title.text.text = val != "" ? "Character #2: " + val : "Character #2";
        };

        _character3RoleJSON.setCallbackFunction = val =>
        {
            character3Title.text.text = val != "" ? "Character #3: " + val : "Character #2";
        };
    }

    public void Update()
    {
        _scheduler.Update();

        _onChatSessionTrigger?.Trigger?.Update();
        _onChatLoadingSessionTrigger?.Trigger?.Update();
        _onStateChangedTrigger?.Trigger?.Update();
        _onSpeakTrigger?.Trigger?.Update();
        _isSpeakingTrigger?.Trigger?.Update();
        _onActionTrigger?.Trigger?.Update();
    }

    public void OnEnable()
    {
        if (!_initialized) return;

        InitializeVoxtaClient();
    }

    public void OnDisable()
    {
        _onChatLoadingSessionTrigger.SetActive(false);
        DisposeVoxtaClient();
    }

    private void InitializeVoxtaClient()
    {
        if (_client != null) return;

        _client = new VoxtaClient(_credentials, _scheduler, _logger);

        _client.OnStatusChanged.AddListener((status) =>
        {
            _statusJSON.val = status;
        });
        _client.OnConnected.AddListener((connected) =>
        {
            _connectedJSON.val = connected;
            _readyJSON.val = false;
            if (connected)
                TryStartChat();

            _scheduler.Enqueue(RefreshRemoteLists);
        });
        _client.OnUserNameAvailable.AddListener((userName) =>
        {
            _userNameJSON.val = userName;
        });
        _client.OnCharactersListReceived.AddListener((characters) =>
        {
            _characters = characters;
            _character1JSON.choices = new[] { "" }.Concat(characters.Select(c => c.Id)).ToList();
            _character1JSON.displayChoices = new[] { "" }.Concat(characters.Select(c => c.Name + " - " + c.CreatorNotes)).ToList();
            _character1JSON.popup.currentValueNoCallback = _character1JSON.val;

            _character2JSON.choices = _character1JSON.choices;
            _character2JSON.displayChoices = _character1JSON.displayChoices;
            _character2JSON.popup.currentValueNoCallback = _character2JSON.val;

            _character3JSON.choices = _character1JSON.choices;
            _character3JSON.displayChoices = _character1JSON.displayChoices;
            _character3JSON.popup.currentValueNoCallback = _character3JSON.val;

            var mainCharacter = _characters.FirstOrDefault(s => s.Id == _character1JSON.val);
            if (mainCharacter != null)
            {
                if ((mainCharacter.PackageId ?? "") != _packageIdJSON.val) RefreshPackageLink();
            }
        });
        _client.OnScenariosListReceived.AddListener((scenarios) =>
        {
            var choices = new List<string> { "", "" };
            var displayChoices = new List<string> { "None (Use Character's Scenario)", "==== FOR VAM ====" };
            var voxtaScenes = true;
            foreach (var scenario in scenarios.OrderBy(s => s.Client == VoxtaClient.ClientName ? 0 : 1))
            {
                if(voxtaScenes && scenario.Client != VoxtaClient.ClientName)
                {
                    voxtaScenes = false;
                    choices.Add("");
                    displayChoices.Add("==== OTHER ====");
                }
                choices.Add(scenario.Id);
                displayChoices.Add(scenario.Name);
            }
            _scenarios = scenarios;
            _scenarioJSON.choices = choices;
            _scenarioJSON.displayChoices = displayChoices;
            _scenarioJSON.popup.currentValueNoCallback = _scenarioJSON.val;
            var selectedScenario = _scenarios.FirstOrDefault(s => s.Id == _scenarioJSON.val);
            if (selectedScenario != null)
            {
                if ((selectedScenario.PackageId ?? "") != _packageIdJSON.val) RefreshPackageLink();
            }
        });
        _client.OnChatsListReceived.AddListener((chat) =>
        {
            _chatJSON.choices = new[] { "" }.Concat(chat.Select(c => c.Id)).ToList();
            _chatJSON.displayChoices = new[] { "Create New" }.Concat(chat.Select(c => $"{c.Created} {c.Id.Substring(0, 8)}")).ToList();
            _chatJSON.popup.currentValueNoCallback = _chatJSON.val;
        });
        _client.OnChatStartedReceived.AddListener((e) =>
        {
            var chatId = e.ChatId;
            _subtitles.TryConnect();
            _subtitles.Show("", "");
            _chatJSON.valNoCallback = chatId;
            if (!string.IsNullOrEmpty(chatId) && !_chatJSON.choices.Contains(chatId))
            {
                var newChoices = new List<string>(_chatJSON.choices);
                newChoices.Insert(0, chatId);
                _chatJSON.choices = newChoices;
                var newDisplayChoices = new List<string>(_chatJSON.displayChoices);
                newDisplayChoices.Insert(0, $"Chat {chatId.Substring(0, 8)}");
                _chatJSON.displayChoices = newDisplayChoices;
                _chatJSON.popup.currentValue = chatId;
            }
            _stateJSON.val = States.Idle;
            if (_actions1.Count > 0 || string.IsNullOrEmpty(_context1JSON.val))
                _client.UpdateContext(_actions1, _context1JSON.val, "VaM/Slot1");
            if (_actions2.Count > 0 || string.IsNullOrEmpty(_context2JSON.val))
                _client.UpdateContext(_actions2, _context2JSON.val, "VaM/Slot2");
            if (_actions3.Count > 0 || string.IsNullOrEmpty(_context3JSON.val))
                _client.UpdateContext(_actions3, _context3JSON.val, "VaM/Slot3");
            if (_actions4.Count > 0 || string.IsNullOrEmpty(_context4JSON.val))
                _client.UpdateContext(_actions4, _context4JSON.val, "VaM/Slot4");
            var pendingFlags = _pendingFlags.ToArray();
            _pendingFlags.Clear();
            foreach(var pendingFlag in pendingFlags)
                _client.SendSetFlags(pendingFlag);
            foreach (var character in e.Characters)
            {
                if (character.Id == _character1JSON.val)
                {
                    _character1NameJSON.val = character.Name;
                } else if (character.Id == _character2JSON.val)
                {
                    _character2NameJSON.val = character.Name;
                }
                else if (character.Id == _character3JSON.val)
                {
                    _character3NameJSON.val = character.Name;
                }
            }
            _readyJSON.val = true;
        });
        _client.OnChatClosedReceived.AddListener((chatId) =>
        {
            _readyJSON.val = false;
        });
        _client.OnReplyGeneratingReceived.AddListener((msg) =>
        {
            _stateJSON.val = States.Thinking;
            _speechPlayback.Start(msg.MessageId);

            if (!string.IsNullOrEmpty(msg.AudioUrl))
            {
                var audioSource = msg.IsNarration ? _audioAtomNarrator.AudioSource : GetAudioSourceControl(msg.SenderId);
                if (audioSource != null)
                    _speechPlayback.EnqueuePlay(msg, audioSource);
            }
        });
        _client.OnReplyStartReceived.AddListener(start =>
        {
            if (_character1JSON.val == start.SenderId)
            {
                _characterMessageJSON.val = "";
                if (_characterCanSpeak.val)
                    _stateJSON.val = States.Speaking;
            }
        });
        _client.OnReplyChunkReceived.AddListener((chunk) =>
        {
            if (!_characterCanSpeak.val)
                return;

            if (!string.IsNullOrEmpty(chunk.AudioUrl))
            {
                var audioSource = chunk.IsNarration ? _audioAtomNarrator.AudioSource : GetAudioSourceControl(chunk.SenderId);
                if (audioSource != null)
                    _speechPlayback.EnqueuePlay(chunk, audioSource);
            }
            else
            {
                if (_character1JSON.val == chunk.SenderId)
                {
                    _subtitles.Show(_character1NameJSON.val, chunk.Text);
                    InvokeOnSpeakTrigger();
                }
                else if (_character2JSON.val == chunk.SenderId)
                {
                    _subtitles.Show(_character2NameJSON.val, chunk.Text);
                }
                else if (_character3JSON.val == chunk.SenderId)
                {
                    _subtitles.Show(_character3NameJSON.val, chunk.Text);
                }
                else
                {
                    _subtitles.Show("", chunk.Text);
                }
            }
        });
        _client.OnReplyEndReceived.AddListener(end =>
        {
            _speechPlayback.EnqueueComplete(end);
        });
        _client.OnServerSpeechRecognitionStart.AddListener(() =>
        {
            _stateJSON.val = States.Listening;
        });
        _client.OnServerSpeechRecognitionPartial.AddListener((text) =>
        {
            if (string.IsNullOrEmpty(text))
            {
                _subtitles.Show("", "");
            }
            else
            {
                _subtitles.Show(_userNameJSON.val, text);
            }
        });
        _client.OnServerSpeechRecognitionEnd.AddListener((text) =>
        {
            if (string.IsNullOrEmpty(text))
            {
                _subtitles.Show("", "");
                _stateJSON.val = States.Idle;
                return;
            }
            _userMessageJSON.val = text;
            _subtitles.Show(_userNameJSON.val, text);
            if (!_autoSendRecognizedSpeech.val)
            {
                _stateJSON.val = States.Idle;
                return;
            }
            _client.SendChatMessage(text, _characterCanSpeak.val, true);
        });
        _client.OnActionReceived.AddListener((action) =>
        {
            _currentAction.val = action;
            Invoke(nameof(InvokeOnActionTrigger), 0);
        });
        _client.OnAppTriggerReceived.AddListener((trigger) =>
        {
            TriggerInvoker.Invoke(trigger);
        });
        _client.OnScenarioFlagsReceived.AddListener(flags =>
        {
            _flags.valNoCallback = string.Join(", ", flags);
        });
        _client.OnError.AddListener(message =>
        {
            _errorJSON.val = true;
            _lastErrorJSON.val = message;
        });
        _client.OnChatFlow.AddListener(state =>
        {
            if (state == "WaitingForUserInput")
                _stateJSON.val = States.Idle;
        });
        _client.OnMissingResourcesReceived.AddListener((resources) =>
        {
            _activeJSON.valNoCallback = false;

            if (_packagePathJSON.val != "" && _packageIdJSON.val != "")
            {
                SuperController.LogMessage("Voxta: Some resources are missing, the scene package will be installed. Missing resources: " + string.Join(", ", resources.Select(x => x.Id).ToArray()));

                DeployResource(new VoxtaClient.MissingResource
                {
                    Id = _packageIdJSON.val,
                    Kind = "Package",
                    Version = !string.IsNullOrEmpty(_packageVersionJSON.val) ? _packageVersionJSON.val : null,
                    Status = "",
                }, _packagePathJSON.val);
                return;
            }

            var package = resources.FirstOrDefault(r => r.Kind == "Package");

            if (package != null)
            {
                SuperController.LogMessage("Voxta: Some resources are missing, the scene package will be installed. Looking for package: " + package.Id);
                DeployResource(package);
                return;
            }

            SuperController.LogMessage("Voxta: Some resources are missing and will be installed: " + string.Join(", ", resources.Select(x => x.Id).ToArray()));
            foreach (var resource in resources)
            {
                DeployResource(resource);
            }
        });
        _client.OnDeployResourceResultReceived.AddListener(result =>
        {
            var resource = _pendingResources.FirstOrDefault(x => x.Id == result.Id);
            if (resource == null) return;
            _pendingResources.Remove(resource);
            if (result.Success)
            {
                if (_pendingResources.Count == 0)
                {
                    _activeJSON.valNoCallback = true;
                    RefreshCharactersList();
                    RefreshScenariosList();
                    TryStartChat();
                }
            }
            else
            {
                SuperController.LogError($"Voxta: Failed to deploy resource {resource.Kind} {resource.Id}: {result.Error}");
            }
        });
        _client.OnInterruptSpeech.AddListener(() =>
        {
            _speechPlayback.Interrupt();
            _audioAtomTarget1.AudioSource?.Stop();
            _audioAtomTarget2.AudioSource?.Stop();
            _audioAtomTarget3.AudioSource?.Stop();
            _audioAtomNarrator.AudioSource?.Stop();
        });
        _client.OnMessageUpdatedReceived.AddListener((message) =>
        {
            if (message.Role == "Instructions")
            {
                _logger.Log(() => $"<- Instructions: {message.Text ?? ""}");
            }
            else if (message.Role == "User")
            {
                _userMessageJSON.val = message.Text ?? "";
            }
        });

        _client.Connect();
    }

    private AudioSourceControl GetAudioSourceControl(string senderId)
    {
        if (!_characterCanSpeak.val) return null;
        if (_character1JSON.val == senderId)
            return _audioAtomTarget1.AudioSource;
        if (_character2JSON.val == senderId)
            return _audioAtomTarget2.AudioSource;
        if (_character3JSON.val == senderId)
            return _audioAtomTarget3.AudioSource;
        return null;
    }

    private void DeployResource(VoxtaClient.MissingResource resource, string path)
    {
        if (!FileManagerSecure.FileExists(path))
        {
            SuperController.LogError($"Could not find a scene dependency of type {resource.Kind} with id {resource.Id} in Voxta nor an exported package in '{path}'");
            return;
        }
        var bytes = FileManagerSecure.ReadAllBytes(path);
        _pendingResources.Add(resource);
        _client.SendDeployResource(resource, path.Substring(path.LastIndexOf('/') + 1), bytes);
    }

    private void DeployResource(VoxtaClient.MissingResource resource)
    {
        string path;
        if (!TryLoadResource(resource, out path))
        {
            SuperController.LogError($"Could not find a scene dependency of type {resource.Kind} with id {resource.Id} in Voxta nor an exported package in 'Saves/PluginData/Voxta/{resource.Kind}s'");
            return;
        }
        var bytes = FileManagerSecure.ReadAllBytes(path);
        _pendingResources.Add(resource);
        _client.SendDeployResource(resource, path.Substring(path.LastIndexOf('/') + 1), bytes);
    }

    private bool TryLoadResource(VoxtaClient.MissingResource resource, out string path)
    {
        {
            var pathIdPrefix = $"{_varPrefix}Saves/PluginData/Voxta/{resource.Kind}s/{resource.Id}.{resource.Kind.ToLowerInvariant()}";
            if (TryLoadResourceExtensions(pathIdPrefix, out path)) return true;

            if (!string.IsNullOrEmpty(resource.Version))
            {
                if (TryLoadResourceExtensions(pathIdPrefix + "." + resource.Version, out path)) return true;
            }

            if (!string.IsNullOrEmpty(_packageVersionJSON.val))
            {
                if (TryLoadResourceExtensions(pathIdPrefix + "." + _packageVersionJSON.val, out path)) return true;
            }
        }

        if(resource.Kind == "Package" && _packageIdJSON.val == resource.Id && _packagePathJSON.val != "")
        {
            return TryLoadResourceExtensions(Normalize(_packagePathJSON.val), out path);
        }

        path = null;
        return false;
    }

    private string Normalize(string path)
    {
        if(path.StartsWith("SELF:/"))
            return _varPrefix + path.Substring(6);
        return path;
    }

    private static bool TryLoadResourceExtensions(string pathIdPrefix, out string path)
    {
        if(pathIdPrefix.EndsWith(".png") || pathIdPrefix.EndsWith(".json") || pathIdPrefix.EndsWith(".zip") || pathIdPrefix.EndsWith(".vxz") || pathIdPrefix.EndsWith(".voxpkg"))
        {
            if (FileManagerSecure.FileExists(pathIdPrefix))
            {
                path = pathIdPrefix;
                return true;
            }

            path = null;
            return false;
        }

        if (FileManagerSecure.FileExists(pathIdPrefix + ".png"))
        {
            path = pathIdPrefix + ".png";
            return true;
        }

        if (FileManagerSecure.FileExists(pathIdPrefix + ".zip"))
        {
            path = pathIdPrefix + ".zip";
            return true;
        }

        if (FileManagerSecure.FileExists(pathIdPrefix + ".vxz"))
        {
            path = pathIdPrefix + ".vxz";
            return true;
        }

        if (FileManagerSecure.FileExists(pathIdPrefix + ".voxpkg"))
        {
            path = pathIdPrefix + ".voxpkg";
            return true;
        }

        if (FileManagerSecure.FileExists(pathIdPrefix + ".json"))
        {
            path = pathIdPrefix + ".json";
            return true;
        }

        path = null;
        return false;
    }

    private static string SanitizeName(string value)
    {
        return Regex.Replace(value, @"[^a-z0-9_ -]", "", RegexOptions.IgnoreCase).Trim();
    }

    private void DisposeVoxtaClient()
    {
        _readyJSON.val = false;
        if (_client == null) return;
        _client.Disconnect();
        _client.Dispose();
        _client = null;
    }

    private void ReconnectToServer()
    {
        if (!enabled) return;
        if (!_credentials.IsValid())
        {
            _statusJSON.val = "Invalid host or API key";
            return;
        }
        DisposeVoxtaClient();
        InitializeVoxtaClient();
    }

    private void TryStartChat()
    {
        if (!_initialized) return;
        if (!_activeJSON.val) return;
        if (_client?.IsConnected != true) return;

        if (string.IsNullOrEmpty(_character1JSON.val))
        {
            _activeJSON.val = false;
            SuperController.LogError("Voxta: A character was not set!");
            return;
        }

        var characters = new JSONArray();
        if (!string.IsNullOrEmpty(_character1JSON.val))
            characters.Add(_character1JSON.val);
        if (!string.IsNullOrEmpty(_character2JSON.val))
            characters.Add(_character2JSON.val);
        if (!string.IsNullOrEmpty(_character3JSON.val))
            characters.Add(_character3JSON.val);

        var json = new JSONClass
        {
            ["$type"] = "startChat",
            ["characterIds"] = characters,
            ["contextKey"] = "VaM/Base",
        };
        if (!string.IsNullOrEmpty(_chatJSON.val)) json["chatId"] = _chatJSON.val;
        var contextStr = _contextJSON.val.Trim();
        if (contextStr != "")
        {
            if (!string.IsNullOrEmpty(_contextJSON.val))
            {
                json["contexts"] = new JSONArray()
                {
                    new JSONClass
                    {
                        ["text"] = contextStr
                    }
                };
            }
        }
        if (_actions != null && _actions.Count > 0) json["actions"] = _actions;
        if (!string.IsNullOrEmpty(_scenarioJSON.val)) json["scenarioId"] = _scenarioJSON.val;
        if (!string.IsNullOrEmpty(_packageIdJSON.val))
        {
            var dependencies = new JSONArray();

            var packageDependency = new JSONClass
            {
                ["kind"] = "Package",
                ["id"] = _packageIdJSON.val
            };
            if(!string.IsNullOrEmpty(_packageVersionJSON.val))
                packageDependency["version"] = _packageVersionJSON.val;

            dependencies.Add(packageDependency);

            json["dependencies"] = dependencies;
        }

        if (_character1RoleJSON.val != "")
        {
            var roles = new JSONClass
            {
                [_character1RoleJSON.val] = _character1JSON.val
            };
            if (_character2RoleJSON.val != "" && _character2JSON.val != "")
            {
                roles.Add(_character2RoleJSON.val, _character2JSON.val);
            }
            if (_character3RoleJSON.val != "" && _character3JSON.val != "")
            {
                roles.Add(_character3RoleJSON.val, _character3JSON.val);
            }
            json["roles"] = roles;
        }

        _pendingResources.Clear();
        _onChatLoadingSessionTrigger.SetActive(true);
        _client.StartChat(json);
    }

    private void RefreshRemoteLists()
    {
        RefreshScenariosList();
        RefreshCharactersList();
        RefreshChatsList();
    }

    private void RefreshScenariosList()
    {
        _scenarioJSON.choices = new List<string> { "" };
        _scenarioJSON.displayChoices = new List<string> { "None" };
        _scenarioJSON.popup.currentValueNoCallback = _scenarioJSON.val;
        if (_client?.IsConnected != true) return;
        _client.LoadScenarios();
    }

    private void RefreshCharactersList()
    {
        _character1JSON.choices = new List<string>();
        if (_client?.IsConnected != true) return;
        _client.LoadCharacters();
    }

    private void RefreshChatsList()
    {
        _chatJSON.choices = new List<string>();
        if (_client?.IsConnected != true) return;
        if (!string.IsNullOrEmpty(_character1JSON.val))
        {
            _client.LoadChats(_scenarioJSON.val, _character1JSON.val);
        }
        else
        {
            _chatJSON.choices = new List<string> { "" };
            _chatJSON.displayChoices = new List<string> { "Create New" };
            _chatJSON.val = "";
        }
    }

    private void RefreshPackageLink()
    {
        var scenario = _scenarios?.FirstOrDefault(s => s.Id == _scenarioJSON.val);
        var character = _characters?.FirstOrDefault(s => s.Id == _character1JSON.val);
        var packageSource = scenario?.PackageId != null ? (VoxtaClient.IResourceItem)scenario : (character?.PackageId != null ? character : null);
        if (string.IsNullOrEmpty(packageSource?.PackageId))
        {
            _packageIdJSON.val = "";
            _packageVersionJSON.val = "";
            _packagePathJSON.val = "";
            return;
        }

        if (_packageIdJSON.val != packageSource.PackageId)
            _packageVersionJSON.val = "";

        _packageIdJSON.val = packageSource.PackageId;
        var packagePath = $"Saves/PluginData/Voxta/Packages/{SanitizeName(packageSource.PackageName ?? packageSource.PackageId)}.package";
        if(!string.IsNullOrEmpty(packageSource.PackageVersion))
            packagePath += "." + packageSource.PackageVersion;
        packagePath += ".png";
        _packagePathJSON.val = packagePath;
    }

    public void OnDestroy()
    {
        SuperController.singleton.onAtomUIDRenameHandlers -= OnAtomRename;
        SuperController.singleton.BroadcastMessage("OnActionsProviderDestroyed", this, SendMessageOptions.DontRequireReceiver);

        _speechPlayback?.Dispose();
    }

    public override void Validate()
    {
        base.Validate();
        _onChatSessionTrigger?.Trigger?.Validate();
        _onChatLoadingSessionTrigger?.Trigger?.Validate();
        _onStateChangedTrigger?.Trigger?.Validate();
        _onSpeakTrigger?.Trigger?.Validate();
        _isSpeakingTrigger?.Trigger?.Validate();
        _onActionTrigger?.Trigger?.Validate();
    }

    public void InvokeOnStateChangedTrigger()
    {
        _onStateChangedTrigger.Toggle();
    }

    public void InvokeOnSpeakTrigger()
    {
        _onSpeakTrigger.Toggle();
    }

    public void InvokeOnActionTrigger()
    {
        _onActionTrigger.Toggle();
    }

    public override JSONClass GetJSON(bool includePhysical = true, bool includeAppearance = true, bool forceStore = false)
    {
        var json = base.GetJSON(includePhysical, includeAppearance, forceStore);
        json["OnChatSessionTrigger"] = _onChatSessionTrigger.Trigger.GetJSON();
        json["OnChatLoadingSessionTrigger"] = _onChatLoadingSessionTrigger.Trigger.GetJSON();
        json["OnStateChangedTrigger"] = _onStateChangedTrigger.Trigger.GetJSON();
        json["OnSpeakTrigger"] = _onSpeakTrigger.Trigger.GetJSON();
        json["IsSpeakingTrigger"] = _isSpeakingTrigger.Trigger.GetJSON();
        json["OnActionTrigger"] = _onActionTrigger.Trigger.GetJSON();
        needsStore = true;
        return json;
    }

    public override void RestoreFromJSON(JSONClass jc, bool restorePhysical = true, bool restoreAppearance = true, JSONArray presetAtoms = null, bool setMissingToDefault = true)
    {
        base.RestoreFromJSON(jc, restorePhysical, restoreAppearance, presetAtoms, setMissingToDefault);
        if (jc.HasKey("OnChatSessionTrigger")) _onChatSessionTrigger.Trigger.RestoreFromJSON(jc["OnChatSessionTrigger"].AsObject);
        if (jc.HasKey("OnChatLoadingSessionTrigger")) _onChatLoadingSessionTrigger.Trigger.RestoreFromJSON(jc["OnChatLoadingSessionTrigger"].AsObject);
        if (jc.HasKey("OnStateChangedTrigger")) _onStateChangedTrigger.Trigger.RestoreFromJSON(jc["OnStateChangedTrigger"].AsObject);
        if (jc.HasKey("OnSpeakTrigger")) _onSpeakTrigger.Trigger.RestoreFromJSON(jc["OnSpeakTrigger"].AsObject);
        if (jc.HasKey("IsSpeakingTrigger")) _isSpeakingTrigger.Trigger.RestoreFromJSON(jc["IsSpeakingTrigger"].AsObject);
        if (jc.HasKey("OnActionTrigger")) _onActionTrigger.Trigger.RestoreFromJSON(jc["OnActionTrigger"].AsObject);
        _restored = true;
    }

    public void OnBindingsListRequested(List<object> bindings)
    {
        bindings.Add(new Dictionary<string, string>
        {
            { "Namespace", "Voxta" }
        });
        bindings.Add(new JSONStorableAction("ToggleActive", () =>
        {
            _activeJSON.val = !_activeJSON.val;
        }));
        bindings.Add(new JSONStorableAction("Activate", () =>
        {
            _activeJSON.val = true;
        }));
        bindings.Add(new JSONStorableAction("Deactivate", () =>
        {
            _activeJSON.val = false;
        }));
        bindings.Add(new JSONStorableAction("CreateNewChat", () =>
        {
            _startNewChat.actionCallback.Invoke();
        }));
        bindings.Add(new JSONStorableAction("RevertLastSentMessage", () =>
        {
            _revertLastSentMessage.actionCallback.Invoke();
        }));
        bindings.Add(new JSONStorableAction("OpenUI", () =>
        {
            if (containingAtom == null) return;
            if (UITransform != null && UITransform.gameObject.activeInHierarchy) return;
            if (SuperController.singleton.gameMode != SuperController.GameMode.Edit) SuperController.singleton.gameMode = SuperController.GameMode.Edit;
            SuperController.singleton.SelectController(containingAtom.mainController, false, false, true);
            SuperController.singleton.ShowMainHUDAuto();
            StartCoroutine(WaitForUI());
        }));
    }

    private IEnumerator WaitForUI()
    {
        var expiration = Time.unscaledTime + 1f;
        while (Time.unscaledTime < expiration)
        {
            yield return 0;
            var selector = containingAtom.gameObject.GetComponentInChildren<UITabSelector>();
            if(selector == null) continue;
            selector.SetActiveTab("Plugins");
            if (UITransform != null) break;
        }
        if (UITransform.gameObject.activeSelf) yield break;
        foreach (Transform scriptController in manager.pluginContainer)
        {
            var script = scriptController.gameObject.GetComponent<MVRScript>();
            if (script != null && script != this)
            {
                script.UITransform.gameObject.SetActive(false);
            }
        }
        UITransform.gameObject.SetActive(true);
    }
}

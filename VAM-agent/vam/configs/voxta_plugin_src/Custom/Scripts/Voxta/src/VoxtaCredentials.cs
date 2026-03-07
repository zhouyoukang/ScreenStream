using System;
using System.Net;
using MVR.FileManagementSecure;
using SimpleJSON;
using UnityEngine.Events;

public interface IVoxtaCredentials
{
    IPAddress Address { get; }
    int Port { get; }
    string APIKey { get; }
    bool IsValid();
}

public class VoxtaCredentials : IVoxtaCredentials
{
    private const string _defaultServerIPAddress = "127.0.0.1";
    private const int _defaultServerPort = 5384;
    private const string _localSettingsFolder = @"Saves\PluginData\Voxta";
    private const string _localSettingsPath = @"Saves\PluginData\Voxta\settings.json";
    private const string ApiKeyPlaceholder = "[An API Key was set]";

    public readonly JSONStorableString AddressJSON = new JSONStorableString("ServerAddress", $"{_defaultServerIPAddress}:{_defaultServerPort}") { isStorable = false, isRestorable = false };
    public readonly JSONStorableString APIKeyJSON = new JSONStorableString("ApiKey", "") { isStorable = false, isRestorable = false };

    public readonly UnityEvent OnChanged = new UnityEvent();

    public string BaseUrl { get; private set; } = $"http://{_defaultServerIPAddress}:{_defaultServerPort}";
    public IPAddress Address { get; private set; } = IPAddress.Parse(_defaultServerIPAddress);
    public int Port { get; private set; } = _defaultServerPort;
    public string APIKey => _apiKey;

    private bool _isValid = true;
    private string _apiKey = "";

    public void Initialize()
    {
        LoadSettings();

        BaseUrl = $"http://{AddressJSON.val}";
        AddressJSON.setCallbackFunction = val =>
        {
            _isValid = false;

            AddressJSON.valNoCallback = val = val.Trim();
            BaseUrl = $"http://{val}";
            SaveSettings();

            var parts = AddressJSON.val.Trim().Split(':');

            if (parts.Length < 2)
            {
                SuperController.LogError("Voxta: Invalid address format (should be IP:PORT)");
                return;
            }

            IPAddress address;
            if (!IPAddress.TryParse(parts[0], out address))
            {
                SuperController.LogError($"Voxta: Invalid IP address: {parts[0]}");
                return;
            }

            int port;
            if (!int.TryParse(parts[1], out port))
            {
                SuperController.LogError($"Voxta: Invalid port: {parts[1]}");
                return;
            }

            Address = address;
            Port = port;

            _isValid = true;
            OnChanged.Invoke();
        };

        APIKeyJSON.setCallbackFunction = val =>
        {
            _apiKey = val.Trim();
            APIKeyJSON.valNoCallback = _apiKey == "" ? "" : ApiKeyPlaceholder;

            SaveSettings();
            OnChanged.Invoke();
        };
    }

    public bool IsValid() => _isValid;

    private void SaveSettings()
    {
        try
        {
            var json = new JSONClass
            {
                ["host"] = AddressJSON.val,
                ["apiKey"] = _apiKey
            };
            FileManagerSecure.CreateDirectory(_localSettingsFolder);
            FileManagerSecure.WriteAllText(_localSettingsPath, json.ToString());
        }
        catch (Exception e)
        {
            SuperController.LogError($"Voxta: Error saving local settings: {e.Message}");
        }
    }

    private void LoadSettings()
    {
        try
        {
            if (!FileManagerSecure.FileExists(_localSettingsPath)) return;
            var json = JSON.Parse(FileManagerSecure.ReadAllText(_localSettingsPath));
            var host = json["host"].Value;
            if(!string.IsNullOrEmpty(host))
                AddressJSON.val = host;
            var apiKey = json["apiKey"].Value;
            if (!string.IsNullOrEmpty(apiKey))
            {
                APIKeyJSON.val = ApiKeyPlaceholder;
                _apiKey = apiKey;
            }
        }
        catch (Exception e)
        {
            SuperController.LogError($"Voxta: Error loading local settings: {e.Message}");
        }
    }
}

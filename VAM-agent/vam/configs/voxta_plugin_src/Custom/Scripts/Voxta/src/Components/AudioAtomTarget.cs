using System.Collections.Generic;
using System.Linq;

public class AudioAtomTarget
{
    private readonly MVRScript _script;

    public readonly JSONStorableStringChooser AudioAtomJSON;
    public readonly JSONStorableStringChooser AudioStorableJSON;

    public AudioSourceControl AudioSource;

    public AudioAtomTarget(MVRScript script, string prefix = null)
    {
        _script = script;
        AudioStorableJSON = new JSONStorableStringChooser($"{prefix}AudioStorable", new List<string>(), "", "Audio Storable");
        AudioAtomJSON = new JSONStorableStringChooser($"{prefix}AudioAtom", new List<string>(), "", "Audio Atom");
    }

    public void Initialize(AudioSourceControl defaultAudioSourceControl)
    {
        AudioAtomJSON.setCallbackFunction = val =>
        {
            AudioStorableJSON.val = "";
            AudioStorableJSON.popupOpenCallback();
            var atom = SuperController.singleton.GetAtomByUid(val);
            if (atom == null)
            {
                if (val != "") SuperController.LogError($"Voxta: Audio output atom \"{val}\" not found");
                AudioStorableJSON.val = "";
                return;
            }

            var audioSourceStorableName = atom.GetStorableIDs()
                .Select(s => atom.GetStorableByID(s) as AudioSourceControl)
                .Where(s => s != null)
                .Select(a => a.name)
                .FirstOrDefault() ?? "";
            AudioStorableJSON.val = audioSourceStorableName;
        };

        AudioAtomJSON.popupOpenCallback = () =>
        {
            AudioAtomJSON.choices = SuperController.singleton
                .GetAtoms()
                .Where(a => a.GetStorableIDs().Any(s => a.GetStorableByID(s) is AudioSourceControl))
                .Select(a => a.name)
                .ToList();
        };

        AudioStorableJSON.setCallbackFunction = val =>
        {
            AudioSource = null;
            if (AudioAtomJSON.val == "" || val == "") return;
            var atom = SuperController.singleton.GetAtomByUid(AudioAtomJSON.val);
            if (atom == null)
            {
                SuperController.LogError($"Voxta: Audio output atom \"{AudioAtomJSON.val}\" not found");
                return;
            }
            var audioSource = atom.GetStorableByID(val) as AudioSourceControl;
            if (audioSource == null)
            {
                SuperController.LogError($"Voxta: Audio output storable \"{AudioAtomJSON.val}/{val}\" not found");
                return;
            }
            AudioSource = audioSource;
        };

        AudioStorableJSON.popupOpenCallback = () =>
        {
            var atom = SuperController.singleton.GetAtomByUid(AudioStorableJSON.val);
            if (atom == null)
            {
                AudioStorableJSON.choices = new List<string>();
                return;
            }
            AudioStorableJSON.choices = atom.GetStorableIDs()
                .Select(s => atom.GetStorableByID(s) as AudioSourceControl)
                .Where(s => s != null)
                .Select(a => a.name)
                .ToList();
        };

        if (defaultAudioSourceControl != null)
        {
            AudioAtomJSON.defaultVal = AudioAtomJSON.valNoCallback = defaultAudioSourceControl.containingAtom.name;
            AudioStorableJSON.defaultVal = AudioStorableJSON.valNoCallback = defaultAudioSourceControl.name;
            AudioSource = defaultAudioSourceControl;
        }

        OnAtomRename();
    }

    public void RegisterStorables()
    {
        _script.RegisterStringChooser(AudioAtomJSON);
        _script.RegisterStringChooser(AudioStorableJSON);
    }

    public void OnAtomRename()
    {
        AudioAtomJSON.popupOpenCallback();
        AudioStorableJSON.popupOpenCallback();

    }
}

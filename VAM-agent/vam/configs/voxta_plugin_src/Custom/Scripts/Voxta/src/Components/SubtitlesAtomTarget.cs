using System.Collections.Generic;
using System.Linq;

public class SubtitlesAtomTarget
{
    private readonly MVRScript _script;

    public readonly JSONStorableStringChooser SubtitlesAtomJSON;
    public readonly JSONStorableStringChooser SubtitlesStorableJSON;
    public readonly JSONStorableStringChooser SubtitlesParamJSON;
    public readonly JSONStorableStringChooser SubtitlesActionJSON;

    private JSONStorableString _stringTarget;
    private JSONStorableAction _actionTarget;

    public SubtitlesAtomTarget(MVRScript script)
    {
        _script = script;
        SubtitlesAtomJSON = new JSONStorableStringChooser("Subtitles Atom", new List<string>(), "", "Atom");
        SubtitlesStorableJSON = new JSONStorableStringChooser("Subtitles Storable", new List<string>(), "", "Storable");
        SubtitlesParamJSON = new JSONStorableStringChooser("Subtitles String Param", new List<string>(), "", "String Param");
        SubtitlesActionJSON = new JSONStorableStringChooser("Subtitles Action Param", new List<string>(), "", "Action Param");
    }

    public void Initialize()
    {
        SubtitlesAtomJSON.setCallbackFunction = val =>
        {
            SubtitlesStorableJSON.val = "";
            SubtitlesStorableJSON.popupOpenCallback();
        };

        SubtitlesAtomJSON.popupOpenCallback = () =>
        {
            SubtitlesAtomJSON.choices = SuperController.singleton
                .GetAtoms()
                .Select(a => a.name)
                .ToList();
        };

        SubtitlesStorableJSON.setCallbackFunction = val =>
        {
            SubtitlesParamJSON.val = "";
            SubtitlesActionJSON.val = "";
            SubtitlesParamJSON.popupOpenCallback();
            SubtitlesActionJSON.popupOpenCallback();
        };

        SubtitlesStorableJSON.popupOpenCallback = () =>
        {
            var atom = SuperController.singleton.GetAtomByUid(SubtitlesAtomJSON.val);
            if (atom == null)
            {
                SubtitlesStorableJSON.choices = new List<string>();
                return;
            }
            SubtitlesStorableJSON.choices = atom.GetStorableIDs()
                .Select(s => atom.GetStorableByID(s))
                .Where(s => s.GetStringParamNames().Count > 0)
                .Select(a => a.name)
                .ToList();
        };

        SubtitlesParamJSON.setCallbackFunction = val =>
        {
            TryConnect(false);
        };

        SubtitlesParamJSON.popupOpenCallback = () =>
        {
            var storable = GetTargetStorable(false);
            if (storable == null)
            {
                SubtitlesParamJSON.choices = new List<string>();
                return;
            }
            SubtitlesParamJSON.choices = storable.GetStringParamNames();
        };

        SubtitlesActionJSON.setCallbackFunction = val =>
        {
            TryConnect(false);
        };

        SubtitlesActionJSON.popupOpenCallback = () =>
        {
            if (SubtitlesActionJSON.val == "")
            {
                SubtitlesActionJSON.choices = new List<string>();
                return;
            }
            var storable = GetTargetStorable(false);
            if (storable == null)
            {
                SubtitlesActionJSON.choices = new List<string>();
                return;
            }
            SubtitlesActionJSON.choices = storable.GetActionNames();
        };

        OnAtomRename();
    }

    public void TryConnect(bool complain = true)
    {
        if (SubtitlesParamJSON.val != "")
        {
            var storable = GetTargetStorable(complain);
            if (storable != null)
            {
                var param = storable.GetStringJSONParam(SubtitlesParamJSON.val);
                _stringTarget = param;
                if (complain && param == null)
                    SuperController.LogError($"Voxta: Subtitles parameter \"{SubtitlesAtomJSON.val}/{SubtitlesStorableJSON.val}/{SubtitlesParamJSON.val}\" not found");
            }
        }

        if (SubtitlesActionJSON.val != "")
        {
            var storable = GetTargetStorable(complain);
            if (storable != null)
            {
                var action = storable.GetAction(SubtitlesActionJSON.val);
                _actionTarget = action;
                if (complain && action == null)
                    SuperController.LogError($"Voxta: Subtitles action \"{SubtitlesAtomJSON.val}/{SubtitlesStorableJSON.val}/{SubtitlesActionJSON.val}\" not found");
            }
        }
    }

    private JSONStorable GetTargetStorable(bool complain)
    {
        if (SubtitlesAtomJSON.val == "" || SubtitlesStorableJSON.val == "")
            return null;
        var atom = SuperController.singleton.GetAtomByUid(SubtitlesAtomJSON.val);
        if (atom == null)
        {
            SubtitlesParamJSON.choices = new List<string>();
            return null;
        }
        var storable = atom.GetStorableByID(SubtitlesStorableJSON.val);
        if (storable == null)
        {
            if (complain)
                SuperController.LogError($"Voxta: Subtitles storable \"{SubtitlesAtomJSON.val}/{SubtitlesStorableJSON.val}\" not found");
            return null;
        }
        return storable;
    }

    public void RegisterStorables()
    {
        _script.RegisterStringChooser(SubtitlesAtomJSON);
        _script.RegisterStringChooser(SubtitlesStorableJSON);
        _script.RegisterStringChooser(SubtitlesParamJSON);
        _script.RegisterStringChooser(SubtitlesActionJSON);
    }

    public void OnAtomRename()
    {
        SubtitlesAtomJSON.popupOpenCallback();
    }

    public void Show(string name, string text)
    {
        if (_stringTarget != null)
        {
            if (name != "")
                _stringTarget.val = "<b>" + name + ":</b> " + text;
            else
                _stringTarget.val = text;
        }

        if (_actionTarget != null)
        {
            _actionTarget.actionCallback.Invoke();
        }
    }
}

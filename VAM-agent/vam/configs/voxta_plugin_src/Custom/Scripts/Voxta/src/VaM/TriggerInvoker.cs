using UnityEngine;
using UnityEngine.UI.Extensions.ColorPicker;

public static class TriggerInvoker
{
    private static int _invalidTriggersCounter = 3;

    public static void Invoke(VoxtaClient.AppTrigger trigger)
    {
        if (trigger.Arguments.Length < 3)
        {
            SuperController.LogError($"Voxta: Received invalid app trigger: {trigger.Name} (Not enough arguments)");
            return;
        }
        var atom = SuperController.singleton.GetAtomByUid(trigger.Arguments[0]);
        if(atom == null)
        {
            SuperController.LogError($"Voxta: Received invalid app trigger: {trigger.Name} (Atom '{trigger.Arguments[0]}' not found)");
            return;
        }
        var storable = atom.GetStorableByID(trigger.Arguments[1]);
        if(storable == null)
        {
            SuperController.LogError($"Voxta: Received invalid app trigger: {trigger.Name} (storable '{trigger.Arguments[1]}' not found on atom {atom.name})");
            return;
        }
        switch (trigger.Name)
        {
            case "Action":
                storable.CallAction(trigger.Arguments[2]);
                break;
            case "String":
                storable.SetStringParamValue(trigger.Arguments[2], trigger.Arguments[3]);
                break;
            case "StringChooser":
                storable.SetStringChooserParamValue(trigger.Arguments[2], trigger.Arguments[3]);
                break;
            case "Bool":
                storable.SetBoolParamValue(trigger.Arguments[2], bool.Parse(trigger.Arguments[3]));
                break;
            case "Float":
                storable.SetFloatParamValue(trigger.Arguments[2], float.Parse(trigger.Arguments[3]));
                break;
            case "Color":
                storable.SetColorParamValue(trigger.Arguments[2], ParseHtmlColor(trigger.Arguments[3]));
                break;
            default:
                if (_invalidTriggersCounter <= 0)
                    return;
                _invalidTriggersCounter--;
                SuperController.LogError($"Voxta: Received invalid app trigger: {trigger.Name} (Unknown trigger name)");
                if (_invalidTriggersCounter == 0)
                    SuperController.LogError("Voxta: Further invalid app triggers will be suppressed");
                break;
        }
    }

    private static HSVColor ParseHtmlColor(string html)
    {
        if(html.Length != 7 || html[0] != '#')
        {
            SuperController.LogError($"Voxta: Received invalid color: '{html}'");
            return new HSVColor();
        }

        Color color;
        if (!ColorUtility.TryParseHtmlString(html, out color))
            SuperController.LogError($"Voxta: Received invalid color: '{html}'");
        var hsv = HSVUtil.ConvertRgbToHsv(color);
        return new HSVColor { H = hsv.NormalizedH, S = hsv.NormalizedS, V = hsv.NormalizedV };
    }
}

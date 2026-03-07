using System;
using UnityEngine;
using UnityEngine.UI;
using Object = UnityEngine.Object;

// ReSharper disable UnusedMethodReturnValue.Global

public class UI
{
    private readonly MVRScript _script;

    public UI(MVRScript script)
    {
        _script = script;
    }

    public UIDynamic CreateSpacer(bool rightSide = false)
    {
        var spacer = _script.CreateSpacer(rightSide);
        spacer.height = 16f;
        return spacer;
    }

    public UIDynamicTitle CreateTitle(string text, bool rightSide = false, int fontSize = 30, bool fontBold = true)
    {
        var spacer = _script.CreateSpacer(rightSide);
        spacer.height = fontSize * 1.16f;

        var textComponent = spacer.gameObject.AddComponent<Text>();
        textComponent.text = text;
        textComponent.font = _script.manager.configurableTextFieldPrefab.GetComponentInChildren<Text>().font;
        textComponent.fontSize = fontSize;
        textComponent.fontStyle = fontBold ? FontStyle.Bold : FontStyle.Normal;
        textComponent.color = new Color(0.95f, 0.9f, 0.92f);

        return new UIDynamicTitle(textComponent);
    }

    public UIDynamicTextField CreateTextField(JSONStorableString jss, bool rightSide = false)
    {
        var textfield = _script.CreateTextField(jss, rightSide);

        var layout = textfield.gameObject.GetComponent<LayoutElement>();
        if (layout == null) throw new NullReferenceException($"Could not find {nameof(LayoutElement)} in {nameof(UIDynamicTextField)}");
        layout.minHeight = 50f;
        textfield.height = 50f;

        var text = textfield.gameObject.GetComponentInChildren<Text>();
        if (text == null) throw new NullReferenceException($"Could not find {nameof(Text)} in {nameof(UIDynamicTextField)}");
        text.fontSize = 26;

        return textfield;
    }

    public UIDynamicTextField CreateTextInput(JSONStorableString jss, bool rightSide = false)
    {
        var textfield = _script.CreateTextField(jss, rightSide);
        textfield.backgroundColor = Color.white;

        var layout = textfield.gameObject.GetComponent<LayoutElement>();
        layout.minHeight = 50f;
        textfield.height = 50f;

        var input = textfield.gameObject.AddComponent<InputField>();
        input.textComponent = textfield.UItext;
        jss.inputField = input;

        return textfield;
    }

    public UIDynamicTextField CreateMultilineTextInput(JSONStorableString jss, bool rightSide = false)
    {
        var textfield = _script.CreateTextField(jss, rightSide);
        textfield.backgroundColor = Color.white;

        var layout = textfield.gameObject.GetComponent<LayoutElement>();
        layout.flexibleWidth = 1;
        layout.flexibleHeight = 1;
        layout.minHeight = 140f;
        textfield.height = 140f;

        var input = textfield.gameObject.AddComponent<InputField>();
        input.textComponent = textfield.UItext;
        input.lineType = InputField.LineType.MultiLineNewline;
        jss.inputField = input;

        Object.Destroy(textfield.UItext.GetComponent<ContentSizeFitter>());
        Object.Destroy(textfield.UItext.GetComponent<ContentSizeFitter>());

        var textRect = textfield.UItext.GetComponent<RectTransform>();
        textRect.sizeDelta = new Vector2(textRect.sizeDelta.x, 340f);

        // input.onValueChanged.AddListener(delegate { UpdateSize(textfield.UItext, input); });
        // UpdateSize(textfield.UItext, input);

        return textfield;
    }

    /* Remove dynamic size update, it is not working well and causes some flickering
    private static void UpdateSize(Text textField, InputField input)
    {
        var rectTransform = textField.GetComponent<RectTransform>();
        var textGenerator = textField.cachedTextGenerator;

        var settings = textField.GetGenerationSettings(rectTransform.rect.size);
        settings.generationExtents.x = 505f;

        var height = textGenerator.GetPreferredHeight(
            input.text,
            settings
        );

        rectTransform.sizeDelta = new Vector2(rectTransform.sizeDelta.x, height);
    }
    */

    public UIDynamicToggle CreateToggle(JSONStorableBool jsb, bool rightSide = false)
    {
        return _script.CreateToggle(jsb, rightSide);
    }

    public UIDynamicPopup CreatePopup(JSONStorableStringChooser audioAtomJSON, bool rightSide = false, int popupPanelHeight = 600)
    {
        var popup = _script.CreateFilterablePopup(audioAtomJSON, rightSide);
        popup.popupPanelHeight = popupPanelHeight;
        return popup;
    }

    public UIDynamicPopup CreateUpwardsPopup(JSONStorableStringChooser audioAtomJSON, bool rightSide = false)
    {
        var popup = _script.CreateFilterablePopup(audioAtomJSON, rightSide);
        popup.popupPanelHeight = 600;
        popup.popup.popupPanel.offsetMin += new Vector2(0, popup.popupPanelHeight + 60);
        popup.popup.popupPanel.offsetMax += new Vector2(0, popup.popupPanelHeight + 60);
        return popup;
    }
}

public class UIDynamicTitle
{
    public readonly Text text;

    public UIDynamicTitle(Text text)
    {
        this.text = text;
    }
}

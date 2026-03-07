using System;
using UnityEngine;
    using UnityEngine.UI;
using Object = UnityEngine.Object;

public class SimpleTrigger : TriggerHandler
{
    private readonly string _startName;
    private readonly string _stopName;

    public Trigger Trigger { get; }

    public SimpleTrigger(string startName, string stopName)
    {
        _startName = startName;
        _stopName = stopName;

        Trigger = new Trigger
        {
            handler = this
        };
    }

    public void RemoveTrigger(Trigger _)
    {
    }

    public void DuplicateTrigger(Trigger _)
    {
    }

    public RectTransform CreateTriggerActionsUI()
    {
        var rt = Object.Instantiate(VamAssets.TriggerActionsPrefab);

        var content = rt.Find("Content");
        var transitionTab = content.Find("Tab2");
        transitionTab.parent = null;
        Object.Destroy(transitionTab);
        var startTab = content.Find("Tab1");
        startTab.GetComponentInChildren<Text>().text = _startName;
        var endTab = content.Find("Tab3");
        if (_stopName != null)
        {
            var endTabRect = endTab.GetComponent<RectTransform>();
            endTabRect.offsetMin = new Vector2(264, endTabRect.offsetMin.y);
            endTabRect.offsetMax = new Vector2(560, endTabRect.offsetMax.y);
            endTab.GetComponentInChildren<Text>().text = _stopName;
        }
        else
        {
            endTab.gameObject.SetActive(false);
        }

        return rt;
    }

    public RectTransform CreateTriggerActionMiniUI()
    {
        var rt = Object.Instantiate(VamAssets.TriggerActionMiniPrefab);
        return rt;
    }

    public RectTransform CreateTriggerActionDiscreteUI()
    {
        var rt = Object.Instantiate(VamAssets.TriggerActionDiscretePrefab);
        return rt;
    }

    public RectTransform CreateTriggerActionTransitionUI()
    {
        return null;
    }

    public void RemoveTriggerActionUI(RectTransform rt)
    {
        if (rt != null) Object.Destroy(rt.gameObject);
    }

    public void OnAtomRename()
    {
        Trigger.SyncAtomNames();
    }

    public void Toggle()
    {
        try
        {
            Trigger.active = true;
            Trigger.active = false;
        }
        catch (Exception exc)
        {
            SuperController.LogError($"Voxta: Error while activating trigger: {exc}");
        }
    }

    public void SetActive(bool active)
    {
        try
        {
            Trigger.active = active;
        }
        catch (Exception exc)
        {
            SuperController.LogError($"Voxta: Error while activating trigger: {exc}");
        }
    }
}

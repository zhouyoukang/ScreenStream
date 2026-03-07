using System;
using System.Collections;
using AssetBundles;
using UnityEngine;

public static class VamAssets
{
    public static RectTransform TriggerActionsPrefab;
    public static RectTransform TriggerActionMiniPrefab;
    public static RectTransform TriggerActionDiscretePrefab;
    // ReSharper disable once NotAccessedField.Global
    public static RectTransform TriggerActionTransitionPrefab;

    public static IEnumerator LoadUIAssets()
    {
        foreach (var x in LoadUIAsset("z_ui2", "TriggerActionsPanel", prefab => TriggerActionsPrefab = prefab)) yield return x;
        foreach (var x in LoadUIAsset("z_ui2", "TriggerActionMiniPanel", prefab => TriggerActionMiniPrefab = prefab)) yield return x;
        foreach (var x in LoadUIAsset("z_ui2", "TriggerActionDiscretePanel", prefab => TriggerActionDiscretePrefab = prefab)) yield return x;
        foreach (var x in LoadUIAsset("z_ui2", "TriggerActionTransitionPanel", prefab => TriggerActionTransitionPrefab = prefab)) yield return x;
    }

    private static IEnumerable LoadUIAsset(string assetBundleName, string assetName, Action<RectTransform> assign)
    {
        var request = AssetBundleManager.LoadAssetAsync(assetBundleName, assetName, typeof(GameObject));
        if (request == null) throw new NullReferenceException($"Request for {assetName} in {assetBundleName} assetbundle failed: Null request.");
        yield return request;
        var go = request.GetAsset<GameObject>();
        if (go == null) throw new NullReferenceException($"Request for {assetName} in {assetBundleName} assetbundle failed: Null GameObject.");
        var prefab = go.GetComponent<RectTransform>();
        if (prefab == null) throw new NullReferenceException($"Request for {assetName} in {assetBundleName} assetbundle failed: Null RectTransform.");
        assign(prefab);
    }
}

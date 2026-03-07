    using System.Linq;
    using System.Text.RegularExpressions;
    using SimpleJSON;

    public static class ActionsParser
    {
        private static readonly Regex _splitRegex = new Regex(@"(\r?\n){2,}", RegexOptions.Compiled | RegexOptions.ExplicitCapture);

        public static JSONArray Parse(string val)
        {
            var functionsListJson = new JSONArray();
            if (string.IsNullOrEmpty(val))
            {
                return functionsListJson;
            }

            var blocks = _splitRegex.Split(val);
            for (var blockIndex = 0; blockIndex < blocks.Length; blockIndex++)
            {
                var block = blocks[blockIndex];
                var lines = block.Split('\r', '\n');
                if (lines.Length == 0) continue;

                var functionJson = new JSONClass();
                var effectJson = new JSONClass();
                functionJson["effect"] = effectJson;

                var relevantLines = 0;
                for (var lineIndex = 0; lineIndex < lines.Length; lineIndex++)
                {
                    var line = lines[lineIndex];
                    if (line == "") continue;
                    if (line.StartsWith("#")) continue;
                    relevantLines++;
                    var parts = line.Split(':');
                    if (parts.Length != 2)
                    {
                        SuperController.LogError($"Voxta: Invalid function line (Found {parts.Length - 1} colons, should be only one) (block {blockIndex + 1}, line {lineIndex + 1}): '{line}'");
                        continue;
                    }

                    var key = parts[0].Trim();
                    var value = parts[1].Trim();
                    switch (key)
                    {
                        // Definition
                        case "action":
                            functionJson["name"] = value;
                            break;
                        case "short":
                            functionJson["shortDescription"] = value;
                            break;
                        case "when":
                            functionJson["description"] = value;
                            break;
                        case "layer":
                            functionJson["layer"] = value;
                            break;
                        case "finalLayer":
                            bool finalLayer;
                            functionJson["finalLayer"].AsBool = bool.TryParse(value, out finalLayer) && finalLayer;
                            break;
                        case "timing":
                            functionJson["timing"] = value;
                            break;
                        case "cancelReply":
                            bool cancelReply;
                            functionJson["cancelReply"].AsBool = bool.TryParse(value, out cancelReply) && cancelReply;
                            break;
                        // Conditions
                        case "match":
                        case "matchFilter":
                            var matches = new JSONArray();
                            matches.Add(value);
                            functionJson["matchFilter"] = value;
                            break;
                        case "flags":
                        case "flagsFilter":
                            var flagsJson = new JSONArray();
                            foreach(var flag in value.Split(',').Select(x => x.Trim()).Where(x => x != ""))
                                flagsJson.Add(flag);
                            functionJson["flagsFilter"] = flagsJson;
                            break;
                        case "roleFilter":
                            functionJson["roleFilter"] = value;
                            break;
                        // Effects
                        case "effect":
                            effectJson["effect"] = value;
                            break;
                        case "note":
                            effectJson["note"] = value;
                            break;
                        case "secret":
                            effectJson["secret"] = value;
                            break;
                        case "instructions":
                            effectJson["instructions"] = value;
                            break;
                        case "event":
                            effectJson["event"] = value;
                            break;
                        case "generate":
                            bool generate;
                            effectJson["generate"].AsBool = bool.TryParse(value, out generate) && generate;
                            break;
                        case "trigger":
                            effectJson["trigger"] = value;
                            break;
                        case "setFlags":
                            var setFlags = new JSONArray();
                            foreach (var flag in value.Split(',').Select(x => x.Trim()).Where(x => x != ""))
                                setFlags.Add(flag);
                            functionJson["setFlags"] = setFlags;
                            break;
                        case "activates":
                            var activates = new JSONArray();
                            foreach (var name in value.Split(',').Select(x => x.Trim()).Where(x => x != ""))
                                activates.Add(name);
                            functionJson["activates"] = activates;
                            break;
                        default:
                            SuperController.LogError($"Voxta: Invalid function key '{key}' (block {blockIndex + 1}, line {lineIndex + 1})");
                            break;
                    }
                }

                if (relevantLines == 0) continue;

                if (!functionJson.HasKey("name") || functionJson["name"].Value == "")
                {
                    SuperController.LogError($"Voxta: A function block is missing an name: {functionJson} (block {blockIndex + 1})");
                    continue;
                }

                functionsListJson.Add(functionJson);
            }

            return functionsListJson;
        }
    }

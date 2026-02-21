---
description: SWE Pipeline - optimized for weaker models handling complex long-chain requirements. User gives one sentence, AI delivers complete solution.
---

# SWE Pipeline: Top-Level Requirement to Complete Delivery

> Optimized for SWE/weaker models. Every step is EXPLICIT with concrete outputs.
> Source: Anthropic Context Engineering + Long-Running Agent Harness (2025)

## TRIGGER
User provides a high-level requirement like:
- "Add clipboard sync feature"
- "Make the file manager support drag and drop between folders"
- "Add a battery optimization mode"

## Step 1: DECOMPOSE (Mandatory, never skip)

**Action**: Break the user's requirement into a concrete feature list.

1. Parse the user's sentence to extract:
   - **WHAT**: The core capability being requested
   - **WHO**: Who benefits (end user / developer / AI agent)
   - **WHERE**: Which modules are affected (use code-index.md)
   
2. Generate a feature list in this format:
`json
[
  {"id": "F1", "description": "...", "files": ["InputService.kt", "InputRoutes.kt"], "complexity": "S/M/L", "passes": false},
  {"id": "F2", "description": "...", "files": ["index.html"], "complexity": "S/M/L", "passes": false}
]
`

3. Show the feature list to the user for confirmation (unless TRIVIAL - 1-2 features, all S complexity).

**Output**: Feature list with estimated file changes.

---

## Step 2: RESEARCH (Mandatory for M/L complexity, skip for S)

**Action**: Search for the best implementation pattern.

// turbo
1. **External search** (2-3 queries):
`
search_web: "best open source <feature> Android/Web GitHub"
search_web: "<feature> REST API design patterns"
search_web: "<feature> UX best practices"
`

2. **Internal pattern match**:
   - Read .windsurf/code-index.md for insertion points
   - Read .windsurf/quick-recipes.md for matching template
   - Check if similar feature already exists in codebase (grep_search)

3. **Synthesize**: Pick the TOP pattern from external + internal. Write a 3-5 line implementation plan per feature.

**Output**: Implementation plan with references.

---

## Step 3: IMPLEMENT (One feature at a time)

**Action**: Implement features incrementally, following this exact order:

### For each feature (F1, F2, ...):

**3a. Backend first** (if needed):
- Read the EXACT insertion point from code-index.md
- Read only the surrounding 20-30 lines of context (NOT the whole file)
- Add the new method to InputService.kt
- Add the route to InputRoutes.kt
- Use requireInputService pattern (see quick-recipes.md)
- Use JSONObject for all responses (NEVER string concat)

**3b. Frontend second** (if needed):
- Read the EXACT section from code-index.md
- Add command menu item in buildMenuHTML()
- Add toggle function if needed
- Add keyboard shortcut if needed
- Use escapeHtml() for ALL dynamic content

**3c. Mark feature as done**:
`
Feature F1: DONE - Added /new-endpoint + UI toggle
`

### Critical rules:
- **ONE feature at a time** - do not try to implement everything at once
- **Read minimal context** - use code-index.md line numbers, read only 30 lines around insertion point
- **Follow existing patterns EXACTLY** - copy the nearest similar feature's code structure
- **Never leave broken state** - each feature should be independently functional

**Output**: All features implemented.

---

## Step 4: BUILD (Auto-run)

// turbo
**Action**: Compile the project.
`powershell
 = "C:\Program Files\Processing\app\resources\jdk";  = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk"; & "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache 2>&1 | Select-Object -Last 20
`

If compile fails: Fix error, recompile (max 2 rounds).

**Output**: BUILD SUCCESSFUL

---

## Step 5: DEPLOY + VERIFY (Auto-run if device connected)

// turbo
**Action**: Deploy and verify.
`powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild
`

Then verify new endpoints:
`powershell
# For each new API endpoint:
curl.exe -s http://127.0.0.1:8086/<new-endpoint>
`

**Output**: All new APIs responding correctly.

---

## Step 6: DOCUMENT

**Action**: Update docs.
1. Add new features to FEATURES.md
2. Update STATUS.md if significant
3. Update code-index.md with new line numbers if file grew significantly

**Output**: Docs synchronized.

---

## Step 7: SUMMARY

**Action**: Output completion report.
`
## Done
- [1-2 lines: what was built]
- Files: [list]  
- APIs: [new endpoints]
- Build: SUCCESS/FAIL
- Deploy: SUCCESS/PENDING
- Features: F1 PASS, F2 PASS, ...
`

---

## Emergency: Context Running Low

If context is getting long (many tool calls):
1. Write progress to a temp note: what's done, what's left
2. Summarize current state
3. Continue from the note in next turn

## Anti-Patterns (things that waste time)

- DO NOT read entire 3600-line files. Use code-index.md line numbers.
- DO NOT research for TRIVIAL tasks. Just use quick-recipes.md.
- DO NOT compile after each feature. Batch all features, compile once.
- DO NOT ask user for confirmation on obvious next steps. Just do it.
- DO NOT implement something without checking if a similar pattern exists first.

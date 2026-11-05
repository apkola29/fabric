# Verification of the catalog of MCP servers, round 7: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the files in the state of the review snapshot of round 7 (the paths in the reply are relative to it) and took: the four claims of the fact list that Grok had found too weak in round 6 and the other claims that changed in rounds 5 and 6 (mutations of live page text of its own), and the closure of the four round-6 findings of Grok. The author's checks and the dispositions are in [mcp-catalog-findings.md](mcp-catalog-findings.md).

K6-F1 | P | the restore sentence negated | “You cannot restore” now produces DRIFT, but a conditional restore sentence and a billing exception still produce PASS. See F1.
K6-F2 | P | the reason negated in front | Both added regressions are rejected. However, an explicitly obsolete prompt still passes, as do negated input descriptions. See F2–F3.
K6-F3 | P | not `eventstream_create_from_definition` | The inserted negation is caught, but “No longer supported” before the Validation label is not. See F4.
K6-F4 | P | Anthropic Claude CLAUDE.md OpenAI Codex AGENTS.md | The original single-row decoy is rejected. An unsupported-file column or a two-row legacy note still satisfies the pattern. See F5.

## FINDINGS

All paths below are relative to `CLONE7\new`. These are reproduced detector failures on scratch mutations, not assertions that the live services have the mutated behavior.

### F1 — Medium — `page-onelake-soft-delete-billing`
**Location:** `scripts\facts.json:105–106`  
**Quote:** “bills them at the active rate”

The patterns still match sentence prefixes. Replacing the billing sentence’s final period with:

`only for the first day; after that, soft-deleted data is free.`

leaves the entire claim **PASS**. Likewise, adding `only if the workspace retention setting has not changed` to the restore sentence passes.

**Suggested replacement:** Require complete affirmative sentences, including their terminal punctuation, rather than prefixes. Add both suffix mutations as negative tests. The new “cannot” test is effective but does not establish the claimed whole-sentence binding.

### F2 — Low — `page-catalog-tools-foundry-mcp`: obsolete prompt
**Location:** `scripts\facts.json:528–529`  
**Quote:** “an example prompt gives as the reason”

I prefixed the existing example’s HTML list item with `Do not use this obsolete prompt:` and followed its quoted prompt with an explicit denial that Managed Compute allocates billable dedicated GPUs. The claim remained **PASS**. No duplicate or moved example was needed.

**Suggested replacement:** Match the complete affirmative example item within the model-deployment examples section, including its beginning and ending—not a globally searchable substring inside a disavowed quotation. Add this negative-prefix case.

### F3 — Low — `page-catalog-tools-foundry-mcp`: wrong cell supplies inputs
**Location:** `scripts\facts.json:528–529`  
**Quote:** “a file directory tool takes a permission mode”

I removed permission mode from `session_file_mkdir`’s **Key inputs** cell and placed `A permission mode (optional) is no longer accepted` solely in its **Description** cell. The claim remained **PASS**.

Appending `is no longer supported` after `instanceCount (optional)` also passed.

**Suggested replacement:** Bind parameter assertions to the actual Key inputs cell and its affirmative parameter list. Tempering against the next tool row prevents cross-row borrowing, but not borrowing a negated mention from another cell of the same row.

### F4 — Low — RTI Eventstream and Map claims
**Claims:** `gh-rti-mcp-eventstream-definition-tools`, `gh-rti-mcp-map-definition-tools`  
**Location:** `scripts\facts.json:649–653`  
**Quote:** “lists eventstream_create_from_definition in its validation bullet”

These in-place changes still produce **PASS**:

- Prefix the Validation bullet with `- **No longer supported**:`, leaving `**Validation**:` afterward.
- Prefix the `eventstream_create` or `map_update_definition` bullet with the same unsupported marker.

Moving the original Validation list or Map replacement description into a removed-capabilities section also passes after changing the active entry.

**Suggested replacement:** Scope matches to the Eventstreams or Map section, then anchor complete bullet lines using horizontal whitespace—not unrestricted `\s` across lines. Require the expected label/tool at the start of the bullet and its description/list through the line ending.

### F5 — Low — `page-vscode-custom-instructions-agents-md`
**Location:** `scripts\facts.json:315–316`  
**Quote:** “lists CLAUDE.md for Anthropic Claude”

I added a third table column headed **Unsupported legacy file**, emptied Claude’s current instructions-file cell, and put `CLAUDE.md` in that third column. The flattened text still matches the new pattern, yielding **PASS**.

Changing Claude’s current file to `AGENTS.md` and retaining the two-row mapping in an explicitly obsolete note also passes.

**Suggested replacement:** Check the Claude row’s actual current-file cell in the HTML table. Adjacency to the following Codex row does not establish column membership. Add a structured HTML fixture with the unsupported third column.

### F6 — Low — `page-pbi-authoring-remote-objects`
**Location:** `scripts\facts.json:569–570`  
**Quote:** “in its bulk bullet”

Prefixing the bulk list item with `No longer supported:` still produces **PASS**. Removing that item from the active capability list and moving it under **Unsupported operations** also passes.

**Suggested replacement:** Scope the check to **What you can do with the Power BI Authoring MCP server**, and require the complete affirmative list item there. Test both a negated item and relocation outside that section.

### F7 — Medium — `page-datafactory-pipeline-flag`: lost platform scope
**Location:** `scripts\facts.json:542–543`  
**Quote:** “its tools appear only with the --pipeline flag”

I changed the requirement to say the flag is required **only on Linux**, and changed the accompanying availability sentence to say Windows tools are always available. Both current prefix patterns still matched; the claim remained **PASS** despite losing its platform-independent scope.

**Suggested replacement:** Match the complete existing requirement and availability sentences, including `in your server configuration.` and `in Copilot's tool list.` Add the Linux-only/Windows-available mutation.

### F8 — Low — `page-datafactory-pipeline-flag`: negated copy activity
**Location:** `scripts\facts.json:542–543`  
**Quote:** “a copy activity that reads from a Blob Storage source”

Changing the prompt from including a Copy Activity to including `a Lookup Activity, not a Copy Activity` still produces **PASS**. The pattern starts at `Copy Activity`, after the negation, and borrows the unchanged subsequent tool call.

**Suggested replacement:** Include the prompt’s affirmative opening—`Update the definition ... to include a Copy Activity`—through the directly following tool-call sentence. Add this negated-activity mutation.

### F9 — Low — `gh-datafactory-mcp-readme-preview-and-dnx`
**Location:** `scripts\facts.json:545–546`  
**Quote:** “lists, in the Advanced row”

Two independent mutations pass:

- Replace **all four** preview annotations with `generally available, not *(Preview)*`. The arbitrary same-line spans still satisfy both preview checks.
- Change the current Advanced row to read-only topics and move its original contents beneath **Removed knowledge files**. The global row pattern still matches.

**Suggested replacement:** Require affirmative tool-list syntax immediately before the preview marker, rather than arbitrary same-line text. Restrict the Advanced-row match to the current **What's Covered** table before **Usage**. Add both mutations.

## CHECKED AND FINE

- All eight claims passed against seven freshly fetched public URLs; every fetch returned HTTP 200.
- **34/34 `ClaimPrecisionTests` passed.**
- Replaying the four relevant test methods against round-6 patterns produced exactly **five expected assertion failures and zero errors**. Thus, the newly added regression cases are non-vacuous.
- Ran **30 asserted, non-no-op live-source mutations**: **9 DRIFT**, **21 PASS**. Related variants are not separate findings.
- Reproduced the acknowledged wholesale copied-sentence limitation without counting it as an additional finding.
- Reproduction and results persist in `scratch7-gpt\run_mutations.py` and `scratch7-gpt\mutation-results.json`.
- All report quotes were checked verbatim and contain at most 12 words. Reviewed source-file hashes remained unchanged.

**Not confirmed:** full sentence/row/list-bound guarantees for these eight checks. The full 123-test suite, unassigned catalog code, and live MCP/tenant behavior were not tested. No installation or sign-in occurred.

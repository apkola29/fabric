# Fourth verification of the reference pack, the 24 rows changed after the third: lens C, from the page to the line (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It checked the 23 checks and the note that were changed after the third verification, with a verbatim quote for each row that a program looked up in the cited section. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

std-arc-02 | S | Store everything exactly as it arrives. No changes are allowed.
std-arc-04 | S | Whenever possible, keep the data in its original format.
std-arc-15 | S | before you pause a capacity that supports production workloads.
std-del-01 | S | After you create the item definitions
std-del-02 | S | If your Git repository also needs to hold workflow files,
std-del-03 | S | A validation pipeline can run any time a developer creates
std-del-06 | S | If necessary, update the logicalId and/or display names in any dependencies.
std-del-09 | S | If you're using the test stage to simulate real life data usage,
std-del-10 | S | you probably want all BI creators for a specific workspace
std-del-12 | S | some, but not all, workspace item types support:
std-del-14 | S | Environment-specific settings that you commit to Git cause one issue.
std-del-17 | S | You still need to run the notebook in the target workspace
std-del-18 | S | Fabric makes it possible to extend the item definition of notebooks
std-gov-01 | S | for potentially high impact modifications.
std-gov-04 | S | Its capacity monitoring experience is currently in preview,
std-gov-10 | S | when a Fabric item does not support the standard pattern.
std-ops-03 | S | Test environments should use sample or anonymized data sources
std-ops-06 | S | escalation paths so higher severity alerts reach the appropriate support teams quickly.
std-rel-04 | S | If upstream gateways or databases go down, your workloads may stall
std-sec-10 | S | for supported Fabric workloads and supported data sources.
std-sec-14 | T | Do not store secrets in notebooks, scripts, or pipelines. | Introduced credentials need not change a security setting; blanket flagging also captures code contents covered by std-sec-01.
std-sec-15 | S | you may need workspace segmentation to separate supported and unsupported items.
std-sec-16 | S | When private connectivity is required for selected workspaces,
note-del-4 | S | variable libraries should usually be your first choice for parameterization

## FINDINGS

**Result: 23 supported rows; one wrong-tag finding.** All 24 evidence quotes were mechanically verified against their cited source sections; every quote contains at most 12 words.

### Low — std-sec-14: credential use is not necessarily a security-setting change

The Key Vault and parameterization guidance is supported. The problem is the blanket instruction to **“Flag a credential that the change introduces”**, combined with an applicability scope covering any notebook, script or pipeline needing a credential.

A new notebook can retrieve an existing secret without changing identities, permissions or security settings. The clarified policy distinguishes such code contents from setting changes. Embedded secrets already receive the deterministic content check in `std-sec-01`.

**Evidence:**

- WAF security, “Secret management”: “Do not store secrets in notebooks, scripts, or pipelines.”
- Same section: “Use Azure Key Vault, with dynamic retrieval at runtime.”
- “Secure Development Lifecycle (SDL)” supports key vault references or parameterization rules for sensitive pipeline configuration.
- The Well-Architected header expressly distinguishes file contents from setting changes.

**Suggested replacement:**

- `std-sec-14` Does code that needs a secret retrieve it from Azure Key Vault at runtime, with sensitive pipeline configuration supplied through key vault references or parameterization rules? [review] Applies to: secret retrieval in a notebook, script or pipeline. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".

Actual changes to authentication, permissions or security settings must still be refused and escalated under the factory policy. The replacement does not authorize them.

## HEADERS

### well-architected.md

The changed `Tags:` paragraph accurately describes the clarified policy:

- Deterministic content checks can be `[gate]`, even when their topic concerns secrets.
- `[review]` represents judgement.
- `[flag]` concerns the prohibited categories of change, not every security-related topic.
- Questions about destructive operations do not authorize execution.

Its tags **do not completely agree** with that paragraph because `std-sec-14` indiscriminately flags introduced credentials. Otherwise, the distinction is reflected appropriately: `std-sec-01` gates embedded-secret contents, while `std-sec-03` reviews security-validation workflows.

### delivery-and-lifecycle.md

The changed `Tags:` paragraph is accurate and agrees with the file’s tags. In particular:

- `std-del-15` correctly gates credential-bearing repository contents.
- `std-del-10` flags production deployment permissions.
- `std-del-19` flags automation identity concerns.
- Runtime/workspace knowledge, such as the active variable-library value set, remains an `Ask:` question rather than a deterministic gate.

The excluded `toolchain\skills\factory-standards\SKILL.md` was not sought.

## CONFLICTS

No additional **X** finding was confirmed.

- `std-del-01` is limited to the feature-workspace process after initial definitions exist. Its neighbouring note correctly preserves the simpler direct-update development process.
- `std-del-06` fits the explicit copied-item exception in `std-del-05`; the logicalId source tension remains disclosed.
- `std-del-12`, `std-del-14` and `note-del-4` are compatible: supported variable-library references are preferred, while committed environment-specific values still need environment-specific adjustment.
- `std-gov-10` supplies an approved alternative when the selected deployment pattern cannot use the item’s supported capabilities; it does not waive the risk-based controls in `std-gov-05` through `std-gov-07`.
- The bronze immutability versus format-conversion ambiguity affecting `std-arc-02` and `std-arc-04` is accurately disclosed in `note-arc-1`; the correction introduces no false reconciliation.

The `std-sec-14` tag-boundary mismatch is the finding above, not a separate conflict finding.

## DANGER

No reviewed row, interpreted with its file header, directly instructs the factory to perform a prohibited operation.

- `std-arc-15` reviews capacity-pausing automation and production unavailability; the architecture header explicitly makes this a question, not permission to pause capacity.
- `std-del-17` asks whether schema-update notebook execution is included in the release process. It does not authorize the verifier to execute that notebook or perform destructive schema operations.
- The network, key and permission rows present guidance behind `[flag]`, not executable authorization.

The review remained read-only. No credentials, pushes, live resource operations or file modifications were used.

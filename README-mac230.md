# macOS Hélène 2.3 RC acceptance harness

Root `dff311ef`; final harness author `85f19e49`, continuing the preliminary
`895cdff9` controls. **Harness ready for parent dispatch, not a native PASS.**
The product source and archives stay frozen. Parent alone publishes sanitized
control files/inputs and dispatches public standard Mac Actions. No child CI,
release, owner profile, installed Jarvis, model, SSH, local Docker or WSL effects.

## Exact public publication footprint

Publish ONLY these six files from this directory:

| Local file | Public helper-repository path |
|---|---|
| `mac230.yml` | `.github/workflows/mac230.yml` |
| `mac230_prepare.py` | `mac230_prepare.py` |
| `mac230_full.py` | `mac230_full.py` |
| `mac230_consumer.py` | `mac230_consumer.py` |
| `test_mac230_harness.py` | `test_mac230_harness.py` |
| `README.md` | `README-mac230.md` (or existing appropriate README) |

Do **not** publish `preparation/`, local `.git`, `.ouroboros`, preimages, runtime
or npm preparation results wholesale, private input paths, task logs or profiles.
Existing helper repo: `josephsteuerjr/helene-mac-migration-2410`. Parent chooses the
exact branch/commit, reads back these bytes, then dispatches that exact ref.

Workflow inputs (three, no hidden environment configuration):

- `manifest_url`: explicit public HTTPS URL to parent's sanitized input JSON.
- `manifest_sha256`: lowercase SHA256 of its complete exact bytes.
- `mode`: `qualify` for the full/native journey; `capture-executor` only for a new
  explicit executor observation. Capture is NOT a qualification PASS.

Standard `macos-15` ARM64, Node `22.14.0`, driver Python `3.14`, 180-minute cap.
Driver dependencies (`psutil`, Playwright/Chromium, Quartz) are separate from
product runtime dependencies. Changing the runner tools may cause the real
version-bound lock to refuse; that is evidence, not grounds to bypass it.

## Input manifest

All URLs below are placeholders, deliberately invalid. Parent supplies observed
public URLs; no inferred latest/tag/download address is used by the driver.

```json
{
  "format": "helene-mac230-acceptance-input.v1",
  "target": "macos-arm64",
  "version": "2.3.0-rc.1",
  "base_version": "2.2.17",
  "base": {
    "name": "Helene-2.2.17-macos-arm64.zip",
    "url": "PARENT_OBSERVED_PUBLIC_OLD17_URL",
    "sha256": "49a8912a44efdba2c3a4e409de9b672b605c7665093147bf2a6e4e474c593e38",
    "bytes": 127880161
  },
  "candidate": {
    "name": "Helene-2.3.0-rc.1-macos-arm64.zip",
    "url": "PARENT_OBSERVED_PUBLIC_RC_URL",
    "sha256": "cc9584997fdb6fa7be0baef6844acdd42eb05a584cf5134940d2aeb43e590657",
    "bytes": 174292095
  },
  "broken": {
    "name": "Helene-2.3.1-rc.1-macos-arm64.zip",
    "url": "PARENT_OBSERVED_PUBLIC_SYNTHETIC_BADNEXT_URL",
    "sha256": "PARENT_EXACT_BADNEXT_SHA256",
    "bytes": 1
  },
  "broken_version": "2.3.1-rc.1",
  "npm_cache": {
    "name": "mac230-npm-cache.zip",
    "url": "PARENT_OBSERVED_PUBLIC_NPM_CACHE_URL",
    "sha256": "PARENT_EXACT_CACHE_SHA256",
    "bytes": 1
  },
  "feed_url": "PARENT_OBSERVED_EXACT_RC_RELEASE_API_OR_COMPATIBLE_FEED_URL",
  "source_inputs_sha256": "60d64beba7faffaf41b6c5ef0063120bf89b86e639928a2ec7cf8a7eb9f1bef4",
  "verification_bundle_sha256": "5c9970631b0048af29767082dfee86fb61bb0133bf47c949a9be23c07c9273c4"
}
```

Known candidate identity above comes from this task's exact local archive metadata
and parent's freeze. Base byte count is inherited from parent's earlier published
observation, not a new network read. Parent rechecks all URLs/SHA/sizes before
publication. A changed package/bundle needs a new exact manifest, not editing the
working extraction or relaxing a lock.

`npm_cache` is an ordinary ZIP whose single top level is **`cache/`**, containing
only the public-registry npm cache prepared for exact app/mobile/miniapp/**remote**
locks. Do not zip the whole preparation directory or any home/auth/npmrc. The
cache ZIP is pinned by complete SHA/size; npm later verifies actual content using
source lock integrities. Extraction refuses symlinks/traversal/casefold collisions
and preserves Unix modes. The cache path is selected explicitly per run as
`work/npm-cache/cache`; frozen executor-lock/manifest bytes are never rewritten.

`broken` is required for `qualify`, optional for capture. Parent builds a coherent
synthetic BADnext input including actual version/admission/package inventory and
an application-entry startup failure. It is **not** a supported future release.
`broken_archive()` remains a narrow fixture-tested primitive; the native journey
does not fabricate packages or set a ready/review/cancellation marker by hand.

## Full applicable manifest: actual packaged interpreter/API

`mac230_full.py run` launches **candidate/runtime/bin/python3** with only selected
non-secret environment and an isolated home. It imports the shipped modules and:

1. Calls normal `source_admission.activate(program)`; records package-manifest
   before/after SHA and activation journal. Compatibility view is not pristine B.
2. Loads the exact version-bound complete verification bundle, then calls
   `source_merge.create(program/tree, program/tree, program/tree, new_plan, exe=...)`.
3. Records operation identities and per-run executor paths; calls
   `update_composition.prepare`, observes its signature, then
   `source_update_battery.prepare` and **`validate`**. A completed attempt is not
   green until actual `validate` returns. No handwritten ready/apply/panel PASS.
4. Preserves the exact report/cases/raw logs and compact independent result.

The executor binds packaged Python and `helene-body`/`helene-bridge` absolute
paths+SHA, and only `HELENE_BODY_DIR`/`HELENE_BODY_BIN` native environment keys.
Node/npm/Cargo tool observations remain checked by the shipped lock. Parent
confirmed no current Rust/Cargo producer delta; final recipe intentionally has
`native_lanes=[]`, all four locked npm preparation lanes, all Python/Node suites
and the same three app/mobile/miniapp builds. No speculative Cargo/cache surface
or extra native compilation is added here.

Frozen bundle currently has **295 lanes, not 295 cases**, and
`allowed_test_skips={}`. That is an initial diagnostic contract, not permission to
bless dependency/input skips later. Red, missing or undeclared skipped cases stay
red with full observations. Native journey still runs after a red full step;
Actions overall cannot be green if its full step failed. This is useful separation,
not a substitute for parent inspection of every failure/skip.

## Native journey: old17 → RC, detached observer, BADnext rollback

Every profile, memory text, identity, code copy and Git edit is synthetic under
runner work. `setup_complete=false`, no account/credentials, disabled relay/TTS;
no Stop marker is erased or used to fake a positive startup.

1. Invoke **old17's packaged** `source_admission.activate` BEFORE copying selected
   pristine code. Preserve its journal and manifest-before/after observations.
   Create separate selected code from those activated bytes and Git/workspace
   fixture, then open actual `Helene.app/Contents/MacOS/Helene` with Quartz capture.
   Do **not** label this Mac17 input as Windows2.1.1.
2. Old17's real `update_check` resolves exact RC/hash. Old17 has **no
   `update_start` command**: use its real `update_download` → `update_install`.
   It invokes incoming `.app --migration-wizard`; final `helene_setup` recognizes
   this in-place old-update shape and directly admits a persistent migration job.
   Historical `.python-migrator` descriptor explicitly says `wizard_opened=false`.
   Do not try to screenshot or call `migration_install` on that non-window.
   Require durable exact job/profile/target/mode, distinct live host PID/birth,
   matching handoff descriptor and actual eventual native startup proof.
3. No driver `python_ready` call. Require production renderer's migration proof,
   completed transaction, correct version and real Cocoa window **before** opening
   separate Chromium. Browser PNG/text are separate observations, not Cocoa proof.
4. RC's real `update_start` admits before I/O. Pause by authenticated production
   session RPC, close only observer, reopen/rejoin same PID/birth/generation and
   same job, resume production job and observe mechanical/native cutover. No new
   migration UI or replacement semantic job is manufactured by the harness.
5. Use parent's pinned BADnext in ordinary `update_install`. Require startup
   failure, actual `rollback_completed` progress, restored entry hash, reopened
   previous native app/version and exact selected profile/Git/workspace custody.
   Cancel attention through production RPC; require settled `cancelled` before
   unrelated work. Never delete/reset cancellation to proceed.
6. Explicit Exit; move program to spaced/Unicode path; reopen same external data
   identity and retain relocatable program-owned paths.
7. Add `.py` delta to the **actually configured selected code**, not stock
   `program/tree`. Ordinary modified-preserve Update must block without genuine
   author/battery/review authority, preserving delta/current window. A genuine
   `waiting_agent` source pipeline is expected even while the job is `running`;
   observe that bound pipeline, do not demand/fabricate an attention error. Detach window,
   cancel that same job via persistent owner, then explicit Exit.

Pristine positive checks compare actual selected source inventory to the release's
actual `code-upstream.json`; no source resealing to force equality. Git checks
retain HEAD/reachable commits/refs/config/index and staged/unstaged/untracked
**excluded workspace**. Workspace status is filtered to `workspace/`; upstream
runtime source is supposed to change, so whole-source porcelain equality would
be a false invariant. Workspace file bytes are separately hashed.

This proves neither genuine authored-runtime successful reconciliation nor a live
model/reviewer campaign. Parent explicitly owns that separate acceptance branch.
No physical microphone/phone/sign-in/TCC/all-provider/CU parity claim is made.

## Tests, evidence, and next parent action

Local command: `C:/Program Files/Python314/python.exe -B -m unittest -v test_mac230_harness`.
Control tests cover safe cache/ZIP inputs, exact identity, full-adapter ordering and
negative validation with **fake API modules**, explicit native/cache bindings,
old-before-copy order and old/new command split, isolated environment, real Git
fixture, and absence of forged native-ready/review state. Their green result is
**Windows harness-control evidence only**, not actual full/native Mac execution.

Preimages of the six original controls are retained in `.preimages-85f19e49.zip`;
original assertion/scenario changes are described above rather than relabelled as
an old native PASS. Native runtime/API reads used frozen source and exact donor
ZIP modules; no owner persona or original profile was read.

Parent: publish six controls; create explicit sanitized cache ZIP and exact input
manifest with real RC/base/BADnext/feed/cache URLs; dispatch `qualify` on the exact
published commit. Read `full/full-summary.json`, `full/full-verification.json`, all
full `test-battery` reports and `native/native-result.json`. Inspect native PNGs
**with vision**; `screenshots_visually_judged=false` deliberately remains until
that happens. Read failure logs even if another branch passes. Native diagnostic
copies are explicitly selected synthetic logs with observed capability tokens
redacted; no control descriptors/profile/home HTML are uploaded.

Forced cleanup or cleanup errors keep native result red. Sampling measured
PID/birth and Quartz windows cannot prove absence of sub100ms flashes. No native
Action was dispatched by this author; historical preparation runs are not this
final product's acceptance.

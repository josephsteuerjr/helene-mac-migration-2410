# Existing Mac Hélène → Python application

This one-time path is separate from routine Python updates. The delivered folder
contains **Migrate Helene.app** beside **Helene.app**, `runtime/` and `app/`.
Move the complete new folder to a writable location separate from the old one.
No privileged broker, uninstaller or automatic source deletion is involved.

1. In the old Hélène choose **Quit**, not merely close/hide its window. Disable
   its previous login start or service first; a loaded launchd integration bound
   to that installation is refused, not silently unloaded with administrator rights.
2. Open **Migrate Helene.app** in Finder. Choose the old folder (or its `.app`)
   and an absolute new data-home path outside both application folders. Confirm
   that the old application is Quit and will remain closed during migration.
3. Choose **Подготовить перенос**. Actual same-user executable/argument/cwd
   observations and OS `flock` leases are checked, including effective external
   code/data/custom-script roots. Configurations, essential backup, complete
   selected data and executable source are preserved. Git HEAD/index, staged,
   unstaged and untracked bytes travel together. Configured external roots are
   copied too, not silently shared with the donor. Existing lease bytes are not
   rewritten; a missing `.desktop-owner.lock` can be created empty in the source
   data directory. This operational file is excluded from the preserved copy.
4. Choose **Открыть новую Hélène**. Only the new rendered application and its
   controller can write startup confirmation. Until then the UI says prepared
   or launch requested, not success. Setup-incomplete profiles prove the local
   channel/UI; configured runner profiles additionally require runner/code proof.

The old installation is retained, including its memory/config/source. Do not run
both copies simultaneously: they still contain the same remote account/session
credentials. The importer does not rotate credentials or decide which account
should be used. Old Rust versions did not cooperate with the Python flock: a
final process census detects reopening, but is not an adversarial exclusion
mechanism against a manually reopened legacy application.

## Copied old Mac folders

The disclosure accepts the former absolute installation location. It maps POSIX
path components under that old root to the selected copied folder (not a string
prefix such as `Helene2`). For data/code formerly outside the installation,
transfer those directories and correct their configured paths in the private
copy before importing. Windows exports remain the separate `profile_paths.py`
offline path; no private mapping or configuration belongs in public source.
Absolute or escaping nested source links are refused with their path rather
than leaving the new memory writing through to the old installation. Safe
internal relative links are preserved. Optional old voice runtimes are not
copied across this migration; use the new platform's component installer.

## Failure and retry

Before the initial essential snapshot, the fresh setup template is atomically
retained as `.mac-migration-template.json` under the destination lease. If the
process/window exits before a journal exists, reopen the migration window and
prepare with the same paths; it reads that retained template without requiring
manual config restoration. This is not a claim that the donor was captured.
`python-migration.json` is written after the snapshot and before preserved data
copy bytes. An interrupted `preserving` operation can resume only the same
old/new/data/path-map choices;
replaced prior bytes/configs are retained in attempt/delta directories. A
prepared profile is reused rather than recopied when startup fails. Startup
exit and a 150-second absence of proof are explicitly reported; no unknown
process is killed automatically. Close a failed new window, inspect
`migration-start.log` / `startup-error.log`, then repeat opening. The separate
`mac-migration-status.json` records request/failure, never substitutes for the
controller's startup proof. Reopening the migration window shows historical
success as historical, not a current liveness guarantee. A plain Finder launch
of a prepared new Helene.app also confirms that pending migration after UI
readiness. Nothing retires the donor.

## Build and focused qualification

Full assembly copies `mac_migrate.py`, the shared migration modules and
`resources/mac-migration.html`; `macos_python_app.create()` compiles and ad-hoc
signs both native entries. Existing main delivery ZIPs must not be overwritten.
For a small overlay over the qualified final main ZIP:

```sh
# Extract the exact immutable base ZIP to a NEW disposable stage, preserving
# ZipInfo Unix mode bits (zipfile.extractall alone does not do that).
python desk/installer/overlay_mac_migration.py \
  --program /tmp/new-stage/Helene --archive /tmp/Helene-mac-migration-candidate.zip
# Driver Python must be outside /tmp/new-stage/Helene. Driver-only dependencies:
# psutil + playwright, with its Chromium browser installed.
python desk/tests/macos_migration_pilot.py \
  --program /tmp/new-stage/Helene --evidence /tmp/mac-migration-evidence
```

The overlay updates the program inventory, compiles/signs the small Cocoa
entries and writes a new archive with original executable modes and a SHA
sidecar. The native pilot uses synthetic legacy memory and dirty Git, launches
Migrate.app, drives its real served form, proves actual process/flock refusals,
forces a failed new startup, retries to rendered/controller proof and checks
source preservation. It captures Cocoa and served-UI PNGs for visual inspection.
It does not replay voice/large component tests or use live authentication/TCC.
A Windows source test is not that native proof. Local focused tests:
`python -m unittest discover -s desk/tests -p t_mac_migration_2410.py -v`.

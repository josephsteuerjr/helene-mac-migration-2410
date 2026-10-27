from pathlib import Path
import os,platform,subprocess,sys
assert platform.machine()=='arm64'
root=Path(os.environ['RUNNER_TEMP']);inputs=root/'inputs';base=inputs/'Helene-2.2.9-macos-arm64.zip';candidate=inputs/os.environ['CANDIDATE_NAME']
for mode in ('preserve','clean'):
 subprocess.run([sys.executable,'native_modes_driver.py','--base',str(base),'--base-sha','b42c6c964d83d6d87981dbe3ea6a20a09a2a5b5fee7b068fbdf3713eb350ddf2','--candidate',str(candidate),'--candidate-sha',os.environ['CANDIDATE_SHA'],'--work',str(root/'native210'/mode),'--evidence',str(root/'native210'/(mode+'-evidence')),'--mode',mode],check=True,timeout=1100)

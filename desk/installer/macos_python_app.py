"""Native Finder entry for the Python app; no Rust shell/service or second owner.

The tiny Mach-O stays inside Helene.app for Cocoa/TCC application identity while
loading the selected runtime's libpython. Python's executable/prefix still name
the bundled interpreter, so supervised children never recurse into the window.
Ad-hoc signing is launch integrity only, not Developer ID/notarization.
"""
from pathlib import Path
import plistlib
import subprocess

DESK=Path(__file__).resolve().parents[1]
LAUNCHER=r'''#include <mach-o/dyld.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv) {
    char exe[PATH_MAX], resolved[PATH_MAX], root[PATH_MAX], lib[PATH_MAX];
    char python[PATH_MAX], entry[PATH_MAX]; uint32_t size=sizeof(exe);
    if (_NSGetExecutablePath(exe,&size) || !realpath(exe,resolved)) return 70;
    char *slash=strrchr(resolved,'/'); if (!slash) return 70; *slash=0;
    if (snprintf(root,sizeof(root),"%s/../../..",resolved)>=(int)sizeof(root)) return 70;
    char canonical[PATH_MAX]; if (!realpath(root,canonical)) return 70;
    if (snprintf(lib,sizeof(lib),"%s/runtime/lib/libpython3.14.dylib",canonical)>=(int)sizeof(lib)) return 70;
    if (snprintf(python,sizeof(python),"%s/runtime/bin/python3",canonical)>=(int)sizeof(python)) return 70;
    if (snprintf(entry,sizeof(entry),"%s/app/python_app.py",canonical)>=(int)sizeof(entry)) return 70;
    if (snprintf(root,sizeof(root),"%s/runtime",canonical)>=(int)sizeof(root)) return 70;
    setenv("PYTHONHOME",root,1);
    unsetenv("PYTHONPATH");
    void *handle=dlopen(lib,RTLD_NOW|RTLD_GLOBAL);
    if (!handle) { fprintf(stderr,"Hélène: %s\n",dlerror()); return 70; }
    int (*run)(int,char **)=dlsym(handle,"Py_BytesMain");
    if (!run) { fprintf(stderr,"Hélène: libpython lacks Py_BytesMain\n"); return 70; }
    /* PYTHONHOME sizes this embedded interpreter, not separately selected children.
       Clear it after Python initialization and before any application import. */
    char *bootstrap="import os,runpy,sys;os.environ.pop('PYTHONHOME',None);entry=sys.argv.pop(1);sys.path.insert(0,os.path.dirname(entry));runpy.run_path(entry,run_name='__main__')";
    char **args=calloc((size_t)argc+9,sizeof(char*)); if (!args) return 71;
    args[0]=python; args[1]="-s"; args[2]="-c"; args[3]=bootstrap;
    args[4]=entry; args[5]="--root"; args[6]=canonical;
    for (int i=1;i<argc;i++) args[i+6]=argv[i];
    int status=run(argc+6,args); free(args); return status;
}
'''


def app_plist(version):
    return {'CFBundleName':'Hélène','CFBundleDisplayName':'Hélène',
        'CFBundleIdentifier':'app.helene.python','CFBundleExecutable':'Helene',
        'CFBundlePackageType':'APPL','CFBundleShortVersionString':version,
        'CFBundleVersion':version,'CFBundleIconFile':'icon','LSMinimumSystemVersion':'14.0',
        'NSHighResolutionCapable':True,'LSAppNapIsDisabled':True,
        'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True},
        'NSMicrophoneUsageDescription':'Record voice messages for your agent.'}


def create_entry(program, version, *, migration=False):
    program=Path(program)
    app=program/('Migrate Helene.app' if migration else 'Helene.app');contents=app/'Contents'
    (contents/'MacOS').mkdir(parents=True,exist_ok=True);(contents/'Resources').mkdir(exist_ok=True)
    value=app_plist(version)
    if migration:
        value.update(CFBundleName='Migrate Hélène',CFBundleDisplayName='Перенос Hélène',CFBundleIdentifier='app.helene.python.migrate')
    (contents/'Info.plist').write_bytes(plistlib.dumps(value))
    source=program.parent/('helene-migration-entry.c' if migration else 'helene-python-entry.c')
    source.write_text(LAUNCHER.replace('app/python_app.py','app/mac_migrate.py') if migration else LAUNCHER,encoding='utf-8')
    subprocess.run(['clang','-arch','arm64','-mmacosx-version-min=14.0','-O2',str(source),'-o',str(contents/'MacOS/Helene')],check=True)
    iconset=program.parent/'Helene.iconset';iconset.mkdir(exist_ok=True)
    for size in (16,32,128,256,512):
        for scale in (1,2):
            name=f'icon_{size}x{size}'+('@2x' if scale==2 else '')+'.png'
            subprocess.run(['sips','-z',str(size*scale),str(size*scale),str(DESK/'shell/icons/python-app.png'),'--out',str(iconset/name)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(contents/'Resources/icon.icns')],check=True)
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
    subprocess.run(['codesign','--verify','--strict',str(app)],check=True)
    return app


def create(program, version):
    program=Path(program)
    create_entry(program,version)
    create_entry(program,version,migration=True)
    (program/'MACOS-READ-ME.txt').write_text('Hélène private Apple Silicon build, macOS 14 or later.\nKeep both .app entries beside runtime/app/tree; move the complete Helene folder, not an app alone.\nFor an existing Mac Hélène: Quit the old app, disable its old login/service integration, then open Migrate Helene.app. Choose its folder and a separate data home. The old installation is never deleted. Open the new app from the migration window and wait for its startup confirmation.\nFor a fresh profile open Helene.app. This build is ad-hoc signed, not notarized. Gatekeeper approval is a deliberate user action.\nNo privileged broker or system service is installed. Native body TCC permissions require your consent.\nRoutine updates use the Python app updater; retain old releases used by optional component maps.\n',encoding='utf-8')
    return {'entry':'Helene.app','signing':'ad-hoc','notarized':False,'minimum_macos':'14.0'}

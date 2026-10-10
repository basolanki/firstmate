import os, pathlib, subprocess, time, json, shutil, shlex, tempfile, hashlib
ROOT=pathlib.Path('/Users/brkrbnkr/.no-mistakes/worktrees/3bb5d30aa0d7/01M4KT6VREVW4ZSDYE3RTXE6DX')
EVIDENCE=pathlib.Path('/Users/brkrbnkr/.no-mistakes/evidence/01M4KT6VREVW4ZSDYE3RTXE6DX')
WORLD=ROOT/'.inbox-live-validation'
WORLD.mkdir()
HOME= WORLD/'home'
USER= WORLD/'user'
USER.mkdir()
ENV=os.environ.copy()
for k in list(ENV):
    if k.startswith('FM_') or k.startswith('HERDR_') or k.startswith('GIT_') or k in ['TMUX','TMUX_PANE','NO_MISTAKES_GATE','TASKS_AXI_FILE','TASKS_AXI_BACKEND','CLAUDECODE','CURSOR_AGENT','CURSOR_INVOKED_AS','BASH_ENV','ENV']:
        ENV.pop(k,None)
ENV.update(HOME=str(USER), FM_HOME=str(HOME), FM_BACKEND='tmux', GROK_HOME=str(USER/'.grok'), CLAUDE_CONFIG_DIR=str(USER/'.claude'), CODEX_HOME=str(USER/'.codex'), XDG_CONFIG_HOME=str(USER/'config'), XDG_DATA_HOME=str(USER/'data'), XDG_STATE_HOME=str(USER/'state'), GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1', SHELL='/bin/bash', TREEHOUSE_ROOT=str(WORLD/'pool'), TREEHOUSE_WORKTREE_PATH='{pool}/{slot}/{repo}', FM_TASK_INBOX=str(WORLD/'wrong-inbox'))
LOG=open(EVIDENCE/'live-inbox.log','w')
results=[]; sock=None; secondary=[]; tasktmp=[]
def command(args,check=True,env=None,cwd=ROOT,timeout=90):
    LOG.write('$ '+shlex.join(map(str,args))+'\n'); LOG.flush()
    p=subprocess.run(list(map(str,args)),cwd=cwd,env=env or ENV,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    LOG.write('[baseline executable bytes retained only in disposable copy]\n' if args[:2]==['git','show'] else p.stdout); LOG.write('exit='+str(p.returncode)+'\n'); LOG.flush()
    if check and p.returncode: raise RuntimeError(p.stdout)
    return p

def tmux(*args,**kw): return command(['tmux','-L','fm-lab',*args],**kw)
def init_repo(path):
    path.mkdir(parents=True,exist_ok=True)
    command(['git','init','-q','-b','main',path])
    command(['git','-C',path,'config','user.name','Inbox lab'])
    command(['git','-C',path,'config','user.email','inbox-lab@example.invalid'])
    (path/'README.md').write_text('Disposable inbox validation project.\n')
    command(['git','-C',path,'add','README.md'])
    command(['git','-C',path,'commit','-qm','Disposable fixture'])

def scenario(harness,kind,blocked=False,baseline=False):
    tag=('baseline-' if baseline else 'blocked-' if blocked else '')+harness+'-'+kind
    id='inbox-lab-'+tag+'-'+str(os.getpid())
    tasktmp.append(pathlib.Path('/tmp')/('fm-'+id))
    tasktmp.append(pathlib.Path('/tmp')/('fm-'+id+'+'+hashlib.sha256(str(HOME).encode()).hexdigest()))
    brief=HOME/'data'/id/'brief.md'; brief.parent.mkdir(parents=True)
    brief.write_text("# Task\n## Captain's intent\nVerify that a newly launched worker can list its steering inbox before any message is sent.\n\n## Firstmate spec\nPerform a local filesystem check only.\n")
    target=WORLD/'projects'/tag
    if kind=='secondmate':
        # The trusted runbook explicitly permits disposable fm-lab homes.
        target=pathlib.Path(tempfile.mkdtemp(prefix='fm-lab.'))
        secondary.append(target)
        command(['bin/fm-lab-home.sh','create',target])
        (target/'bin').mkdir()
        shutil.copyfile(ROOT/'AGENTS.md',target/'AGENTS.md')
        (target/'.fm-secondmate-home').write_text(id+'\n')
        (target/'data'/'charter.md').write_text('Disposable filesystem validation; remain idle.\n')
        (target/'.gitignore').write_text('state/\ndata/\nconfig/\nprojects/\n')
    init_repo(target)
    expected=HOME/'state'/(id+'.inbox')
    if blocked: expected.write_text('occupied by a regular file\n')
    else: assert not expected.exists()
    receipt=WORLD/(tag+'.json')
    checker=WORLD/'check-inbox.py'
    raw=f'{harness} '+ ('__CLAUDEADDDIRS__ ' if harness=='claude' else '')+f'--version && python3 {shlex.quote(str(checker))} {shlex.quote(str(expected))} {shlex.quote(str(receipt))}'
    entry=ROOT/'bin'/('.inbox-baseline-spawn.sh' if baseline else 'fm-spawn.sh')
    args=[entry,id,target,raw]
    if kind=='ship': args+=['--mode','local-only','--yolo','off']
    elif kind=='scout': args+=['--scout']
    else: args+=['--secondmate']
    start=time.monotonic()
    p=command(args,check=False,timeout=95)
    at_launch=brief.parent/'at-launch.json'
    if blocked:
        assert not at_launch.exists()
        observed=tmux('capture-pane','-p','-t','primary:fm-'+id,'-S','-180',check=False).stdout
        assert p.returncode!=0 and 'could not create the steering inbox' in p.stdout
        assert not receipt.exists() and '--version' not in observed
        item=dict(name=tag,result='pass',live=True,detail='An occupied inbox pathname stops spawn before CLI launch; no worker receipt was created.')
    elif baseline:
        for _ in range(100):
            if receipt.exists(): break
            time.sleep(.1)
        assert p.returncode==0 and receipt.exists()
        data=json.loads(receipt.read_text())
        before=json.loads(at_launch.read_text())
        assert before==dict(inbox_is_dir=False,handled_is_dir=False)
        assert not data['inbox_is_dir'] and not data['handled_is_dir'] and data['listing_error']=='FileNotFoundError'
        item=dict(name=tag,result='pass',live=True,detail='Original spawn reproduced the missing-inbox failure in a real tmux worker.',worker=data)
    else:
        if p.returncode: raise RuntimeError('spawn failed '+tag+'\n'+p.stdout)
        for _ in range(100):
            if receipt.exists(): break
            time.sleep(.1)
        assert receipt.exists(), 'worker did not produce receipt '+tag
        data=json.loads(receipt.read_text())
        before=json.loads(at_launch.read_text())
        assert before==dict(inbox_is_dir=True,handled_is_dir=True)
        data['ready_before_launch_delivery']=True
        assert data['export_matches_expected'] and data['inbox_is_dir'] and data['handled_is_dir'] and data['entries']==['handled'] and data['listing_error'] is None, data
        item=dict(name=tag,result='pass',live=True,detail='Installed CLI version command ran; its launch then listed the correct empty inbox and handled directory before any fm-send.',worker=data)
    if not blocked: item['before_delivery']=before
    pane=tmux('capture-pane','-p','-t','primary:fm-'+id,'-S','-180',check=False)
    (EVIDENCE/(tag+'.txt')).write_text(p.stdout+'\nWORKER RECEIPT\n'+(receipt.read_text() if receipt.exists() else 'none\n')+'\nREAL PANE\n'+pane.stdout)
    item['seconds']=round(time.monotonic()-start,2)
    results.append(item)
    print(tag+': '+item['result'],flush=True)
    (EVIDENCE/'live-results.json').write_text(json.dumps(results,indent=2)+'\n')

try:
    command(['bin/fm-lab-home.sh','create',HOME])
    (HOME/'config'/'launch-env-allowlist').touch()
    (HOME/'state'/'.last-watcher-beat').touch()
    # Supported helper owns the short ephemeral socket directory.
    sock=command(['bin/fm-lab-home.sh','tmux-dir',HOME]).stdout.strip()
    ENV['TMUX_TMPDIR']=sock
    actual_tmux=shutil.which('tmux',path=ENV['PATH'])
    shim=WORLD/'observer'; shim.mkdir()
    observer=shim/'tmux'
    observer.write_text('#!'+shutil.which('python3')+'\n'+'''import os,sys,shlex,pathlib,json
args=sys.argv[1:]
if args and args[0]=='send-keys' and '-l' in args:
    for arg in args:
        if arg.startswith('. '):
            words=shlex.split(arg)
            if len(words)==2 and pathlib.Path(words[1]).name.startswith('launch.'):
                task=pathlib.Path(words[1]).parent.name.removeprefix('fm-').split('+')[0]
                inbox=pathlib.Path(os.environ['FM_HOME'])/'state'/(task+'.inbox')
                receipt=pathlib.Path(os.environ['FM_HOME'])/'data'/task/'at-launch.json'
                receipt.write_text(json.dumps(dict(inbox_is_dir=inbox.is_dir(),handled_is_dir=(inbox/'handled').is_dir())))
os.execv('''+repr(actual_tmux)+''',["tmux",*args])
''')
    observer.chmod(0o755)
    ENV['PATH']=str(shim)+os.pathsep+ENV['PATH']
    tmux('-f','/dev/null','new-session','-d','-s','primary','-x','160','-y','45','-c',ROOT,'/bin/bash --noprofile --norc')
    tmux('set-option','-g','default-shell','/bin/bash')
    tmux('set-option','-g','default-command','/bin/bash --noprofile --norc')
    ENV['TMUX']=tmux('display-message','-p','-t','primary','#{socket_path},#{pid},0').stdout.strip()
    (WORLD/'check-inbox.py').write_text('''import os, sys, pathlib, json
want=pathlib.Path(sys.argv[1]); seen=os.environ.get("FM_TASK_INBOX")
p=pathlib.Path(seen) if seen else pathlib.Path("/definitely-absent-inbox")
try: entries=sorted(x.name for x in p.iterdir()); error=None
except Exception as e: entries=[]; error=type(e).__name__
result=dict(export_matches_expected=seen==str(want),inbox_is_dir=p.is_dir(),handled_is_dir=(p/"handled").is_dir(),entries=entries,listing_error=error)
pathlib.Path(sys.argv[2]).write_text(json.dumps(result)+"\\n")
print("INBOX_LAUNCH_RECEIPT "+json.dumps(result),flush=True)
''')
    baseline=command(['git','show','fb75c1f94170df7e0751147ea61afabcf5d4e104:bin/fm-spawn.sh']).stdout
    basepath=ROOT/'bin'/'.inbox-baseline-spawn.sh'
    basepath.write_text(baseline); basepath.chmod(0o755)
    scenario('codex','scout',baseline=True)
    for harness in ['grok','codex','claude']:
        for kind in ['ship','scout','secondmate']:
            scenario(harness,kind)
    scenario('codex','scout',blocked=True)
finally:
    if sock:
        tmux('kill-server',check=False)
        probe=tmux('list-sessions',check=False)
        LOG.write('CLEANUP private tmux server stopped='+str(probe.returncode!=0)+'\n')
        command(['bin/fm-lab-home.sh','teardown',HOME],check=False)
    for p in secondary: shutil.rmtree(p)
    for p in tasktmp:
        if p.exists(): shutil.rmtree(p)
    (ROOT/'bin'/'.inbox-baseline-spawn.sh').unlink(missing_ok=True)
    
    for directory, dirs, files in os.walk(WORLD): os.chmod(directory,0o700)
    shutil.rmtree(WORLD)
    LOG.write('CLEANUP disposable homes, projects, pool, baseline copy, and owned task temp roots removed\n'); LOG.close()

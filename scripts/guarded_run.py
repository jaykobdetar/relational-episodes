"""One-core subprocess supervisor; watches own child and never other processes."""
import argparse
from pathlib import Path
import json
import os
import resource
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from relational_episodes.resources import check_headroom, host_sample

parser=argparse.ArgumentParser()
parser.add_argument('--prefix',required=True)
parser.add_argument('command',nargs=argparse.REMAINDER)
a=parser.parse_args()
if a.command and a.command[0]=='--':a.command=a.command[1:]
if not a.command:parser.error('command required')
prefix=Path(a.prefix)
paths={kind:Path(str(prefix)+'.'+kind) for kind in ('json','stdout.log','stderr.log')}
if any(p.exists() for p in paths.values()):raise SystemExit('refuse overwrite of prior run evidence')
prefix.parent.mkdir(parents=True,exist_ok=True)
started=time.monotonic()
report={'command':a.command,'status':'preflight','single_cpu_core':None}
try:
    gate=check_headroom(); report['preflight']=gate
except Exception as exc:
    report.update(status='resource_paused',reason=str(exc),seconds=time.monotonic()-started)
    paths['json'].write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));raise SystemExit(2)
# Affinity is local to this supervisor and its own child; no system-wide setting.
core=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{core});report['single_cpu_core']=core
last=gate['second'];samples=[];peak=0;reason=None
with paths['stdout.log'].open('x') as stdout,paths['stderr.log'].open('x') as stderr:
    proc=subprocess.Popen(a.command,stdout=stdout,stderr=stderr)
    # Child initializes its own 256 MiB address-space limit. The supervisor
    # additionally monitors combined RSS and terminates its child above 256 MiB.
    resource.setrlimit(resource.RLIMIT_AS,(64*1024*1024,64*1024*1024))
    while True:
        state=host_sample()
        def rss(pid):
            try:
                for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                    if line.startswith('VmRSS:'):return int(line.split()[1])
            except FileNotFoundError:pass
            return 0
        combined=rss(os.getpid())+rss(proc.pid);peak=max(peak,combined)
        if len(samples)<1000:samples.append(dict(state,combined_rss_kib=combined,elapsed_seconds=round(time.monotonic()-started,3)))
        if state['mem_available_kib']<2*1024*1024:reason='host MemAvailable fell below 2 GiB'
        elif state['pswpout']>last['pswpout'] or state['swap_free_kib']<last['swap_free_kib']:reason='swap-out/used-swap pressure increased'
        elif combined>256*1024:reason='combined supervisor+child RSS exceeded 256 MiB'
        if reason:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=1)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            break
        last=state
        if proc.poll() is not None:break
        time.sleep(0.2)
report.update(status='resource_stopped' if reason else ('passed' if proc.returncode==0 else 'failed'),reason=reason,returncode=proc.returncode,seconds=time.monotonic()-started,peak_combined_rss_kib=peak,samples=samples)
paths['json'].write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','reason','returncode','seconds','peak_combined_rss_kib')}))
raise SystemExit(2 if reason else proc.returncode)

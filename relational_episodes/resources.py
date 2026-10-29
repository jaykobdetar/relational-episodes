"""Local-process bounds and a read-only host-capacity gate."""
import resource
import time
from .core import ContractError


def limits():
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    # All work is one standard-library process, without workers or numerical BLAS.


def host_sample():
    with open('/proc/meminfo') as f:
        info = {line.split(':')[0]:int(line.split()[1]) for line in f}
    with open('/proc/vmstat') as f:
        vm = dict(line.split() for line in f)
    return {"mem_available_kib":info["MemAvailable"],"swap_free_kib":info["SwapFree"],"swap_total_kib":info["SwapTotal"],"pswpin":int(vm["pswpin"]),"pswpout":int(vm["pswpout"])}


def check_headroom():
    first = host_sample(); time.sleep(0.25); second = host_sample()
    if min(first["mem_available_kib"],second["mem_available_kib"]) < 3*1024*1024:
        raise ContractError(f"resource gate: MemAvailable {second['mem_available_kib']} KiB below 3 GiB; defer heavy work")
    if second["pswpout"] > first["pswpout"] or second["swap_free_kib"] < first["swap_free_kib"]:
        raise ContractError("resource gate: increasing swap-out/used-swap pressure; defer heavy work")
    return {"first":first,"second":second,"policy":"one CPU process; 256 MiB RLIMIT_AS; >=3 GiB available; no observed swap-out or used-swap growth"}

import asyncio
import aiohttp
import json
from typing import List
from ipaddress import IPv4Network


def _explode_cidrs(cidr: str):
    try:
        return [str(ip).split('/', 1)[0] for ip in IPv4Network(cidr)]
    except:
        return cidr


async def get_header(host: str, port: int, timeout: int, session):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"}
    results = {"host": host, "port": port}
    try:
        async with session.head(f"https://{host}:{port}", verify_ssl=False, timeout=timeout, headers=headers) as response:
            results["headers"] = dict(**response.headers)
    except:
        try:
            async with session.head(f"http://{host}:{port}", timeout=timeout, headers=headers) as response:
                results["headers"] = dict(**response.headers)
        except:
            results["headers"] = None
    return results


async def run(targets: List[str], ports: List[int], outfile: str, timeout: int = 5):
    # Build a list of (target, port) 2-tuples
    host_port_combos = [(_ip, port) for cidr in targets for _ip in _explode_cidrs(cidr) for port in ports]
    loop = asyncio.get_event_loop()
    session = aiohttp.ClientSession()
    tasks = [loop.create_task(get_header(*hpc, timeout=timeout, session=session)) for hpc in host_port_combos]
    tasks_separated = [tasks[i:i + 10] for i in range(0, len(tasks), 10)]
    results = []
    for task_set in tasks_separated:
        task_set_results = await asyncio.gather(*task_set)
        results.extend(task_set_results)
    with open(outfile, "w") as o_file:
        json.dump(results, o_file, indent=2)

if __name__ == '__main__':

    import time
    import argparse

    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()

    group.add_argument("--host", help="A single host to query")
    group.add_argument("--infile",
                       help="A file containing a newline-separated list of hosts",
                       default="/tmp/scan_targets.txt")
    parser.add_argument("--ports", help="The port(s) to which we want to connect")
    parser.add_argument("--outfile",
                        help="The file to which we want to dump our results",
                        default="/tmp/scan_results.json")
    parser.add_argument("--timeout", help="Timeout for the HTTP connection", default=3, type=int)

    args = parser.parse_args()

    if args.host:
        _targets = [args.host]
    else:
        with open(args.infile, "r") as f:
            _targets = [x.strip() for x in f.read().split('\n')]

    _ports = [int(x.strip()) for x in args.ports.split(',')]

    start_time = time.time()
    asyncio.run(run(_targets, _ports, args.outfile, args.timeout))
    end_time = time.time()
    print(f"Processed {len(_targets)} in {round(end_time - start_time, 2)} seconds")




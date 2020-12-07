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
    results = {"host": host, "port": port}
    try:
        async with session.head(f"https://{host}:{port}", verify_ssl=False, timeout=timeout) as response:
            results["headers"] = dict(**response.headers)
    except:
        try:
            async with session.head(f"http://{host}:{port}", timeout=1) as response:
                results["headers"] = dict(**response.headers)
        except:
            results["headers"] = None
    return results


async def run(targets: List[str], ports: List[int], outfile: str, timeout: int = 3):
    # Build a list of (target, port) 2-tuples
    host_port_combos = [(_ip, port) for cidr in targets for _ip in _explode_cidrs(cidr) for port in ports]
    print(f"Got {len(host_port_combos)} host:port combinations")
    loop = asyncio.get_event_loop()
    session = aiohttp.ClientSession()
    tasks = [loop.create_task(get_header(*hpc, timeout=timeout, session=session)) for hpc in host_port_combos]
    results = await asyncio.gather(*tasks)
    with open(outfile, "w") as o_file:
        json.dump(results, o_file, indent=2)
    await session.close()

if __name__ == '__main__':

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
    asyncio.run(run(_targets, _ports, args.outfile, args.timeout))




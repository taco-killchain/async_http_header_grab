import asyncio
import aiohttp
import json
from typing import List


async def get_header(host: str, port: int, timeout: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(f"https://{host}:{port}", verify_ssl=False, timeout=timeout) as response:
                return dict(**response.headers)
        except:
            try:
                async with session.head(f"http://{host}:{port}", timeout=1) as response:
                    return dict(**response.headers)
            except:
                return None


async def run(targets: List[str], ports: List[int], outfile: str, timeout: int = 3):
    # Build a list of (target, port) 2-tuples
    host_port_combos = [(target, port) for target in targets for port in ports]
    results = [{"host": hpc[0], "port": hpc[1], "headers": await get_header(*hpc, timeout=timeout)} for hpc in host_port_combos]
    with open(outfile, "w") as o_file:
        json.dump(results, o_file, indent=2)


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
    el = asyncio.get_event_loop()
    el.run_until_complete(run(_targets, _ports, args.outfile, args.timeout))




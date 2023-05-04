import asyncio
import aiohttp
import json
from typing import List
from ipaddress import IPv4Network
import threading

lock = threading.Lock()


def _explode_cidrs(cidr: str):
    try:
        return [str(ip).split('/', 1)[0] for ip in IPv4Network(cidr)]
    except:
        return cidr


async def get_header(host: str, port: int, timeout: int, session):
    results = {"host": host, "port": port}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"}
    try:
        async with session.head(f"https://{host}:{port}", verify_ssl=False, timeout=timeout, headers=headers) as response:
            results["headers"] = dict(**response.headers)
    except Exception as e:
        try:
            async with session.head(f"http://{host}:{port}", timeout=timeout, headers=headers) as response:
                results["headers"] = dict(**response.headers)
        except Exception as e:
            results["headers"] = None
    return results


async def worker(queue, session, timeout):
    results = []
    while True:
        hpc = await queue.get()
        if hpc is None:
            break
        result = await get_header(*hpc, timeout=timeout, session=session)
        results.append(result)
        queue.task_done()
    return results


async def run(targets: List[str], ports: List[int], outfile: str, timeout: int = 5):
    # Build a list of (target, port) 2-tuples
    host_port_combos = [(_ip, port) for cidr in targets for _ip in _explode_cidrs(cidr) for port in ports]

    async with aiohttp.ClientSession() as session:
        queue = asyncio.Queue()
        for hpc in host_port_combos:
            await queue.put(hpc)

        workers = [asyncio.create_task(worker(queue, session, timeout)) for _ in range(10)]

        await queue.join()

        for _ in workers:
            await queue.put(None)

        all_results = await asyncio.gather(*workers)

    # Flatten the list of lists of results and write them to the output file
    with open(outfile, "w") as o_file:
        flat_results = [item for sublist in all_results for item in sublist]
        json.dump(flat_results, o_file, indent=2)


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
    parser.add_argument("--timeout", help="Timeout for the HTTP connection", default=1, type=int)

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

    print(f"Total time taken: {end_time - start_time} seconds")

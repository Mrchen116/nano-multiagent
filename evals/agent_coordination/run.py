"""Run any registered coordination DAG in an isolated Global Agent IM."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from case import load_case
from engine import Engine
from runtime import Runtime


def run_arm(case, run, arm, images, resume=False):
    output = run / f"{case['id']}-{arm}.json"
    checkpoint = json.loads(output.read_text()) if resume and output.exists() else None
    if output.exists() and not resume:
        raise ValueError("Use a fresh run or --resume")
    env = dict(
        line.removeprefix("export ").split("=", 1)
        for line in (run / ".e2e-ports.env").read_text().splitlines()
        if "=" in line
    )
    url = env.get("IM_URL", "http://127.0.0.1:" + env["IM_PORT"]).strip("'\"")
    control = json.loads((run / "provider.json").read_text())["url"]
    runtime = Runtime(run, case, arm, url, control, images, checkpoint)

    def save(state):
        state.update(
            chat=runtime.chat,
            root=runtime.root,
            url=f"{url}/chat/{runtime.chat}",
            timeline=runtime.messages,
        )
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        temporary.replace(output)

    runtime.save = save
    engine = Engine(case, runtime, checkpoint, save)
    print(arm, f"{url}/chat/{runtime.chat}", flush=True)
    try:
        while not engine.tick():
            runtime.probe_images(engine.state)
            save(engine.state)
            time.sleep(1)
        runtime.refresh()
        save(engine.state)
    finally:
        runtime.close()
    return engine.state


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("run", type=Path, nargs="?")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--arms", default="AB")
    parser.add_argument(
        "--images",
        type=Path,
        help="Private JSON mapping attachment keys to original paths",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    case = load_case(args.case)
    if args.validate:
        print(case["id"], len(case["nodes"]), "nodes", case["sha256"])
        return
    if not args.run or not (args.run / "defaults.json").exists():
        parser.error("Start the isolated default Global stack before replay")
    run = args.run.resolve()
    images = json.loads(args.images.read_text()) if args.images else {}
    for key in case.get("attachments", {}):
        if key not in images or not Path(images[key]).is_file():
            parser.error(f"Missing original attachment: {key}")
    (run / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2))
    with ThreadPoolExecutor(max_workers=len(args.arms)) as pool:
        futures = [
            pool.submit(run_arm, case, run, arm, images, args.resume)
            for arm in args.arms
        ]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()

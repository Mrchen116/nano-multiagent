"""Load the single coordination case definition used by replay and the viewer."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).parent
PRIMITIVES = json.loads((ROOT / "primitives.json").read_text())


def material(case_dir, content):
    if "text" in content:
        return content["text"]
    path = (case_dir / content["file"]).resolve()
    if ROOT.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"Unknown case material: {content}")
    return path.read_text().strip()


def validate_matcher(matcher, ids):
    for key in matcher:
        if key not in {"all", "any", "not", "source_node"}:
            raise ValueError(f"Unknown matcher operator: {key}")
    for key in ("all", "any", "not"):
        for pattern in matcher.get(key, []):
            re.compile(pattern, re.I | re.S)
    if matcher.get("source_node") and matcher["source_node"] not in ids:
        raise ValueError("Unknown source_node")


def load_case(path):
    path = Path(path).resolve()
    case = json.loads(path.read_text())
    case.pop("sha256", None)
    if case.get("version") != 1 or not case.get("nodes") or not case.get("id"):
        raise ValueError("Expected a version 1 coordination DAG")
    nodes = case["nodes"]
    ids = {n["id"] for n in nodes}
    if len(ids) != len(nodes):
        raise ValueError("Duplicate node id")
    workers = {n["worker"] for n in nodes if n["type"] == "delegate"}
    for n in nodes:
        if n["type"] not in PRIMITIVES or n["task"] not in case["tasks"]:
            raise ValueError(f"Unknown primitive or task: {n['id']}")
        if (
            n["type"] in {"delegate", "child_message", "worker_message"}
            and n.get("worker") not in workers
        ):
            raise ValueError(f"Unknown worker: {n['id']}")
        refs = [*n.get("after", []), *n.get("order_after", [])]
        for ref in refs:
            if ref not in ids:
                raise ValueError(f"Unknown dependency {ref} in {n['id']}")
        for key in ("content", "fallback"):
            if key in n:
                n[key]["text"] = material(path.parent, n[key])
        if n["type"] in {"user_message", "worker_message"} and "content" not in n:
            raise ValueError(f"Missing content: {n['id']}")
        validate_matcher(n.get("matcher", {}), ids)
        when = n.get("when")
        if when:
            if when.get("evidence_node") and when["evidence_node"] not in refs:
                raise ValueError(f"Condition must reference a predecessor: {n['id']}")
            if not when.get("evidence_node") and when.get("source") != "public":
                raise ValueError("Condition needs public source or evidence_node")
            validate_matcher(when.get("matcher", {}), ids)
        report = n.get("after_report", [])
        reports = [report] if isinstance(report, str) else report
        if any(ref not in n.get("after", []) for ref in reports):
            raise ValueError(f"after_report must be a hard predecessor: {n['id']}")
        for attachment in n.get("attachments", []):
            if attachment not in case.get("attachments", {}):
                raise ValueError(f"Unknown attachment: {attachment}")
    done = set()
    while len(done) < len(nodes):
        ready = [
            n["id"]
            for n in nodes
            if n["id"] not in done
            and set(n.get("after", []) + n.get("order_after", [])) <= done
        ]
        if not ready:
            raise ValueError("Case contains a dependency cycle")
        done.update(ready)
    case["sha256"] = hashlib.sha256(
        json.dumps(
            case, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return case


def matches(text, matcher, states):
    source = matcher.get("source_node")
    if source:
        expected = states.get(source, {}).get("text")
        if expected == "B":
            if not re.search(r"(?<![A-Za-z0-9])B(?![A-Za-z0-9])", text):
                return False
        if not expected or re.sub(r"\s+", "", expected) not in re.sub(r"\s+", "", text):
            return False
    hit = lambda pattern: bool(re.search(pattern, text, re.I | re.S))
    return (
        all(hit(p) for p in matcher.get("all", []))
        and (not matcher.get("any") or any(hit(p) for p in matcher["any"]))
        and not any(hit(p) for p in matcher.get("not", []))
    )

#!/usr/bin/env python3
"""Verify the public Genesis 251 Founding Four RAPP Vision replay."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DRAFT = ROOT / "draft"
STREAM = (
    "rappid:@rapterbox/twin:"
    "74d64548d291f8b13b57eacd69b41600ccc9195d474eb59eff850a0ff5cd6e18"
    ":genesis-251-draft"
)
VIDEO_ID = "genesis-251-founding-four-draft"


def canonical(value):
    if value is None or isinstance(value, (bool, int)):
        return json.dumps(value)
    if isinstance(value, float):
        raise ValueError("floats are not allowed")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=False)
                + ":"
                + canonical(value[key])
                for key in sorted(value)
            )
            + "}"
        )
    raise ValueError("non-I-JSON value")


def H(space, value):
    return hashlib.sha256(
        space.encode("utf-8")
        + b"\n"
        + canonical(value).encode("utf-8")
    ).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    frames = [
        json.loads(line)
        for line in (DRAFT / "draft.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert len(frames) == 254
    assert [frame["seq"] for frame in frames] == list(range(254))
    assert re.fullmatch(
        r"rappid:@[a-z0-9]+(?:-[a-z0-9]+)*/"
        r"[a-z0-9]+(?:-[a-z0-9]+)*:[a-f0-9]{64}:"
        r"[a-z0-9]+(?:-[a-z0-9]+)*",
        STREAM,
    )
    assert [frame["kind"] for frame in frames] == ["memory.save"] * 254
    assert frames[0]["payload"]["event"] == "draft.opened"
    assert frames[1]["payload"]["event"] == "starter.declared"
    assert frames[-1]["payload"]["event"] == "draft.closed"

    previous = None
    for frame in frames:
        assert frame["spec"] == "rapp/1"
        assert re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*\."
            r"[a-z0-9]+(?:-[a-z0-9]+)*",
            frame["kind"],
        )
        assert frame["stream_id"] == STREAM
        assert frame["prev_wave"] is None
        assert frame["sig"] is None
        assert frame["prev"] == (
            previous["payload_hash"] if previous else None
        )
        assert frame["payload_hash"] == H(
            "rapp/1:particle",
            frame["payload"],
        )
        preimage = {
            key: frame[key]
            for key in frame
            if key not in {"frame_hash", "sig"}
        }
        assert frame["frame_hash"] == H("rapp/1:wave", preimage)
        previous = frame

    picks = [
        frame
        for frame in frames
        if frame["payload"]["event"] == "draft.pick"
    ]
    assert len(picks) == 251
    assert len({frame["payload"]["rapter_id"] for frame in picks}) == 251
    assert {
        frame["payload"]["rapter_id"] for frame in picks
    } == {f"G{number:03d}" for number in range(1, 252)}
    assert len({frame["payload"]["name"] for frame in picks}) == 251
    assert [frame["payload"]["overall_pick"] for frame in picks] == list(
        range(1, 252)
    )
    order = ["Molly", "Sawyer", "Evelyn", "Kody"]
    assert [
        frame["payload"]["assignee"] for frame in picks
    ] == [order[index % 4] for index in range(251)]
    assert Counter(
        frame["payload"]["assignee"] for frame in picks
    ) == Counter({"Molly": 63, "Sawyer": 63, "Evelyn": 63, "Kody": 62})

    first = [
        (
            frame["payload"]["assignee"],
            frame["payload"]["starter_role"],
            frame["payload"]["rapter_id"],
            frame["payload"]["name"],
        )
        for frame in picks[:4]
    ]
    assert first == [
        ("Molly", "Overwatch", "G151", "Worldseed"),
        ("Sawyer", "Scout", "G251", "Everframe"),
        ("Evelyn", "Forge", "G005", "Duneledger"),
        ("Kody", "Sentinel", "G008", "Mudcrackoracle"),
    ]

    starters = frames[1]["payload"]["founding_four"]
    assert [item["card_id"] for item in starters] == [
        "001",
        "002",
        "003",
        "004",
    ]
    assert [item["founder_instance_label"] for item in starters] == [
        "Worldseed-001",
        "Everframe-001",
        "Duneledger-001",
        "Mudcrackoracle-001",
    ]
    assert frames[1]["payload"]["current_boundary"] == {
        "paper_test_only": True,
        "founder_001_duplicated": False,
        "title_or_offspring_rights_granted": False,
    }
    assert frames[-1]["payload"]["boundary"] == {
        "watch_only": True,
        "title_transfer": False,
        "metal_cards_issued": False,
        "offspring_issuance_open": False,
    }

    manifest = load_json(DRAFT / "manifest.json")
    assert manifest["frame_count"] == 254
    assert manifest["pick_frame_count"] == 251
    assert manifest["head_frame_hash"] == frames[-1]["frame_hash"]

    channel = load_json(ROOT / "channel.json")
    videos = [video for video in channel["videos"] if video["id"] == VIDEO_ID]
    assert len(videos) == 1
    video = videos[0]
    assert video["sources"] == []
    scenes = video["live"]["scenes"]
    assert len(scenes) == 254
    assert "card" in scenes[0]
    assert "card" in scenes[1]
    pick_scenes = scenes[2:-1]
    assert len(pick_scenes) == 251
    for index, (scene, frame) in enumerate(zip(pick_scenes, picks)):
        payload = frame["payload"]
        assert scene["card"]["title"] == (
            f"#{payload['overall_pick']:03d} {payload['name']}"
        )
        assert payload["assignee"] in scene["card"]["sub"]
        assert payload["rapter_id"] in scene["card"]["sub"]
        assert frame["frame_hash"][:16] in scene["card"]["note"]
        if index:
            assert scene["t"] > pick_scenes[index - 1]["t"]
    app_scene = scenes[-1]
    assert app_scene["app"] == "draft/index.html?pick=251"
    assert app_scene["ready"] == {
        "selector": '#verification[data-ok="true"]'
    }
    assert "actions" not in app_scene
    assert app_scene["dur"] == 20
    assert (ROOT / video["thumb"]).is_file()

    html = (DRAFT / "index.html").read_text(encoding="utf-8")
    assert "scoutTheme" in html
    assert "--cp-accent: #b11f4b;" in html
    assert 'id="next-pick"' in html
    assert 'get("pick")' in html
    assert 'fetch("./draft.jsonl"' in html
    assert "method: \"POST\"" not in html

    public_text = (
        (DRAFT / "draft.jsonl").read_text(encoding="utf-8")
        + html
        + json.dumps(video)
    ).casefold()
    for forbidden in (
        "pokemon",
        "charmander",
        "squirtle",
        "bulbasaur",
        "pikachu",
    ):
        assert forbidden not in public_text

    print(
        "Genesis 251 RAPP Vision replay: "
        "254 verified frames, 251 unique picks, Founding Four only"
    )


if __name__ == "__main__":
    main()

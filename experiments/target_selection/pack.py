#!/usr/bin/env python3
"""Pack exact raw bytes with deterministic archive metadata; retain originals."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    p=argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    args=p.parse_args()
    root=args.directory.resolve()
    target=root/"raw_data.tar.gz"
    if target.exists():
        p.error("archive already exists; refuse to replace evidence")
    files=sorted(f for sub in ("raw", "traces", "logs") for f in (root/sub).rglob("*") if f.is_file())
    members=[]
    with target.open("wb") as stream, gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as gz, tarfile.open(fileobj=gz,mode="w|") as tar:
        for path in files:
            info=tar.gettarinfo(str(path),arcname=str(path.relative_to(root)))
            info.uid=info.gid=info.mtime=0
            info.uname=info.gname=""
            with path.open("rb") as data:
                tar.addfile(info,data)
            members.append(dict(path=info.name,bytes=info.size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    record=dict(archive=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),members=members)
    (root/"archive_manifest.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    print(json.dumps(dict(files=len(files),bytes=target.stat().st_size,sha256=record["sha256"])))


if __name__ == "__main__":
    main()

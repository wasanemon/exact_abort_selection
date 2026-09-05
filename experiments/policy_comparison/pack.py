#!/usr/bin/env python3
"""Archive exact raw bytes, retain originals, and verify every archived member by SHA256."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import run

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--quality',action='store_true');args=p.parse_args()
root=args.directory.resolve()
files=sorted(root.glob('*.jsonl')) if args.quality else sorted(f for d in ('raw','records','traces','logs') for f in (root/d).rglob('*') if f.is_file())
if not files:raise ValueError('no raw files; extract existing archive before repacking')
manifest={str(f.relative_to(root)):run.sha256(f) for f in files}
archive=root/'raw_data.tar.gz';temp=root/'raw_data.tar.gz.tmp'
with temp.open('wb') as raw:
    with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w|') as tar:
            for file in files:
                data=file.read_bytes();info=tarfile.TarInfo(str(file.relative_to(root)))
                info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
with tarfile.open(temp,'r:gz') as tar:
    actual={m.name:hashlib.sha256(tar.extractfile(m).read()).hexdigest() for m in tar if m.isfile()}
if actual!=manifest:raise ValueError('archive bytes differ from originals')
temp.replace(archive)
run.save_json(root/'archive_manifest.json',dict(status='passed',archive_sha256=run.sha256(archive),files=manifest))
print(f'{root}: {len(files)} exact files, {archive.stat().st_size} compressed bytes, verified')

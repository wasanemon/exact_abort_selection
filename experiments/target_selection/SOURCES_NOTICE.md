# External source material and provenance

Files under `sources/` are research evidence, including third-party papers,
repository source snapshots, retrieved web pages, extracted text, and our audit
logs. Their presence does not put external material under this repository's
license. Original copyright, attribution, and license terms remain applicable.

- `fabricpp_code/` and `fabricsharp_sigmod20/` retain each repository's `LICENSE`
  (Apache License 2.0), file headers, and README attribution. Other Fabric/Fabric-X
  extracts retain their original contents and commit-pinned URLs in
  `fabric_sources_manifest.json`.
- Papers and extracts remain attributable to their named authors and publishers.
  Consult each original PDF/web page for the applicable terms. In particular,
  public download access is not a claim that every paper has a permissive software
  license. Extracted `.txt` files are aids to inspection; the source PDF controls
  where PDF text extraction loses mathematical symbols.
- Other downloaded code and artifacts are identified by original repository URLs,
  commits, and hashes in `representation_download_manifest.json` and the relevant
  audit documents. No broader redistribution license is inferred from public
  repository visibility or a missing license file.
- Retrieval failures are retained in the manifests. A failed download record is
  not evidence of the file's contents or proof that an artifact does not exist.

Run `python3 experiments/target_selection/verify_sources.py` for an offline
integrity check. It verifies original retrieval hashes and the frozen inventory
in `sources/checksums.json`, rejects unlisted source files, and checks the two
required Issue #3 documents against their recorded hashes. If the base Git object
is available, their bytes are independently checked against commit
`d150211968ef6d61efda82f9f44f63e3bac28b44`. In a source export without that object,
the Git cross-check is explicitly reported unavailable; the frozen content hashes
are still required.

`--write-manifest` explicitly bootstraps or refreshes the inventory after checking
the original download hashes and both Issue #3 documents against Git. Use it only
when intentionally adding/reviewing evidence. Normal reproduction must use the
default check and must not refresh hashes to hide modifications.

#!/usr/bin/env python3
"""Generate a third-party license inventory from locked Cargo metadata.

No compilation or network access is performed. Registry/git package files are
read from their Cargo source directories; only legal-named files are copied.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, sys
from pathlib import Path

LEGAL_NAME = re.compile(r"^(LICENSE(?:[-_.].*)?|LICENCE(?:[-_.].*)?|COPYING(?:[-_.].*)?|NOTICE(?:[-_.].*)?|COPYRIGHT(?:[-_.].*)?|PATENTS(?:[-_.].*)?|AUTHORS?|THIRD[-_]PARTY(?:[-_.].*)?|LEGAL(?:[-_.].*)?)$", re.I)
NATIVE_RECURSIVE = re.compile(r"(sys|aws-lc|ring|zstd|lz4|snappy|rocksdb|openssl|boring|jemalloc|mimalloc|sqlite|libgit2|onig|bindgen|c.?ares|curl)", re.I)

p=argparse.ArgumentParser()
p.add_argument('--metadata',required=True,type=Path)
p.add_argument('--lock',required=True,type=Path)
p.add_argument('--qdrant-license',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--cargo-cache',type=Path,default=Path.home()/'.cargo'/'registry'/'cache')
p.add_argument('--source-commit',default='bc0eec0015771e8c59134b1b83a740418efcff7e')
p.add_argument('--source-tree',default='f3335fe4f9474c3bbc5274785c4bde930fc272be')
p.add_argument('--binary-sha256',default='9a44f09da70af7921da7b2a6893b98c1ea3d9dcab61986d3504b63f4e3dfa0e8')
p.add_argument('--target',default='x86_64-unknown-linux-gnu')
a=p.parse_args()
meta=json.loads(a.metadata.read_text())
node_by_id={n['id']:n for n in meta['resolve']['nodes']}
root_id=meta['resolve']['root']
seen=set(); pending=[root_id]
while pending:
    pid=pending.pop()
    if pid in seen: continue
    seen.add(pid)
    for dep in node_by_id[pid].get('deps',[]):
        kinds=dep.get('dep_kinds',[])
        # Cargo's filtered resolve graph: keep ordinary runtime deps only;
        # build/dev edges are excluded from this binary dependency inventory.
        if not kinds or any(k.get('kind') is None for k in kinds): pending.append(dep['pkg'])
packages={x['id']:x for x in meta['packages']}
out=a.output.resolve(); licroot=out/'licenses'/'texts'; licroot.mkdir(parents=True,exist_ok=True)
# Clean generated license-text objects only; preserve source archive and script.
for f in licroot.iterdir():
    if f.is_file(): f.unlink()

# SPDX alternatives explicitly selected for the delivered binary's notice accounting.
def choice(name, expr):
    if name=='colored' and expr=='MPL-2.0': return 'MPL-2.0 (source archive included)'
    if name=='self_cell': return 'Apache-2.0 (chosen from declared Apache-2.0 OR GPL-2.0-only)'
    if name in {'slog','slog-scope','slog-stdlog'}: return 'Apache-2.0 (permissive option in declared OR expression)'
    if not expr: return 'UNSPECIFIED: review required'
    if ' AND ' in expr: return 'Full conjunctive expression retained; no single alternative selected'
    if ' OR ' in expr:
        terms=[x.strip(' ()') for x in expr.split(' OR ')]
        for preferred in ('Apache-2.0','MIT','BSD-3-Clause','ISC','0BSD','Unlicense','Zlib'):
            if preferred in terms: return preferred+' (permissive option in declared OR expression)'
    return 'Declared expression; no alternative selected'

def spdx_expression(expr):
    # Cargo package metadata commonly uses the historic `MIT/Apache-2.0`
    # shorthand; represent it in SPDX form while preserving the original field.
    if not expr: return None
    return re.sub(r'(?<=[A-Za-z0-9.+-])/(?=[A-Za-z0-9.+-])',' OR ',expr)

def legal_files(pkg):
    mp=Path(pkg['manifest_path']).resolve(); base=mp.parent
    if not base.is_dir(): return []
    found=[]
    declared=pkg.get('license_file')
    if declared:
        candidate=(base/declared).resolve()
        if candidate.is_file() and candidate.is_relative_to(base): found.append(candidate)
    # Package-root legal docs for every dependency.
    for f in base.iterdir():
        if f.is_file() and LEGAL_NAME.match(f.name): found.append(f)
    # Include legal docs inside license/vendor directories for any crate;
    # native bindings additionally get a full legal-filename recursive scan.
    # No source files are copied by these filename-only rules.
    native=NATIVE_RECURSIVE.search(pkg['name']) is not None
    legal_dirs={'license','licenses','third_party','third-party','vendor','vendors','legal'}
    for f in base.rglob('*'):
        if not f.is_file() or not LEGAL_NAME.match(f.name): continue
        relative=f.relative_to(base)
        under_legal_dir=any(part.lower() in legal_dirs for part in relative.parts[:-1])
        if native or under_legal_dir:
            try:
                if f.stat().st_size <= 2_000_000: found.append(f)
            except OSError: pass
    return sorted(set(found), key=lambda x: str(x))

def copy_legal(f, pkg):
    data=f.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    # Content-addressed path deduplicates common MIT/Apache texts while the
    # inventory retains original package-relative filename/provenance.
    safe=re.sub(r'[^A-Za-z0-9._+-]+','_',f.name)
    dest=licroot/f'{digest[:24]}-{safe}'
    if not dest.exists(): dest.write_bytes(data)
    try: original_relative=str(f.relative_to(Path(pkg['manifest_path']).resolve().parent))
    except ValueError: original_relative=f.name
    return {'path':str(dest.relative_to(out)), 'sha256':digest, 'original_name':f.name, 'original_relative_path':original_relative}

records=[]; root_package=None
for pid in sorted(seen):
    pkg=packages[pid]
    if pid==root_id:
        root_package=pkg
        continue
    expr=pkg.get('license')
    files=legal_files(pkg)
    records.append({
      'name':pkg['name'],'version':pkg['version'],'source':pkg.get('source') or 'local-path',
      'spdx':spdx_expression(expr),'declared_license_expression':expr,
      'permissive_choice':choice(pkg['name'],spdx_expression(expr)),
      'license_file_metadata':pkg.get('license_file'),
      'license_files':[copy_legal(f,pkg) for f in files],
      'review_note':('License expression missing; included under Qdrant root Apache-2.0 pending review.' if not expr and pkg['source'] is None else None)
    })

# Copy Qdrant's project license separately, since it is not third party.
q_data=a.qdrant_license.read_bytes(); q_hash=hashlib.sha256(q_data).hexdigest()
q_dest=out/'licenses'/'QDRANT-LICENSE'
q_dest.parent.mkdir(parents=True,exist_ok=True); q_dest.write_bytes(q_data)
lock_hash=hashlib.sha256(a.lock.read_bytes()).hexdigest()
meta_hash=hashlib.sha256(a.metadata.read_bytes()).hexdigest()
metadata_copy=out/'cargo-metadata-x86_64-unknown-linux-gnu.json'
shutil.copyfile(a.metadata,metadata_copy)
lock_copy=out/'Cargo.lock.v45'
shutil.copyfile(a.lock,lock_copy)
# Retain the exact MPL-2.0 crate source archive. The lockfile checksum is the
# crates.io package checksum and must match the bytes copied from Cargo cache.
lock_text=a.lock.read_text()
colored_match=re.search(r'(?ms)^\[\[package\]\]\n(?:(?!^\[\[package\]\]).)*?^name = "colored"\nversion = "3\.1\.1"\n(?:(?!^\[\[package\]\]).)*?^checksum = "([0-9a-f]{64})"',lock_text)
if not colored_match: raise SystemExit('colored 3.1.1 checksum not found in Cargo.lock')
colored_lock_sha=colored_match.group(1)
colored_candidates=list(a.cargo_cache.glob('*/colored-3.1.1.crate'))
if len(colored_candidates)!=1: raise SystemExit(f'expected one cached colored-3.1.1.crate, found {len(colored_candidates)}')
colored_src=colored_candidates[0]
colored_actual=hashlib.sha256(colored_src.read_bytes()).hexdigest()
if colored_actual!=colored_lock_sha: raise SystemExit(f'colored crate checksum mismatch: lock={colored_lock_sha}, archive={colored_actual}')
source_dir=out/'source'; source_dir.mkdir(parents=True,exist_ok=True)
colored_dest=source_dir/'colored-3.1.1.crate'
shutil.copyfile(colored_src,colored_dest)
source_readme=(
 '# Source availability: `colored` 3.1.1\n\n'
 'The runtime dependency `colored` 3.1.1 is declared MPL-2.0. This directory includes its unmodified crates.io `.crate` source archive; no Qdrant or Veortex engine source is included in this archive.\n\n'
 '- Version: `3.1.1`\n'
 '- SPDX: `MPL-2.0`\n'
 '- Cargo.lock package checksum: `'+colored_lock_sha+'`\n'
 '- Included archive SHA-256: `'+colored_actual+'` (matches the Cargo.lock checksum)\n'
 '- Upstream source/download: https://crates.io/api/v1/crates/colored/3.1.1/download\n'
 '- Crates.io package page: https://crates.io/crates/colored/3.1.1\n'
 '- MPL-2.0 license text: see the corresponding `colored` license file entry in `THIRD_PARTY_NOTICES.md`.\n'
)
(out/'SOURCE-AVAILABILITY.md').write_text(source_readme)
manifest={
 'schema':'v1','audit_scope':'Qdrant 1.20.0 default-feature normal dependency closure for x86_64-unknown-linux-gnu; target-filtered Cargo metadata; build/dev dependencies excluded',
 'source':{'commit':a.source_commit,'tree':a.source_tree,'cargo_lock_sha256':lock_hash,'cargo_lock_file':str(lock_copy.relative_to(out))},
 'binary':{'sha256':a.binary_sha256,'target':a.target,'dynamic_dependencies':['libgcc_s.so.1','libm.so.6','libc.so.6','/lib64/ld-linux-x86-64.so.2'],'max_glibc_symbol_version':'GLIBC_2.34'},
 'metadata':{'sha256':meta_hash,'source_file':str(metadata_copy.relative_to(out)),'command':'cargo metadata --format-version 1 --locked --offline --filter-platform x86_64-unknown-linux-gnu'},
 'colored_source_archive':{'name':'colored','version':'3.1.1','spdx':'MPL-2.0','cargo_lock_checksum':colored_lock_sha,'archive_sha256':colored_actual,'path':str(colored_dest.relative_to(out)),'download_url':'https://crates.io/api/v1/crates/colored/3.1.1/download'},
 'project_license':{'name':'Qdrant','spdx':'Apache-2.0','path':str(q_dest.relative_to(out)),'sha256':q_hash},
 'veortex_project_note':'Veortex engine code is outside this Cargo third-party inventory; redistribution of this binary was explicitly authorized by its owner. No general SPDX license is inferred for Veortex source.',
 'counts':{'normal_closure_including_root':len(seen),'dependency_packages_excluding_root':len(records),'registry_crates':sum(1 for r in records if r['source'].startswith('registry+')),'git_crates':sum(1 for r in records if r['source'].startswith('git+')),'local_path_crates':sum(1 for r in records if r['source']=='local-path')},
 'packages':records,
 'review_flags':[
   {'package':'colored','version':'3.1.1','spdx':'MPL-2.0','note':'MPL-2.0 component; its unmodified registry source archive is included with Cargo.lock checksum and source availability information.'},
   {'packages':['bm25','io_bridge','io_bridge_object_store'],'note':'These local Qdrant path packages lack package-level license metadata; Qdrant root declares Apache-2.0. Confirm project-level coverage during legal review.'},
   {'note':'This notice inventory records Cargo metadata and included license texts; it is not a legal opinion or a blanket compliance guarantee.'}
 ]
}
(out/'license-audit.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
# Human-readable package table with links to the included texts.
lines=['# Third-party notices and dependency inventory','',
       'This directory records licenses for the Qdrant 1.20.0 default-feature runtime dependency closure used for the V45 x86_64 Linux binary. It is generated from the exact locked Cargo metadata described in `license-audit.json`. License texts and notices are copied from package sources; only legal-named files are included. This document is not a legal opinion or a blanket compliance guarantee.','',
       'Qdrant project license: [`licenses/QDRANT-LICENSE`](licenses/QDRANT-LICENSE) (Apache-2.0). The target source metadata lists Qdrant as Apache-2.0.','',
       'The `colored 3.1.1` dependency is MPL-2.0. Its unmodified `.crate` archive is included under `source/`; see [`SOURCE-AVAILABILITY.md`](SOURCE-AVAILABILITY.md) for exact checksum and upstream source URL. `self_cell` is accounted for under its Apache-2.0 alternative; `slog`, `slog-scope`, and `slog-stdlog` are accounted for under Apache-2.0 alternatives. The inventory retains each package’s complete declared SPDX expression.','',
       'The V45 ELF (SHA-256 `'+a.binary_sha256+'`) dynamically depends on `libgcc_s.so.1`, `libm.so.6`, `libc.so.6`, and `/lib64/ld-linux-x86-64.so.2`; its highest observed GLIBC symbol version is `GLIBC_2.34`. Vendor legal files found recursively in native dependency crates (including AWS-LC, ring, and zstd) are included below.','',
       'Veortex engine code is outside this Cargo dependency inventory. Redistribution of this binary was explicitly authorized by its owner; no general SPDX license is inferred for Veortex source.','',
       'The package table includes local Qdrant workspace dependencies as well as external crates. Three local Qdrant path packages (`bm25`, `io_bridge`, `io_bridge_object_store`) have no package-level license metadata in the source manifest; they are noted as covered by the Qdrant root Apache-2.0 declaration pending review.','',
       '| Package | Version | SPDX expression | Accounting choice | License/notice files |','|---|---:|---|---|---|']
for r in sorted(records,key=lambda x:(x['name'],x['version'])):
    fs=', '.join(f"[`{Path(x['path']).name}`]({x['path']})" for x in r['license_files']) or 'No legal-named file found in cached source; see declared SPDX expression.'
    lines.append(f"| `{r['name']}` | `{r['version']}` | `{r['spdx'] or 'UNSPECIFIED'}` | {r['permissive_choice']} | {fs} |")
(out/'THIRD_PARTY_NOTICES.md').write_text('\n'.join(lines)+'\n')
print(f'wrote {len(records)} dependency package records; closure incl root={len(seen)}; metadata sha256={meta_hash}; Cargo.lock sha256={lock_hash}')

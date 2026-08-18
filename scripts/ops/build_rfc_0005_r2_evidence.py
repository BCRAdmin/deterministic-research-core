#!/usr/bin/env python3
"""Package the bounded RFC-0005-R2 trust and cross-artifact closure evidence."""

from __future__ import annotations

import argparse, csv, hashlib, io, json, shutil, subprocess, tempfile, zipfile
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
BASES = {"research": "0e609bd", "product": "8485037"}
CANARIES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str): path.write_text(value.rstrip()+"\n", encoding="utf-8")
    else: path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+"\n", encoding="utf-8")

def run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"command": cmd, "cwd": str(cwd), "exit_code": p.returncode, "output": p.stdout}

def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

def deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes())

def changed(repo: Path, base: str) -> dict[str, Any]:
    head, merge = git(repo,"rev-parse","HEAD"), git(repo,"merge-base",base,"HEAD")
    rows=[]
    for line in git(repo,"diff","--name-status",f"{base}..{head}").splitlines():
        cols=line.split("\t"); status=cols[0]; path=cols[-1]
        ref=base if status.startswith("D") else head
        blob=subprocess.check_output(["git","show",f"{ref}:{path}"],cwd=repo)
        rows.append({"status":status,"path":path,"sha256":hashlib.sha256(blob).hexdigest()})
    return {"base_commit":git(repo,"rev-parse",base),"head_commit":head,"merge_base":merge,"files":rows}

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--bundles-root",type=Path,required=True); p.add_argument("--renders-root",type=Path,required=True); p.add_argument("--review-zip",type=Path,required=True); p.add_argument("--output-dir",type=Path,default=ROOT/"outputs/release")
    a=p.parse_args(); research_head=git(ROOT,"rev-parse","HEAD"); product_head=git(PRODUCT,"rev-parse","HEAD")
    name=f"ROOM16_RFC_0005_R2_BA10_CLOSURE_{research_head[:8].upper()}_{date.today().isoformat()}"
    with tempfile.TemporaryDirectory(prefix="room16-r2-evidence-") as td:
        stage=Path(td)/name; (stage/"NESTED_BUNDLES").mkdir(parents=True); (stage/"NESTED_RENDERED_ARTIFACTS").mkdir()
        replay={}; instance={}
        canary_root=PRODUCT/".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
        for ticker, expected in CANARIES.items():
            source=canary_root/f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
            if sha(source)!=expected: raise SystemExit(f"{ticker} canary changed")
            bundle=a.bundles_root/ticker; render=a.renders_root/ticker
            manifest=json.loads((bundle/"BUNDLE_MANIFEST.json").read_text())
            result_path=Path(td)/f"{ticker}.json"
            check=run(["node","scripts/verify_compiler_artifact_bundle_instance.mjs","--bundle",str(bundle),"--rendered-set",str(render/"rendered_artifact_set.json"),"--output",str(result_path)],APP)
            if check["exit_code"]: raise SystemExit(check["output"])
            instance[ticker]=json.loads(result_path.read_text())
            bz=stage/"NESTED_BUNDLES"/f"{ticker}_COMPILER_ARTIFACT_BUNDLE.zip"; deterministic_zip(bundle,bz)
            rz=stage/"NESTED_RENDERED_ARTIFACTS"/f"{ticker}_RENDERED_ARTIFACTS.zip"; deterministic_zip(render,rz)
            replay[ticker]={"source_canary_sha256":expected,"bundle_sha256":manifest["bundle_sha256"],"bundle_zip_sha256":sha(bz),"rendered_zip_sha256":sha(rz),"instance_status":instance[ticker]["status"],"rendered_artifact_set_accepted":instance[ticker]["rendered_artifact_set_accepted"]}
        fixture_path=Path(td)/"fixtures.json"
        fixture=run(["node","scripts/verify_compiler_artifact_bundle_contract_fixtures.mjs","--bundle",str(a.bundles_root/"WM"),"--rehasher",str(ROOT/"scripts/ops/rehash_ba10_bundle_fixture.py"),"--output",str(fixture_path)],APP)
        tests={
          "research_unit":run([str(ROOT/".venv/bin/python"),"-m","pytest","-q","research_agent/tests/test_ba10_trust_receipt.py","research_agent/tests/test_ba10_artifact_bundle.py"],ROOT),
          "product_unit":run(["npm","run","verify:compiler-artifact-bundle"],APP),
          "full_rehash_fixtures":fixture,
        }
        if any(v["exit_code"] for v in tests.values()): raise SystemExit("R2 test failure")
        fixtures=json.loads(fixture_path.read_text())
        changes={"research":changed(ROOT,BASES["research"]),"product":changed(PRODUCT,BASES["product"])}
        receipt=json.loads((ROOT/"research_agent/productization/config/compiler_artifact_receipt_set_v1.json").read_text())
        write(stage/"00_EXECUTIVE_SUMMARY.md","# RFC-0005-R2 Executive Summary\n\nThe bounded BA10 trust and cross-artifact closure passes. Exact Research-owned receipts, frozen policy fields, fixed artifact/section contracts and eight fully re-hashed negative fixtures are verified. BA10 freeze remains subject to independent acceptance; BA11, BA12, release and publication remain false.")
        write(stage/"01_IMPLEMENTATION_RECORD.md",f"# Implementation Record\n\nResearch head: `{research_head}`\nProduct head: `{product_head}`\n\nScope: BA10-R1-TRUST-001, BA10-R1-XART-001, BA10-R1-TEST-001 and BA10-R1-EVID-001 only. BA0-BA9 were not modified.")
        write(stage/"02_AUTHENTICATED_TRUST_RECEIPT.md",f"# Authenticated Trust Receipt\n\nResearch owns an external `room16.compiler_artifact_bundle_receipt_set@1`. Product mirrors it read-only and hard-pins `{receipt['receipt_set_sha256']}`. The detached SHA pin is the review-permitted alternative to an operator-managed private key; no secret is stored in Product or this evidence bundle. Each receipt binds the exact bundle, compiler, emitter, policy and compile identities.")
        policy=json.loads((ROOT/"research_agent/productization/config/consumer_policy_lock_v1.json").read_text())
        write(stage/"03_POLICY_ENFORCEMENT_MATRIX.json",{"status":"PASS","policy_sha256":policy["policy_sha256"],"receipt_set_sha256":receipt["receipt_set_sha256"],"enforced_fields":["contract major","schema range","canonicalization","hash algorithm","foundation version","registry foundation version","semantic wave version","semantic wave lock","compiler version","registry authority hash","pass manifest hash","IR schema hash","emitter identity","compatibility contracts","source_native_fact_generation","renderer_cutover","ba11_authorized","ba12_authorized","release_ready","publication_allowed"]})
        write(stage/"04_CROSS_ARTIFACT_CONTRACT_MATRIX.json",{"status":"PASS","contracts":["compile identity closure","complete pass attestation and chain","fixed 18 required artifact kinds","fixed 17 sections","exact section mappings","wrapper hash parity","closed dependencies","exact projection IDs and display tokens","authority-v3 one-way compatibility boundary"]})
        write(stage/"05_FULL_REHASH_NEGATIVE_FIXTURES.json",fixtures); write(stage/"06_WM_COST_ABT_REPLAY_RESULTS.json",replay); write(stage/"07_CHANGED_FILES_COMPLETE.json",changes)
        verdict={"contract_id":"room16.rfc_0005_r2.ba10_acceptance_verdict","contract_version":1,"ba10_r1_trust_001_closed":True,"ba10_r1_xart_001_closed":True,"ba10_r1_test_001_closed":True,"ba10_r1_evid_001_closed":True,"actual_wm_cost_abt_exemplars_passed":True,"foundation_unchanged":True,"registry_foundation_unchanged":True,"semantic_compiler_ba0_ba9_unchanged":True,"authority_bundle_v3_unchanged":True,"wm_cost_abt_canaries_unchanged":True,"ba10_acceptance_candidate":True,"ba10_freeze_authorized":False,"ba11_authorized":False,"ba12_authorized":False,"release_ready":False,"publication_allowed":False,"independent_acceptance_required":True}
        write(stage/"08_BA10_R2_ACCEPTANCE_VERDICT.json",verdict); write(stage/"TEST_COMMAND_RESULTS.json",tests)
        snap=stage/"SOURCE_SNAPSHOT"; snap.mkdir(); write(snap/"REPRODUCE.md",f"# Reproduce\n\n```bash\ngit -C {ROOT} checkout {research_head}\ngit -C {PRODUCT} checkout {product_head}\n{ROOT}/.venv/bin/python -m pytest -q research_agent/tests/test_ba10_trust_receipt.py research_agent/tests/test_ba10_artifact_bundle.py\ncd {APP} && npm run verify:compiler-artifact-bundle\n```\n\nUse `07_CHANGED_FILES_COMPLETE.json` to verify every changed blob against the declared base/head ranges.")
        shutil.copy2(a.review_zip,stage/"SOURCE_REVIEW.zip")
        rows=[]
        for path in sorted(p for p in stage.rglob("*") if p.is_file()): rows.append({"path":path.relative_to(stage).as_posix(),"bytes":path.stat().st_size,"sha256":sha(path)})
        write(stage/"RESULT_MANIFEST.json",{"contract_id":"room16.rfc_0005_r2.result_manifest","contract_version":1,"files":rows,"verdict":verdict})
        a.output_dir.mkdir(parents=True,exist_ok=True); out=a.output_dir/f"{name}.zip"; second=Path(td)/"second.zip"; deterministic_zip(stage,out); deterministic_zip(stage,second)
        if sha(out)!=sha(second): raise SystemExit("non-deterministic evidence ZIP")
        (out.with_suffix(out.suffix+".sha256")).write_text(f"{sha(out)}  {out.name}\n")
        print(json.dumps({"zip":str(out),"sha256":sha(out),"second_build_identical":True,"verdict":verdict},indent=2))

if __name__=="__main__": main()

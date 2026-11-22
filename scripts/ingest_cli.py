"""批量导入 Markdown 语料。

用法:
    python scripts/ingest_cli.py --dir D:/项目1/md
    python scripts/ingest_cli.py --dir D:/项目1/md --limit 5
    python scripts/ingest_cli.py --dir D:/项目1/md --force
    python scripts/ingest_cli.py --dir D:/项目1/md --workers 4
"""
import argparse
import hashlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semikb.common.constants import DocStatus, TaskStatus, TaskType
from semikb.common.utils import new_uid, now
from semikb.dao.document_dao import DocumentDao
from semikb.dao.task_dao import TaskDao
from semikb.ingest.milvus_store import MilvusStore
from semikb.ingest.pipeline import IngestPipeline


def parse_args():
    parser = argparse.ArgumentParser(description="批量导入 Markdown 语料")
    parser.add_argument("--dir", default="D:/项目1/md")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="已存在的文档也重新入库")
    parser.add_argument("--workers", type=int, default=4, help="并发处理文档数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.dir)
    files = sorted(source_dir.glob("*.md"))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print("没有找到 Markdown 文件")
        return 1

    docs = DocumentDao()
    tasks = TaskDao()
    store = MilvusStore()
    pipeline = IngestPipeline()
    store.ensure_collection()
    task_id = tasks.create(TaskType.UPLOAD, doc_uid=None)
    tasks.update(task_id, status=TaskStatus.RUNNING, progress=1, message="批量导入开始")

    total_files = len(files)
    lock = threading.Lock()
    stats = {"succeeded": 0, "skipped": 0, "failed": 0, "chunks": 0, "done": 0}
    failures: list[tuple[str, str]] = []

    def prepare(path: Path) -> dict | None:
        data = path.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()
        existed = docs.get_by_hash(file_hash)
        if existed and not args.force:
            if existed.get("status") == DocStatus.READY:
                return None
            docs.update_fields(existed["doc_uid"], status=DocStatus.PENDING, error_msg=None)
            return existed
        if existed:
            docs.update_fields(existed["doc_uid"], status=DocStatus.PENDING, error_msg=None)
            return existed
        doc_uid = new_uid()
        docs.create(
            doc_uid=doc_uid,
            filename=path.name,
            title=path.stem,
            source_path=str(path),
            file_hash=file_hash,
            size_bytes=len(data),
            milvus_collection=store.active_collection,
            status=DocStatus.PENDING,
        )
        return docs.get(doc_uid)

    def process(path: Path) -> tuple[str, int, str]:
        """返回 (状态, 切片数, 错误信息)。"""
        try:
            doc = prepare(path)
            if doc is None:
                return "skipped", 0, ""
            result = pipeline.run_document(
                doc["doc_uid"],
                task_id=None,
                flush_collection=False,
                verify_count=False,
            )
            return "succeeded", int(result.get("chunks", 0)), ""
        except Exception as e:
            return "failed", 0, str(e)[:300]

    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as pool:
        futures = {pool.submit(process, path): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                status, chunks, error = future.result()
            except Exception as e:
                status, chunks, error = "failed", 0, str(e)[:300]
            with lock:
                stats["done"] += 1
                if status == "skipped":
                    stats["skipped"] += 1
                elif status == "failed":
                    stats["failed"] += 1
                    failures.append((path.name, error))
                    print(f"[FAIL] {path.name}: {error}")
                else:
                    stats["succeeded"] += 1
                    stats["chunks"] += chunks
                index = stats["done"]
                tasks.update(
                    task_id,
                    progress=min(95, int(95 * index / total_files)),
                    message=(
                        f"已处理 {index}/{total_files} 篇，成功 {stats['succeeded']}，"
                        f"跳过 {stats['skipped']}，失败 {stats['failed']}"
                    ),
                )
                print(
                    f"[{index}/{total_files}] {path.name} "
                    f"ok={stats['succeeded']} skip={stats['skipped']} fail={stats['failed']}"
                )

    store.flush()
    milvus_total = store.count_total()
    if milvus_total < stats["chunks"]:
        failures.append(("milvus", f"切片总量不足: 本次 {stats['chunks']} / 集合 {milvus_total}"))
    failed = stats["failed"] + (1 if milvus_total < stats["chunks"] else 0)
    final_status = TaskStatus.SUCCEEDED if failed == 0 else TaskStatus.FAILED
    tasks.update(
        task_id,
        status=final_status,
        progress=100,
        total_chunks=stats["chunks"],
        done_chunks=stats["chunks"],
        message=(
            f"导入完成: 成功 {stats['succeeded']}，跳过 {stats['skipped']}，失败 {stats['failed']}，"
            f"切片 {stats['chunks']}，集合总量 {milvus_total}"
        ),
        finished_at=now(),
    )
    print(
        f"\n完成: 文件 {total_files}，成功 {stats['succeeded']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，切片 {stats['chunks']}，集合总量 {milvus_total}"
    )
    for name, error in failures[:10]:
        print(f"  - {name}: {error}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

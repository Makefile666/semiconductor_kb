"""引用数据访问。"""
from semikb.dao.db_pool import DbPool


class CitationDao:
    def __init__(self):
        self._pool = DbPool.instance()

    @staticmethod
    def _source_url(doc_uid: str | None, url: str | None) -> str | None:
        if doc_uid:
            return f"/document/{doc_uid}"
        value = (url or "").strip()
        if value.startswith(("http://", "https://")):
            return value
        return None

    def add_many(self, message_id: int, sources: list[dict]) -> None:
        if not sources:
            return
        rows = []
        for rank, item in enumerate(sources, 1):
            rows.append(
                (
                    message_id,
                    item.get("doc_uid"),
                    item.get("chunk_index"),
                    rank,
                    (item.get("title") or "")[:255] or None,
                    (item.get("filename") or "")[:255] or None,
                    (self._source_url(item.get("doc_uid"), item.get("url")) or "")[:512] or None,
                    (item.get("snippet") or "")[:512] or None,
                )
            )
        with self._pool.cursor() as cur:
            cur.executemany(
                "INSERT INTO t_citation "
                "(message_id, doc_uid, chunk_index, `rank`, title, filename, url, snippet) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                rows,
            )

    def list_by_message(self, message_id: int) -> list[dict]:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT doc_uid, chunk_index, `rank`, title, filename, url, snippet "
                "FROM t_citation WHERE message_id=%s ORDER BY `rank` ASC",
                (message_id,),
            )
            rows = cur.fetchall()
        for row in rows:
            row["url"] = self._source_url(row.get("doc_uid"), row.get("url"))
        return rows

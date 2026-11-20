"""管理台统计。"""
from semikb.dao.db_pool import DbPool
from semikb.dao.document_dao import DocumentDao
from semikb.dao.task_dao import TaskDao


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, max(0, int(len(values) * 0.95) - 1))
    return int(values[index])


class StatsService:
    @classmethod
    def overview(cls, days: int = 7) -> dict:
        days = max(1, min(30, int(days)))
        docs = DocumentDao().stats()
        tasks = TaskDao()
        pool = DbPool.instance()
        with pool.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total, SUM(status='active') AS active FROM t_session")
            sessions = cur.fetchone() or {}
            cur.execute(
                "SELECT COUNT(*) AS today FROM t_session WHERE created_at >= CURDATE()"
            )
            sessions_today = int((cur.fetchone() or {}).get("today") or 0)
            cur.execute(
                "SELECT COUNT(*) AS total, SUM(created_at >= CURDATE()) AS today "
                "FROM t_message WHERE role='bot' AND source <> 'direct'"
            )
            qa = cur.fetchone() or {}
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(verified=1) AS verified, "
                "SUM(rating=1) AS up, SUM(rating=-1) AS down, "
                "SUM(rewrite_count>0) AS rewritten, "
                "SUM(regenerate_count>0) AS regenerated, "
                "SUM(EXISTS(SELECT 1 FROM t_citation c WHERE c.message_id=t_message.id)) AS cited "
                "FROM t_message WHERE role='bot' AND source <> 'direct' "
                "AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,),
            )
            quality = cur.fetchone() or {}
            cur.execute(
                "SELECT latency_ms FROM t_message WHERE role='bot' AND source <> 'direct' "
                "AND latency_ms IS NOT NULL AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,),
            )
            latencies = [int(r["latency_ms"]) for r in cur.fetchall()]
            cur.execute(
                "SELECT COALESCE(source,'unknown') AS source, COUNT(*) AS n "
                "FROM t_message WHERE role='bot' AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY source ORDER BY n DESC",
                (days,),
            )
            routes = cur.fetchall()
            cur.execute(
                "SELECT DATE(created_at) AS day, COUNT(*) AS qa_count, "
                "SUM(EXISTS(SELECT 1 FROM t_citation c WHERE c.message_id=t_message.id)) AS cited "
                "FROM t_message WHERE role='bot' AND source <> 'direct' "
                "AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY DATE(created_at) ORDER BY day ASC",
                (days,),
            )
            series = cur.fetchall()
            cur.execute(
                "SELECT c.doc_uid, COUNT(*) AS citations, MAX(d.title) AS title, MAX(d.filename) AS filename "
                "FROM t_citation c LEFT JOIN t_document d ON d.doc_uid=c.doc_uid "
                "WHERE c.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY c.doc_uid ORDER BY citations DESC LIMIT 8",
                (days,),
            )
            top_documents = cur.fetchall()

        total_bot = int(quality.get("total") or 0)
        verified = int(quality.get("verified") or 0)
        cited = int(quality.get("cited") or 0)
        up = int(quality.get("up") or 0)
        down = int(quality.get("down") or 0)
        rated = up + down
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0
        return {
            "days": days,
            "documents": docs,
            "sessions": {
                "total": int(sessions.get("total") or 0),
                "active": int(sessions.get("active") or 0),
                "today": sessions_today,
            },
            "qa": {
                "total": int(qa.get("total") or 0),
                "today": int(qa.get("today") or 0),
                "window": total_bot,
            },
            "quality": {
                "verified_rate": round(verified / total_bot, 4) if total_bot else 0,
                "citation_rate": round(cited / total_bot, 4) if total_bot else 0,
                "satisfied_rate": round(up / rated, 4) if rated else 0,
                "rewrite_rate": round(int(quality.get("rewritten") or 0) / total_bot, 4) if total_bot else 0,
                "regenerate_rate": round(int(quality.get("regenerated") or 0) / total_bot, 4) if total_bot else 0,
                "up": up,
                "down": down,
                "rated": rated,
            },
            "latency": {
                "avg_ms": avg_latency,
                "p95_ms": _p95(latencies),
                "samples": len(latencies),
            },
            "routes": [
                {"source": row.get("source"), "count": int(row.get("n") or 0)}
                for row in routes
            ],
            "series": [
                {
                    "date": str(row.get("day")),
                    "qa_count": int(row.get("qa_count") or 0),
                    "citation_count": int(row.get("cited") or 0),
                }
                for row in series
            ],
            "top_documents": [
                {
                    "doc_uid": row.get("doc_uid"),
                    "title": row.get("title") or row.get("filename") or "未知文档",
                    "filename": row.get("filename") or "",
                    "citations": int(row.get("citations") or 0),
                }
                for row in top_documents
            ],
            "tasks": {
                "pending": tasks.pending_count(),
            },
        }

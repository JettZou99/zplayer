"""SQLite 数据库层 — 管理收藏单词的持久化存储。"""

from __future__ import annotations

import csv
import logging
import sqlite3
import threading
from pathlib import Path

from data.models import CollectedWord, _format_timestamp
from utils.platforms import get_db_path

logger = logging.getLogger(__name__)

_DB_PATH = get_db_path()


class WordBookDB:
    """单词本数据库，单例式使用。"""

    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or _DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    def _get_conn(self) -> sqlite3.Connection:
        """创建一个新的数据库连接（每次操作创建，避免跨线程问题）。"""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        """初始化表结构（幂等）。"""
        conn = self._get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS collected_words (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    word              TEXT NOT NULL UNIQUE,
                    us_phonetic       TEXT,
                    uk_phonetic       TEXT,
                    definitions       TEXT NOT NULL,
                    subtitle_text     TEXT,
                    subtitle_start_ms INTEGER,
                    subtitle_end_ms   INTEGER,
                    video_name        TEXT,
                    collected_at      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_word ON collected_words(word);
                CREATE INDEX IF NOT EXISTS idx_collected_at
                    ON collected_words(collected_at DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # 写操作
    # ------------------------------------------------------------------ #

    def add(self, word_data: CollectedWord) -> bool:
        """
        添加单词到词库。若单词已存在则更新（INSERT OR REPLACE）。

        Returns:
            True 表示写入成功
        """
        with self._lock:
            conn = self._get_conn()
            try:
                d = word_data.to_db_dict()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO collected_words
                        (word, us_phonetic, uk_phonetic, definitions,
                         subtitle_text, subtitle_start_ms, subtitle_end_ms,
                         video_name, collected_at)
                    VALUES
                        (:word, :us_phonetic, :uk_phonetic, :definitions,
                         :subtitle_text, :subtitle_start_ms, :subtitle_end_ms,
                         :video_name, :collected_at)
                    """,
                    d,
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error("添加收藏单词失败: %s", e)
                return False
            finally:
                conn.close()

    def remove(self, word: str) -> bool:
        """按单词删除收藏记录。"""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "DELETE FROM collected_words WHERE word = ?", (word,)
                )
                conn.commit()
                return cur.rowcount > 0
            except sqlite3.Error as e:
                logger.error("删除收藏单词失败: %s", e)
                return False
            finally:
                conn.close()

    def remove_by_id(self, id: int) -> bool:
        """按 ID 删除收藏记录。"""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "DELETE FROM collected_words WHERE id = ?", (id,)
                )
                conn.commit()
                return cur.rowcount > 0
            except sqlite3.Error as e:
                logger.error("按ID删除收藏单词失败: %s", e)
                return False
            finally:
                conn.close()

    # ------------------------------------------------------------------ #
    # 读操作
    # ------------------------------------------------------------------ #

    def is_collected(self, word: str) -> bool:
        """检查单词是否已收藏。"""
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT 1 FROM collected_words WHERE word = ? LIMIT 1", (word,)
            )
            return cur.fetchone() is not None
        except sqlite3.Error as e:
            logger.error("查询收藏状态失败: %s", e)
            return False
        finally:
            conn.close()

    def get_all(self, order_by: str = "collected_at DESC") -> list[CollectedWord]:
        """获取全部收藏单词，按指定字段排序。"""
        # 白名单排序字段，防止 SQL 注入
        allowed = {
            "collected_at DESC",
            "collected_at ASC",
            "word ASC",
            "word DESC",
        }
        if order_by not in allowed:
            order_by = "collected_at DESC"
        conn = self._get_conn()
        try:
            cur = conn.execute(
                f"SELECT * FROM collected_words ORDER BY {order_by}"
            )
            rows = cur.fetchall()
            return [CollectedWord.from_db_row(dict(r)) for r in rows]
        except sqlite3.Error as e:
            logger.error("获取收藏列表失败: %s", e)
            return []
        finally:
            conn.close()

    def search(self, keyword: str) -> list[CollectedWord]:
        """模糊搜索单词。"""
        pattern = f"%{keyword}%"
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM collected_words WHERE word LIKE ? "
                "ORDER BY collected_at DESC",
                (pattern,),
            )
            rows = cur.fetchall()
            return [CollectedWord.from_db_row(dict(r)) for r in rows]
        except sqlite3.Error as e:
            logger.error("搜索收藏单词失败: %s", e)
            return []
        finally:
            conn.close()

    def count(self) -> int:
        """统计收藏单词总数。"""
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM collected_words")
            return cur.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("统计收藏数量失败: %s", e)
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # 导出
    # ------------------------------------------------------------------ #

    def export_csv(self, file_path: str) -> bool:
        """
        导出全部收藏单词到 CSV 文件（含 UTF-8 BOM，Excel 兼容）。

        Returns:
            True 表示导出成功
        """
        words = self.get_all()
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "单词",
                        "美式音标",
                        "英式音标",
                        "释义",
                        "字幕句子",
                        "字幕时间范围",
                        "视频文件名",
                        "收藏时间",
                    ]
                )
                for w in words:
                    time_range = w.subtitle_time_range or ""
                    writer.writerow(
                        [
                            w.word,
                            w.us_phonetic or "",
                            w.uk_phonetic or "",
                            w.definitions_text,
                            w.subtitle_text or "",
                            time_range,
                            w.video_name or "",
                            w.collected_at,
                        ]
                    )
            return True
        except OSError as e:
            logger.error("导出CSV失败: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """关闭数据库（当前实现每次操作创建新连接，无需额外关闭）。"""
        pass

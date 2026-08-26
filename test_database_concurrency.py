import asyncio
import os
import tempfile
import unittest

from utils.database import Database


class TestDatabaseConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_media_url_can_only_be_claimed_once(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = Database(db_path)
        try:
            await db.init()
            claims = await asyncio.gather(
                db.claim_media_url("https://example.com/image.png"),
                db.claim_media_url("https://example.com/image.png"),
            )
            self.assertEqual(sorted(claims), [False, True])
        finally:
            await db.close()
            for path in (db_path, db_path + "-shm", db_path + "-wal"):
                if os.path.exists(path):
                    os.remove(path)


if __name__ == "__main__":
    unittest.main()
import socket
import unittest

import main


class TestInstanceGuard(unittest.TestCase):
    def tearDown(self):
        main.release_instance_lock()

    def test_second_process_cannot_claim_instance_port(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()

        self.assertTrue(main.acquire_instance_lock(port))
        self.assertFalse(main.acquire_instance_lock(port))


if __name__ == "__main__":
    unittest.main()
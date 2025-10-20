import unittest
from unittest.mock import Mock, patch

# --- TESTS FOR ASYNC CLONE TASK API ---
class TestGCTSAsyncCloneTask(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.rid = 'RID1'
        self.url = 'https://example.com/repo.git'
        self.vsid = '6IT'
        self.task_id = 'task-123'
        self.payload = {'repository': self.rid, 'url': self.url, 'vsid': self.vsid, 'role': 'SOURCE', 'type': 'GITHUB', 'config': {}}

    def test_create_clone_task_success(self):
        response_mock = Mock()
        response_mock.json.return_value = {'taskId': self.task_id, 'status': 'SCHEDULED'}
        self.connection.post_obj_as_json.return_value = response_mock
        from sap.rest.gcts.simple import create_clone_task
        result = create_clone_task(self.connection, self.url, self.rid, vsid=self.vsid)
        self.assertEqual(result['taskId'], self.task_id)
        self.connection.post_obj_as_json.assert_called_once()

    def test_create_clone_task_error(self):
        self.connection.post_obj_as_json.side_effect = Exception('fail')
        from sap.rest.gcts.simple import create_clone_task, SAPCliError
        with self.assertRaises(SAPCliError):
            create_clone_task(self.connection, self.url, self.rid, vsid=self.vsid)

    def test_get_task_status_success(self):
        self.connection.get_json.return_value = {'taskId': self.task_id, 'status': 'RUNNING'}
        from sap.rest.gcts.simple import get_task_status
        result = get_task_status(self.connection, self.rid, self.task_id)
        self.assertEqual(result['status'], 'RUNNING')
        self.connection.get_json.assert_called_once()

    def test_get_task_status_error(self):
        self.connection.get_json.side_effect = Exception('fail')
        from sap.rest.gcts.simple import get_task_status, SAPCliError
        with self.assertRaises(SAPCliError):
            get_task_status(self.connection, self.rid, self.task_id)

    @patch('sap.rest.gcts.simple.get_task_status')
    def test_wait_for_task_success(self, mock_get_task_status):
        # Simulate RUNNING -> FINISHED
        mock_get_task_status.side_effect = [
            {'status': 'RUNNING'},
            {'status': 'FINISHED'}
        ]
        from sap.rest.gcts.simple import wait_for_task
        result = wait_for_task(self.connection, self.task_id, rid=self.rid, timeout=5, poll_interval=0.01, backoff=1.0)
        self.assertEqual(result['status'], 'FINISHED')

    @patch('sap.rest.gcts.simple.get_task_status')
    def test_wait_for_task_fail(self, mock_get_task_status):
        mock_get_task_status.return_value = {'status': 'FAILED'}
        from sap.rest.gcts.simple import wait_for_task, SAPCliError
        with self.assertRaises(SAPCliError):
            wait_for_task(self.connection, self.task_id, rid=self.rid, timeout=1, poll_interval=0.01, backoff=1.0)

    @patch('sap.rest.gcts.simple.get_task_status')
    def test_wait_for_task_timeout(self, mock_get_task_status):
        mock_get_task_status.return_value = {'status': 'RUNNING'}
        from sap.rest.gcts.simple import wait_for_task, SAPCliError
        with self.assertRaises(SAPCliError):
            wait_for_task(self.connection, self.task_id, rid=self.rid, timeout=0.05, poll_interval=0.01, backoff=1.0)

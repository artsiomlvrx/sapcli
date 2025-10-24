import unittest
from unittest.mock import MagicMock, patch
from sap.cli.gcts_task import create_clone_task, task_info, tasks_list, delete_task
from sap.rest.gcts.repo_task import RepositoryTask, GCTSRequestError, GCTSRepoNotExistsError, GCTSRepoCloneError

class TestGCTSTaskCLI(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.console = MagicMock()
        patcher = patch('sap.cli.core.get_console', return_value=self.console)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_create_clone_task_success(self):
        mock_task = MagicMock()
        mock_task.tid = '1234'
        mock_task.status = 'RUNNING'
        mock_task.type = 'CLONE_REPOSITORY'
        with patch.object(RepositoryTask, 'create', return_value=mock_task), \
             patch.object(mock_task, 'schedule_task', return_value=mock_task):
            args = MagicMock(package='ZPKG', branch=None)
            rc = create_clone_task(self.connection, args)
            self.assertEqual(rc, 0)
            self.console.printout.assert_any_call('Task ID:', '1234')
            self.console.printout.assert_any_call('Task Status:', 'RUNNING')
            self.console.printout.assert_any_call('Task Type:', 'CLONE_REPOSITORY')

    def test_create_clone_task_repo_not_exists(self):
        with patch.object(RepositoryTask, 'create', side_effect=GCTSRepoNotExistsError('err')):
            args = MagicMock(package='ZPKG', branch=None)
            rc = create_clone_task(self.connection, args)
            self.assertEqual(rc, 1)
            self.console.printerr.assert_called()

    def test_create_clone_task_clone_error(self):
        with patch.object(RepositoryTask, 'create', side_effect=GCTSRepoCloneError('err')):
            args = MagicMock(package='ZPKG', branch=None)
            rc = create_clone_task(self.connection, args)
            self.assertEqual(rc, 1)
            self.console.printerr.assert_called()

    def test_task_info_success(self):
        mock_task = MagicMock()
        mock_task.tid = '1234'
        mock_task.status = 'SUCCESS'
        mock_task.type = 'CLONE_REPOSITORY'
        with patch.object(RepositoryTask, 'get_by_id', return_value=mock_task):
            args = MagicMock(package='ZPKG', tid='1234')
            rc = task_info(self.connection, args)
            self.assertEqual(rc, 0)
            self.console.printout.assert_any_call('Task ID:', '1234')
            self.console.printout.assert_any_call('Task Status:', 'SUCCESS')
            self.console.printout.assert_any_call('Task Type:', 'CLONE_REPOSITORY')

    def test_task_info_error(self):
        with patch.object(RepositoryTask, 'get_by_id', side_effect=GCTSRequestError('err')):
            args = MagicMock(package='ZPKG', tid='1234')
            rc = task_info(self.connection, args)
            self.assertEqual(rc, 1)
            self.console.printerr.assert_called()

    def test_tasks_list_success(self):
        mock_tasks = [
            {'tid': '1', 'status': 'SUCCESS', 'type': 'CLONE_REPOSITORY'},
            {'tid': '2', 'status': 'RUNNING', 'type': 'CLONE_REPOSITORY'}
        ]
        with patch.object(RepositoryTask, 'get_list', return_value=mock_tasks), \
             patch('sap.cli.helpers.TableWriter') as MockTableWriter:
            args = MagicMock(package='ZPKG')
            rc = tasks_list(self.connection, args)
            self.assertEqual(rc, 0)
            MockTableWriter.return_value.printout.assert_called()

    def test_tasks_list_error(self):
        with patch.object(RepositoryTask, 'get_list', side_effect=GCTSRequestError('err')):
            args = MagicMock(package='ZPKG')
            rc = tasks_list(self.connection, args)
            self.assertEqual(rc, 1)
            self.console.printerr.assert_called()

    def test_delete_task_success(self):
        with patch.object(RepositoryTask, 'delete', return_value=None):
            args = MagicMock(package='ZPKG', tid='1234')
            rc = delete_task(self.connection, args)
            self.assertEqual(rc, None)

if __name__ == '__main__':
    unittest.main()

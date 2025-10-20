"""Simple API for gCTS operations"""

import json
import time

from sap import get_logger
from sap.rest.errors import HTTPRequestError
from sap.rest.gcts.remote_repo import Repository
from sap.rest.gcts.errors import (
    exception_from_http_error,
    GCTSRepoAlreadyExistsError,
    SAPCliError,
)


def _mod_log():
    return get_logger()


def fetch_repos(connection):
    """Returns list of repositories in the target systems defined by the given
       connection.
    """

    try:
        response = connection.get_json('repository')
    except HTTPRequestError as ex:
        raise exception_from_http_error(ex) from ex

    result = response.get('result', [])
    return [Repository(connection, repo['rid'], data=repo) for repo in result]


def wait_for_operation(repo, condition_fn, wait_for_ready, http_exc):
    """Wait for operation to finish"""

    start_time = time.time()
    while time.time() - start_time < wait_for_ready:
        repo.wipe_data()
        try:
            if condition_fn(repo):
                return

        except HTTPRequestError:
            _mod_log().debug('Failed to get status of the repository %s', repo.rid)

    raise SAPCliError(f'Waiting for the operation timed out\n{http_exc}')


# --- ASYNC CLONE TASK SUPPORT ---
def create_clone_task(connection, url, rid, vsid='6IT', start_dir='src/', vcs_token=None, role='SOURCE', typ='GITHUB', no_import=False, opts=None):
    """Create a clone task for the repository (async clone)"""
    config = {}
    if start_dir:
        config['VCS_TARGET_DIR'] = start_dir
    if vcs_token:
        config['CLIENT_VCS_AUTH_TOKEN'] = vcs_token
    if opts:
        config.update(opts)
    if no_import:
        config['NO_IMPORT'] = 'X'

    # Compose the payload for the clone task
    payload = {
        'repository': rid,
        'url': url,
        'vsid': vsid,
        'role': role,
        'type': typ,
        'config': config
    }

    # The endpoint for tasks may differ; adjust as needed for your backend
    # Here we assume /repository/{rid}/tasks with POST
    path = f'repository/{rid}/tasks'
    try:
        response = connection.post_obj_as_json(path, payload, accept='application/json')
        return response.json()
    except Exception as ex:
        raise SAPCliError(f'Failed to create clone task: {ex}')


def get_task_status(connection, rid, task_id):
    """Get the status of a gCTS task by ID"""
    path = f'repository/{rid}/tasks/{task_id}'
    try:
        response = connection.get_json(path)
        return response
    except Exception as ex:
        raise SAPCliError(f'Failed to get task status: {ex}')


def wait_for_task(connection, task_id, rid=None, timeout=600, poll_interval=2.0, backoff=1.5):
    """Wait for a gCTS task to finish, polling for status"""
    import time
    interval = poll_interval
    start = time.time()
    while time.time() - start < timeout:
        if rid is None:
            # Try to extract rid from task_id if possible, or require it
            raise SAPCliError('RID (repository id) is required to poll task status')
        status = get_task_status(connection, rid, task_id)
        state = status.get('status') or status.get('state')
        if state and str(state).upper() in ('SUCCESS', 'FINISHED', 'DONE'):
            return status
        if state and str(state).upper() in ('FAILED', 'ERROR'):
            raise SAPCliError(f'Task {task_id} failed: {status}')
        time.sleep(interval)
        interval *= backoff
    raise SAPCliError(f'Timeout waiting for task {task_id}')


# pylint: disable=too-many-arguments
def clone(connection, url, rid, vsid='6IT', start_dir='src/', vcs_token=None, error_exists=True,
          role='SOURCE', typ='GITHUB'):
    """Creates and clones the repository in the target systems"""

    config = {}

    if start_dir:
        config['VCS_TARGET_DIR'] = start_dir

    if vcs_token:
        config['CLIENT_VCS_AUTH_TOKEN'] = vcs_token

    repo = Repository(connection, rid)

    try:
        repo.create(url, vsid, config=config, role=role, typ=typ)
    except GCTSRepoAlreadyExistsError as ex:
        if error_exists:
            raise ex

        _mod_log().debug(ex)
        _mod_log().info(str(ex))

        repo.wipe_data()

    if not repo.is_cloned:
        repo.clone()
    else:
        _mod_log().info('Not cloning the repository "%s": already performed')

    return repo


def checkout(connection, branch, rid=None, repo=None):
    """Checks out the given branch in the given repository on the give system"""

    if repo is None:
        repo = Repository(connection, rid)

    return repo.checkout(branch)


def log(connection, rid=None, repo=None):
    """Returns log history of the given repository on the give system"""

    if repo is None:
        repo = Repository(connection, rid)

    return repo.log()


def pull(connection, rid=None, repo=None):
    """Pulls the given repository on the give system"""

    if repo is None:
        repo = Repository(connection, rid)

    return repo.pull()


def delete(connection, rid=None, repo=None):
    """Deletes the given repository on the give system"""

    if repo is None:
        repo = Repository(connection, rid)

    return repo.delete()


def get_user_credentials(connection):
    """Get Token for the currently logged in user"""

    response = connection.get_json('user')
    user_data = response.get('user', None)
    if user_data is None:
        raise SAPCliError('gCTS response does not contain \'user\'')

    config_data = user_data.get('config', None)
    if config_data is None:
        return []

    user_credentials = [cred for cred in config_data if cred['key'] == 'USER_AUTH_CRED_ENDPOINTS']
    return json.loads(user_credentials[0]['value'])


def set_user_api_token(connection, api_url, token):
    """Set Token for the currently logged in user"""

    body = {
        'endpoint': api_url,
        'user': '',
        'password': '',
        'token': token,
        'type': 'token'
    }

    connection.post_obj_as_json('user/credentials', body)


def delete_user_credentials(connection, api_url):
    """Delete Token for the currently logged in user"""

    body = {
        'endpoint': api_url,
        'user': '',
        'password': '',
        'token': '',
        'type': 'none'
    }

    connection.post_obj_as_json('user/credentials', body)


def get_system_config_property(connection, config_key):
    """Get configuration property value for given key"""

    response = connection.get_json(f'system/config/{config_key}')
    config_value = response.get('result')
    if config_value is None:
        raise SAPCliError("gCTS response does not contain 'result'")

    return config_value


def list_system_config(connection):
    """List system configuration"""

    response = connection.get_json('system')
    system = response.get('result')
    if system is None:
        raise SAPCliError("gCTS response does not contain 'result'")

    return system.get('config', [])


def set_system_config_property(connection, config_key, value):
    """Create or update the configuration property"""

    body = {
        'key': config_key,
        'value': value,
    }
    response = connection.post_obj_as_json('system/config', body).json()
    config_value = response.get('result')
    if config_value is None:
        raise SAPCliError("gCTS response does not contain 'result'")

    return config_value


def delete_system_config_property(connection, config_key):
    """Delete configuration property"""

    return connection.delete_json(f'system/config/{config_key}')

"""Offline test bootstrap. Discover with -t . so this runs before application imports."""
import os
import socket

# Do not read a developer's credentials/configuration when importing app.py in tests.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DECISIONS_ENABLED'] = '0'

# Tests replace HTTP boundaries explicitly. This guard prevents a missed mock from reaching a real service.
# Opt-in embedding integration tests may download model files.
if os.environ.get('RUN_RETRIEVAL_EVAL') != '1':
    def _offline_connect(*args, **kwargs):
        raise RuntimeError('Network disabled in unit tests; mock the boundary')

    # A suite-wide invariant must survive test fixtures calling mock.patch.stopall().
    socket.socket.connect = _offline_connect

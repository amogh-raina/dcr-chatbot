"""Offline test bootstrap. Discover with -t . so this runs before application imports."""
import os
from unittest.mock import patch

# Do not read a developer's credentials/configuration when importing app.py in tests.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DECISIONS_ENABLED'] = '0'

# Tests replace HTTP boundaries explicitly. This guard prevents a missed mock from reaching a real service.
# Opt-in embedding integration tests may download model files.
if os.environ.get('RUN_RETRIEVAL_EVAL') != '1':
    patch('socket.socket.connect', side_effect=RuntimeError('Network disabled in unit tests; mock the boundary')).start()

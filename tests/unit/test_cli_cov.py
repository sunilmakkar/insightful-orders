"""
Extra coverage for app/cli.py.

Focus:
- Ensures the seed_demo CLI command can be invoked successfully inside
  the Flask application context.
- Verifies that the command exits cleanly with code 0.
"""

from click.testing import CliRunner
from app.cli import seed_demo
from app import create_app

def test_cli_seed_demo_runs():
    app = create_app("testing")
    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(seed_demo, [])
        assert result.exit_code == 0

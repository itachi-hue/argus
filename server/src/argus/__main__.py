"""Allow running as: python -m argus

Commands:
  python -m argus          Start the MCP + HTTP server (default)
  python -m argus token    Print the auth token (and copy to clipboard)
"""

import sys


def cli():
    args = sys.argv[1:]

    if not args or args[0] not in ("token",):
        from argus.main import main

        main()
        return

    if args[0] == "token":
        from argus.config import settings
        from argus.main import _copy_to_clipboard

        print(settings.auth_token)
        if _copy_to_clipboard(settings.auth_token):
            print("(copied to clipboard)", file=sys.stderr)


cli()

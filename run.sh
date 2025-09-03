#!/bin/sh

echo python -m inbox_cleaner.cli auth --setup --web-server
echo python -m inbox_cleaner.cli retention --sync-db
echo python -m inbox_cleaner.cli auth
echo python -m inbox_cleaner.cli auth --setup
echo python -m inbox_cleaner.cli list-filters
echo python -m inbox_cleaner.cli mark-read
echo python -m inbox_cleaner.cli create-spam-filters
echo python -m inbox_cleaner.cli apply-filters

echo python usps_retention_manager.py --cleanup-live
echo python -m inbox_cleaner.cli retention

echo python -m inbox_cleaner.cli
echo pytest

exit 0

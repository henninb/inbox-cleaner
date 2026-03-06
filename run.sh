#!/bin/sh

echo cp config.yaml.example config.yaml
echo pip install -r requirements.txt
echo python -m inbox_cleaner.cli
echo python -m inbox_cleaner.cli create-spam-filters --create-filters
echo pytest
echo python -m inbox_cleaner.cli auth --setup --web-server
echo python -m inbox_cleaner.cli sync --with-progress
echo python -m inbox_cleaner.cli mark-read
echo python -m inbox_cleaner.cli retention
echo python -m inbox_cleaner.cli retention --cleanup
echo python -m inbox_cleaner.cli status
echo python -m inbox_cleaner.cli list-filters
echo python -m inbox_cleaner.cli apply-filters

echo python -m inbox_cleaner.cli create-spam-filters




echo  python -m inbox_cleaner.cli auth --logout
echo  python -m inbox_cleaner.cli auth --setup
echo  python -m inbox_cleaner.cli spam-cleanup --execute --limit 50
echo  python -m inbox_cleaner.cli retention --cleanup

exit 0

#!/bin/sh

echo python -m inbox_cleaner.cli
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

exit 0

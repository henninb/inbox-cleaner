#!/bin/sh

python -m inbox_cleaner.cli

echo python usps_retention_manager.py --cleanup-live

echo python unsubscribe_and_block.py --domain email.totaltools.com.au --execute
echo python unsubscribe_and_block.py --domain info.curaleaf.com --execute --force
echo python unsubscribe_and_block.py --domain t.timberland.com --execute
echo python unsubscribe_and_block.py --domain email.totaltools.com.au --execute
echo python unsubscribe_and_block.py --domain trulieve.com --execute
echo python -m inbox_cleaner.cli auth
echo python unsubscribe_and_block.py --all-domains --dry-run
echo python -m inbox_cleaner.cli
echo pytest

exit 0

#!/bin/sh

python -m inbox_cleaner.cli

echo python unsubscribe_and_block.py --domain email.totaltools.com.au --execute
echo python unsubscribe_and_block.py --domain info.curaleaf.com --execute --force
echo python unsubscribe_and_block.py --domain t.timberland.com --execute
echo python unsubscribe_and_block.py --domain email.totaltools.com.au --execute
echo python unsubscribe_and_block.py --domain trulieve.com --execute
echo python real_demo.py --auth
echo python -m inbox_cleaner.cli auth
echo python unsubscribe_and_block.py --all-domains --dry-run
echo python quick_cleanup.py --archive-old-promos --dry-run
echo python real_demo.py --stats
echo python -m inbox_cleaner.cli
echo python real_demo.py --extract 4225
echo python real_demo.py --extract 500
ehoc pytest
exit 0

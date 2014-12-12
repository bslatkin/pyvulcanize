#!/bin/bash

set -e

PYTHONPATH=../:$PYTHONPATH
python -m vulcanize -v ./example/index.html -o ./tests/test_output.html
diff ./tests/test_output.html ./tests/golden_output.html
echo "PASS"

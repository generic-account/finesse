# !/bin/bash

# Exit on the first failure
set -e

# Run the python test code, just list the files here
python3 backtrack_example.py
python3 test1.py
python3 test_var.py
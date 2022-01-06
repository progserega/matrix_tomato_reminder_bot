#!/bin/bash
python3 -m cProfile -s cumtime ./test.py > cProfile.log

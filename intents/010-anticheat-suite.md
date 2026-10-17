# 010 Anti-cheat suite
Status: done
Problem: an LLM optimising for a score will find shortcuts, some on purpose and many by accident. Each known shortcut should be a test that must stay caught.
Outcome: `tests/test_anticheat.py` runs a catalogue of cheating strategies through the real judge and asserts each is rejected, flagged as look-ahead, or neutralised. Covers: future shifts (literal and hidden in variables), reversed windows, full-sample ranking and z-scores, interpolation, reading files directly (including via getattr), hard-coded dates and tickers (memory leakage), custom classes that could smuggle code back to the judge, and leverage/universe abuse.
Done when: every case in the catalogue is caught, and adding a new cheat means adding one row to the test.
Notes: known gaps stay listed in docs/design.md (a strategy built to detect the truncation check; sampled dates).

"""Registry of baseline encode_fn's, by name.

Lets Test 4 (and any future cross-encoding comparison) loop over every
baseline uniformly instead of importing each module by hand. Add an entry
here each time a new baseline module gains an encode(spec) -> mapping.
"""

from baselines import jw, parity

BASELINES = {
    "jw": jw.encode,
    "parity": parity.encode,
}

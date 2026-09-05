# submissions/

Drop a submission folder here **when submitting by pull request**:

```
submissions/<your-name>/
  encode.py         # def encode(spec) -> mapping; optional order(), represent()
  submission.json   # {"name": ..., "label": ..., "sizes": ...}
  memory/           # OPTIONAL -- notes on what you tried
```

The manifest schema, the `encode(spec)` contract, and which challenge each
field selects are all documented in [`../inbox/README.md`](../inbox/README.md) --
this directory changes *where you put the folder*, nothing about what goes
in it.

## Why this exists separately from `inbox/`

`inbox/` is git-ignored: it's local working state for whoever runs
`scripts/process_inbox.py` by hand, plus the `_processed/` archive. Nothing
in it can be committed, so a pull request has nowhere to put a submission.
This directory is tracked, so a PR can add to it.

The two meet at registration time: when a submission PR is merged, the
post-merge workflow moves the folder into `inbox/`, runs the exact same
`scripts/process_inbox.py` pipeline every manually-handled submission has
gone through, and removes the folder from here once it's been consumed. So
the verification path is identical either way -- there is no separate,
weaker check for PR submissions.

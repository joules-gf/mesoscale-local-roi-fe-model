# Reference outputs

This folder is reserved for small, curated outputs that are useful to share with the repository.

Generated Abaqus results and routine simulation outputs should stay ignored under `simulation_outputs/`. Only move files here when they are intentionally selected as reference artifacts, examples, or documentation figures.

Good candidates:

- small PNGs used in the README or a repository guide;
- small CSVs that serve as reference curves or published comparison data;
- carefully documented example outputs that help a new user verify their setup.

Poor candidates:

- full Abaqus output folders;
- `.odb`, `.dat`, `.msg`, `.sta`, `.lck`, or other solver artifacts;
- routine regenerated plots from exploratory runs;
- large batch-study outputs that can be reproduced from tracked XML inputs.

If a file is added here, include enough provenance to answer:

1. which script generated it;
2. which input XML/CSV was used;
3. whether it is a manually curated figure or a reproducibility check artifact.

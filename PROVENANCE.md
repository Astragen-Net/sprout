# Provenance and scope

- **No code from any prior proprietary codebase is included.** The capture tool and the analysis pipeline were written for this project.
- The decoder uses **public pump.fun protocol facts**: the program ID, instruction discriminators, account layouts, and on-chain transactions. The public IDL is available at `github.com/pump-fun/pump-public-docs`; its JSON is not redistributed in this repository.
- **No secrets are included.** The capture tool reads `GRPC_URL` and `GRPC_TOKEN` from the environment. The repository contains no provider tokens, database passwords, or wallet keys.
- The fixture is one minute of **public on-chain events**, included only to exercise the pipeline. No copyright is claimed over the underlying data; it contains third-party token metadata and URIs that the project does not endorse.
- The exploratory dev-dump test was inspired by the public [`pumpfunbots-reverse`](https://github.com/zostaff/pumpfunbots-reverse) research; no code from that repository is included.
- This project is **not affiliated with pump.fun** and is not financial advice.
- If your employment or contract restricts code influenced by a proprietary codebase, obtain legal advice before publishing. This note records the technical provenance; it is not a legal opinion.

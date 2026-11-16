# How to work on Aegis

## Branches

This repository follows Gitflow. The full picture, for every repository in the family, is in [`docs/ROADMAP.md`](docs/ROADMAP.md).

- `main` holds released code only. Every commit on it is a tagged release.
- `develop` holds the next release. It always passes CI.
- Nobody pushes straight to either. Every change is a pull request.

## A normal change

```bash
git checkout develop && git pull
git checkout -b feature/short-name

# ... make the change ...

make check                      # lint, tests, the code scan and the security drill. The same things CI runs
git push -u origin feature/short-name
```

Open a pull request **into `develop`**. It needs the `ci` and `security` checks green and one approval. Changes to `config/policy.yaml`, `aegis/security/` or `.github/` need the owner's approval.

## A release

```bash
git checkout -b release/0.2.0 develop     # only fixes from here on
```

Open a pull request into `main`. After it merges: tag it (`v0.2.0`), then merge `main` back into `develop`.

## An urgent fix to what is live

Branch `hotfix/short-name` from `main`, open a pull request into `main`, tag the patch version, then merge `main` back into `develop`.

## What every change must keep true

1. Nothing in the outside world changes without a human go, tied to the exact plan.
2. Agents choose actions from `config/policy.yaml`. They never write their own commands.
3. The defender uses rules, never an AI model.
4. A new agent has a `PROMPT`, an `offline()` fallback and a test.
5. A new way to attack the system gets a line in `aegis/security/drill.py`.
6. No secrets, no personal voice recordings, no client data in this repository.

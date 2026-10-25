# Installing and publishing

## Install

`tos` is a console script, so every modern Python installer works.

### pipx — isolated CLI install

```console
$ pipx install "git+https://github.com/yorch/tos-toolkit"
$ tos --version
```

pipx puts `tos` in its own virtualenv and links only the executable onto your
`PATH`. That is the right default for a CLI you use across many projects: it
cannot conflict with a project's own dependencies.

```console
$ pipx upgrade tos-toolkit          # when a new release lands
$ pipx uninstall tos-toolkit
$ pipx run --spec "git+https://github.com/yorch/tos-toolkit" tos lint   # one-off
```

### uv — faster, same idea

```console
$ uv tool install "git+https://github.com/yorch/tos-toolkit"
$ uvx --from "git+https://github.com/yorch/tos-toolkit" tos --version   # ephemeral
$ uv tool upgrade tos-toolkit
```

`uvx` is the closest thing to "run it without installing it" and is handy in a
one-shot CI step.

### pip — into the current environment

```console
$ pip install "git+https://github.com/yorch/tos-toolkit"
```

Use this when the tool should be pinned alongside a project's other tooling.
`pip install -e /path/to/tos-toolkit` is the editable form, for working on the
toolkit itself.

### Once it is on PyPI

```console
$ pipx install tos-toolkit
$ uv tool install tos-toolkit
$ pip install tos-toolkit
```

### The optional grammar check

`tos syntax-check` needs a local thinkorswim install and a JDK. The `[parser]`
extra adds no Python dependencies — it exists so the requirement is visible:

```console
$ pipx install "tos-toolkit[parser]"
$ uv tool install "tos-toolkit[parser]"
```

Everything other than `syntax-check` works without thinkorswim.

---

## Publishing to PyPI

The name **`tos-toolkit` is unclaimed on PyPI**, so it is available.

Publishing uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/):
GitHub Actions mints a short-lived OIDC token and PyPI verifies the workflow.
No API token is stored in the repository, and there is nothing to leak or rotate.

### One-time setup (manual, on PyPI)

1. Sign in to PyPI and go to **Your projects → Publishing**.
2. Add a **pending publisher** (this works *before* the project exists):

   | Field | Value |
   | --- | --- |
   | PyPI project name | `tos-toolkit` |
   | Owner | `yorch` |
   | Repository | `tos-toolkit` |
   | Workflow name | `release.yml` |
   | Environment | `pypi` |

3. In the GitHub repo, create an environment named `pypi`
   (Settings → Environments). Adding required reviewers there means every publish
   waits for a human click — recommended.
4. Add a repository **variable** `PUBLISH_TO_PYPI` with the value `true`.
   Until it exists, the publish job is skipped, so a tag never fails on a
   half-configured publisher.

### Practice on TestPyPI first

Repeat the pending-publisher setup on [test.pypi.org](https://test.pypi.org) with:

| Field | Value |
| --- | --- |
| Workflow name | `release.yml` |
| Environment | `testpypi` |

Set `PUBLISH_TO_TESTPYPI=true` to enable it. TestPyPI is a separate index, so a
version published there is **not** consumed by `pip install`.

### Cutting a release

```console
$ git tag -a v0.2.0 -m "v0.2.0"
$ git push origin v0.2.0
```

The `Release` workflow then:

1. Verifies the tag matches `version` in `pyproject.toml` — a mismatch fails the
   build, so the wheel can never disagree with the tag.
2. Builds the sdist and wheel and runs `twine check`.
3. Creates the GitHub Release with both artifacts attached.
4. Publishes to TestPyPI and/or PyPI **only** when the corresponding variable is
   set.

### Manual fallback

If trusted publishing is not available, the same artifacts can be uploaded by
hand — note that PyPI does not allow replacing a version once uploaded, so a
mistake means burning the version number:

```console
$ python -m build
$ python -m twine check dist/*
$ python -m twine upload --repository testpypi dist/*   # rehearse
$ python -m twine upload dist/*                          # publish
```

### When publishing fails: `invalid-publisher`

This is the one failure you will hit, and it is almost always a form mismatch.
PyPI issues a valid token and then refuses it because no publisher matches the
claims GitHub sent. The claims are printed in the failed job log — copy them and
compare field by field:

```text
sub             repo:yorch@60499/tos-toolkit@1433433744:environment:pypi
repository      yorch/tos-toolkit
workflow_ref    yorch/tos-toolkit/.github/workflows/release.yml@refs/tags/v0.1.0
environment     pypi
```

The four fields that must match, in this order of how often they are wrong:

| PyPI field | Must be | Common mistake |
| --- | --- | --- |
| Environment name | `pypi` | left **blank** — the form says "optional", but the workflow sets `environment: pypi`, so blank can never match |
| Workflow name | `release.yml` | `.github/workflows/release.yml` (full path) or `release.yaml` |
| Repository name | `tos-toolkit` | the owner name, or a fork |
| PyPI project name | `tos-toolkit` | `tos_toolkit` |

Also confirm you added it on **pypi.org**, not test.pypi.org — they are separate
accounts and separate publishers.

**Nothing was uploaded when this fails**, so the version is still free. Fix the
form, then re-run only the failed jobs — no new tag needed, and the claims stay
identical:

```console
$ gh run rerun <run-id> --failed
```

### If the form keeps refusing

Publish once with an API token, which creates the project on PyPI; then attach a
*normal* trusted publisher to the now-existing project (no "pending" matching
involved):

```console
$ python -m build
$ python -m twine check dist/*
$ python -m twine upload dist/*        # PyPI token as password, user __token__
```

Then delete the token from your environment. From the next release onward the
workflow publishes by OIDC.

### Things that will bite you

- **The version must match the tag.** Enforced in CI.
- **PyPI versions are immutable.** `0.1.0` uploaded once can never be replaced;
  bump to `0.1.1`.
- **The project name is permanent.** `tos-toolkit` is a claim you keep. If it is
  ever abandoned, squatting risk is real.
- **Pre-1.0 rule churn.** A new lint rule can turn a consumer's green build red.
  The changelog says to pin; make that prominent when you announce.
- **Attribution.** The package name deliberately avoids the trademark; keep the
  non-affiliation note in the README.

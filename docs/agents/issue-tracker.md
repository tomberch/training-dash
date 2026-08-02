# Issue tracker: GitHub Issues

Issues and specs for this repo live in GitHub Issues at `tomberch/training-dash`.

## CLI

Use the `gh` CLI for all issue operations. The repo is inferred from the current working directory.

## Feature labels

Use `feature:<slug>` labels to group issues by feature (e.g. `feature:fitness-app`, `feature:user-settings`). When `/to-tickets` creates issues, include the feature label:

```bash
gh issue create --title "Title" --body "Body" --label "feature:fitness-app"
```

Filter issues by feature:

```bash
gh issue list --label "feature:fitness-app"
```

## Creating issues

```bash
gh issue create --title "Title" --body "Body"
```

Add labels with `--label`:

```bash
gh issue create --title "Title" --body "Body" --label "ready-for-agent"
```

## Fetching issues

```bash
gh issue view <number>
gh issue list --label "ready-for-agent"
```

## Blocking edges

GitHub Issues doesn't have native blocking links. Record blocking relationships in the issue body:

```
**Blocked by:** #12, #14
```

A ticket is unblocked when every issue it lists is closed.

## When a skill says "publish to the issue tracker"

Run `gh issue create` with the appropriate title, body, and labels.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number>` or `gh issue list` with filters.

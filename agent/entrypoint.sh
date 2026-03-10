#!/bin/bash
set -e

MERGE_OPTION="${MERGE_OPTION:-none}"

echo "=== Claude Agent Container Starting ==="
echo "Task ID: $TASK_ID"
echo "Task Title: $TASK_TITLE"
echo "Platform: $PLATFORM"
echo "Branch: $GIT_BRANCH"
echo "New Branch: $NEW_BRANCH"
echo "Merge Option: $MERGE_OPTION"

# Validate MERGE_OPTION
case "$MERGE_OPTION" in
    none|pull_request|auto_squash_merge) ;;
    *)
        echo "WARNING: Unrecognized MERGE_OPTION '$MERGE_OPTION', defaulting to 'none'"
        MERGE_OPTION="none"
        ;;
esac

# Verify ANTHROPIC_API_KEY is set for Claude CLI authentication
echo "=== Checking Claude API key ==="
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set. Cannot authenticate Claude CLI."
    exit 1
fi
echo "ANTHROPIC_API_KEY is set"

# Configure git (global defaults for clone, overridden locally after clone)
git config --global user.email "${GIT_USER_EMAIL:-claude@agent.ai}"
git config --global user.name "${GIT_USER_NAME:-Claude}"
git config --global init.defaultBranch main

# Clone the repo
echo "=== Cloning repository ==="
git clone --branch "$GIT_BRANCH" --single-branch "$GIT_REPO_URL" /workspace/repo
cd /workspace/repo

# Configure local git identity (container-isolated)
git config user.name "${GIT_USER_NAME:-Claude}"
git config user.email "${GIT_USER_EMAIL:-claude@agent.ai}"

# Create a new branch
echo "=== Creating branch $NEW_BRANCH ==="
git checkout -b "$NEW_BRANCH"

# Verify Claude CLI is available
echo "=== Verifying Claude CLI ==="
if ! claude --version > /dev/null 2>&1; then
    echo "ERROR: Claude CLI not available"
    exit 1
fi
echo "Claude CLI ready (using API key authentication)"

# The $TASK env var contains the pre-generated structured prompt from the backend.
# Fall back to $TASK_DESCRIPTION if $TASK is empty (prompt generation was skipped).
if [ -z "$TASK" ]; then
  echo "=== Warning: No pre-generated prompt, falling back to raw task description ==="
  TASK="$TASK_DESCRIPTION"
fi

# Run Claude — explicitly instruct it NOT to do any git merge/push/PR operations
echo "=== Running Claude Code agent ==="
AGENT_PROMPT="IMPORTANT CONSTRAINTS: You must NEVER run git merge, git push, git rebase, or create pull requests/merge requests. Do NOT merge branches. Do NOT push to any remote. Do NOT use gh, glab, or any CLI to create PRs. Your job is ONLY to: write code, run tests, and commit your changes to the current branch. All git push, merge, and PR operations are handled externally after you finish.

TASK:
$TASK"

claude --dangerously-skip-permissions --model "${MODEL:-claude-sonnet-4-6}" -p "$AGENT_PROMPT" 2>&1 || true

# Detect and run tests
echo "=== Checking for tests ==="
if [ -f "package.json" ] && grep -q '"test"' package.json; then
    echo "Running npm test..."
    npm test 2>&1 || echo "Tests failed (non-fatal)"
elif [ -f "pytest.ini" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo "Running pytest..."
    pip install -q pytest 2>/dev/null || true
    pytest 2>&1 || echo "Tests failed (non-fatal)"
elif [ -f "*.sln" ] || [ -f "*.csproj" ]; then
    echo "Running dotnet test..."
    dotnet test 2>&1 || echo "Tests failed (non-fatal)"
else
    echo "No test runner detected, skipping tests."
fi

# === Generate smart commit message using Claude CLI ===
echo "=== Generating commit message ==="

# Collect the diff: committed changes on branch + any uncommitted changes
BRANCH_DIFF=$(git diff "origin/$GIT_BRANCH...HEAD" 2>/dev/null || true)
UNSTAGED_DIFF=$(git diff 2>/dev/null || true)
STAGED_DIFF=$(git diff --cached 2>/dev/null || true)
FULL_DIFF="${BRANCH_DIFF}${UNSTAGED_DIFF:+
$UNSTAGED_DIFF}${STAGED_DIFF:+
$STAGED_DIFF}"

# If no diff available, fall back to commit log summaries
if [ -z "$FULL_DIFF" ]; then
    FULL_DIFF=$(git log --oneline "origin/$GIT_BRANCH..HEAD" 2>/dev/null || true)
    if [ -n "$FULL_DIFF" ]; then
        FULL_DIFF="Commits on branch (no raw diff available):
$FULL_DIFF"
    fi
fi

# Truncate very large diffs to avoid token limits
DIFF_LEN=${#FULL_DIFF}
if [ "$DIFF_LEN" -gt 10000 ]; then
    DIFF_HEAD="${FULL_DIFF:0:5000}"
    DIFF_TAIL="${FULL_DIFF: -5000}"
    FULL_DIFF="${DIFF_HEAD}

... [diff truncated: ${DIFF_LEN} chars total, showing first 5000 and last 5000] ...

${DIFF_TAIL}"
fi

# Default fallback values
COMMIT_TITLE="${TASK_TITLE:-feat: automated changes (task $TASK_ID)}"
COMMIT_BODY="${TASK_DESCRIPTION}"

# Only attempt generation if we have something to analyze
if [ -n "$FULL_DIFF" ]; then
    COMMIT_MSG_FILE=$(mktemp)
    DIFF_FILE=$(mktemp)
    printf '%s' "$FULL_DIFF" > "$DIFF_FILE"

    COMMIT_MSG_RAW=$(claude --dangerously-skip-permissions --model "${MODEL:-claude-sonnet-4-6}" -p "You are a commit message generator. Given the following git diff and task description, generate a professional commit message.

Rules:
- First line: conventional commit format (feat/fix/refactor/docs/test/chore), max 72 chars, summarizing the actual changes (not the task request)
- Leave a blank line after the title
- Body: describe all significant changes in bullet points grouped by area/file
- Be specific about what changed, not vague
- Do not include Co-Authored-By (that will be added separately)

Output format (exactly):
TITLE: <the commit title line>
BODY:
<the commit body>

Task description: $TASK_DESCRIPTION

Diff:
$(cat "$DIFF_FILE")" 2>&1) || true

    rm -f "$DIFF_FILE"

    # Parse the output to extract TITLE and BODY
    if [ -n "$COMMIT_MSG_RAW" ]; then
        PARSED_TITLE=$(echo "$COMMIT_MSG_RAW" | grep -m1 '^TITLE:' | sed 's/^TITLE:\s*//')
        PARSED_BODY=$(echo "$COMMIT_MSG_RAW" | sed -n '/^BODY:/,$ p' | tail -n +2)

        if [ -n "$PARSED_TITLE" ]; then
            COMMIT_TITLE="$PARSED_TITLE"
        fi
        if [ -n "$PARSED_BODY" ]; then
            COMMIT_BODY="$PARSED_BODY"
        fi
    fi

    rm -f "$COMMIT_MSG_FILE"
fi

# Ensure commit title never exceeds 72 characters
if [ ${#COMMIT_TITLE} -gt 72 ]; then
    COMMIT_TITLE="${COMMIT_TITLE:0:69}..."
fi

echo "Commit title: $COMMIT_TITLE"

# Stage and commit any uncommitted changes left by Claude
if [ -n "$(git status --porcelain)" ]; then
    echo "=== Committing uncommitted changes ==="
    git add -A
    # Use git commit -F to safely handle multiline messages with special characters
    printf '%s\n\n%s\n\nCo-Authored-By: Claude <noreply@anthropic.com>' "$COMMIT_TITLE" "$COMMIT_BODY" | git commit -F -
fi

# Check if there are any new commits on the working branch vs the target
COMMITS_AHEAD=$(git rev-list --count "origin/$GIT_BRANCH..HEAD" 2>/dev/null || echo "0")
if [ "$COMMITS_AHEAD" -eq 0 ]; then
    echo "=== Warning: No new commits compared to $GIT_BRANCH, nothing to push or merge ==="
    echo "=== Agent Complete ==="
    exit 0
fi

echo "=== $COMMITS_AHEAD new commit(s) on $NEW_BRANCH ==="

# Build PR body for use in pull request creation
PR_BODY=$(printf '%s\n\n## Task\n%s\n\n---\n_Generated by Claude Agent_' "$COMMIT_BODY" "$TASK_DESCRIPTION")

# Execute merge option — this is the single source of truth for push/merge/PR
if [ "$MERGE_OPTION" = "none" ]; then
    echo "=== Pushing branch $NEW_BRANCH to remote ==="
    if ! git push origin "$NEW_BRANCH"; then
        echo "MERGE_WARNING=Failed to push branch"
        echo "=== Warning: Could not push branch $NEW_BRANCH ==="
    else
        echo "=== Merge Option: None — branch pushed, no merge performed ==="
    fi

elif [ "$MERGE_OPTION" = "pull_request" ]; then
    echo "=== Pushing branch $NEW_BRANCH to remote ==="
    if ! git push origin "$NEW_BRANCH"; then
        echo "MERGE_WARNING=Failed to push branch"
        echo "=== Warning: Could not push branch $NEW_BRANCH ==="
    else
        echo "=== Creating Pull Request ==="
        PR_URL=""
        case "$PLATFORM" in
            github)
                REPO_PATH=$(echo "$REPO_URL" | sed -E 's|https?://[^/]+/||' | sed 's/\.git$//')
                PR_RESPONSE=$(curl -s -X POST \
                    -H "Authorization: token $PAT" \
                    -H "Accept: application/vnd.github.v3+json" \
                    "https://api.github.com/repos/$REPO_PATH/pulls" \
                    -d "$(jq -n \
                        --arg title "$COMMIT_TITLE" \
                        --arg body "$PR_BODY" \
                        --arg head "$NEW_BRANCH" \
                        --arg base "$GIT_BRANCH" \
                        '{title: $title, body: $body, head: $head, base: $base}')")
                PR_URL=$(echo "$PR_RESPONSE" | jq -r '.html_url // empty')
                ;;
            gitlab)
                HOST="${GIT_HOST:-gitlab.com}"
                REPO_PATH=$(echo "$REPO_URL" | sed -E 's|https?://[^/]+/||' | sed 's/\.git$//')
                ENCODED_PATH=$(echo "$REPO_PATH" | sed 's|/|%2F|g')
                PR_RESPONSE=$(curl -s -X POST \
                    -H "PRIVATE-TOKEN: $PAT" \
                    -H "Content-Type: application/json" \
                    "https://$HOST/api/v4/projects/$ENCODED_PATH/merge_requests" \
                    -d "$(jq -n \
                        --arg source "$NEW_BRANCH" \
                        --arg target "$GIT_BRANCH" \
                        --arg title "$COMMIT_TITLE" \
                        --arg desc "$PR_BODY" \
                        '{source_branch: $source, target_branch: $target, title: $title, description: $desc}')")
                PR_URL=$(echo "$PR_RESPONSE" | jq -r '.web_url // empty')
                ;;
            azure)
                REPO_PATH=$(echo "$REPO_URL" | sed -E 's|https?://[^/]+/||')
                ORG=$(echo "$REPO_PATH" | cut -d'/' -f1)
                PROJECT=$(echo "$REPO_PATH" | cut -d'/' -f2)
                REPO=$(echo "$REPO_PATH" | sed -E 's|.+/_git/||')
                PR_RESPONSE=$(curl -s -X POST \
                    -u ":$PAT" \
                    -H "Content-Type: application/json" \
                    "https://dev.azure.com/$ORG/$PROJECT/_apis/git/repositories/$REPO/pullrequests?api-version=7.0" \
                    -d "$(jq -n \
                        --arg title "$COMMIT_TITLE" \
                        --arg desc "$PR_BODY" \
                        --arg source "refs/heads/$NEW_BRANCH" \
                        --arg target "refs/heads/$GIT_BRANCH" \
                        '{sourceRefName: $source, targetRefName: $target, title: $title, description: $desc}')")
                PR_ID=$(echo "$PR_RESPONSE" | jq -r '.pullRequestId // empty')
                if [ -n "$PR_ID" ]; then
                    PR_URL="https://dev.azure.com/$ORG/$PROJECT/_git/$REPO/pullrequest/$PR_ID"
                fi
                ;;
        esac

        if [ -n "$PR_URL" ]; then
            echo "PR_URL=$PR_URL"
            echo "=== Pull Request Created: $PR_URL ==="
        else
            echo "MERGE_WARNING=Failed to create PR"
            echo "=== Warning: Could not create PR ==="
            echo "Response: $PR_RESPONSE"
        fi
    fi

elif [ "$MERGE_OPTION" = "auto_squash_merge" ]; then
    # Push the feature branch first so work is never lost
    echo "=== Pushing branch $NEW_BRANCH to remote ==="
    if ! git push origin "$NEW_BRANCH"; then
        echo "MERGE_WARNING=Failed to push branch"
        echo "=== Warning: Could not push branch $NEW_BRANCH ==="
    else
        echo "=== Auto Squash Merge: squashing $COMMITS_AHEAD commit(s) into $GIT_BRANCH ==="

        # Switch to base branch and pull latest
        git checkout "$GIT_BRANCH"
        echo "=== Pulling latest $GIT_BRANCH from remote ==="
        git pull origin "$GIT_BRANCH" || true

        # Squash merge (does not auto-commit)
        if git merge --squash "$NEW_BRANCH"; then
            printf '%s (squash merged)\n\n%s\n\nCo-Authored-By: Claude <noreply@anthropic.com>' "$COMMIT_TITLE" "$COMMIT_BODY" | git commit -F -

            echo "=== Pushing squash-merged changes to $GIT_BRANCH ==="
            if ! git push origin "$GIT_BRANCH"; then
                echo "MERGE_WARNING=Failed to push squash merge to $GIT_BRANCH"
                echo "=== Warning: Could not push squash-merged changes ==="
            else
                # Clean up remote feature branch
                git push origin --delete "$NEW_BRANCH" 2>/dev/null || true
                echo "=== Auto Squash Merge Complete ==="
            fi
        else
            # First attempt failed — pull latest and retry once
            echo "=== Merge failed, pulling latest $GIT_BRANCH and retrying ==="
            git merge --abort 2>/dev/null || true
            git pull origin "$GIT_BRANCH" || true

            if git merge --squash "$NEW_BRANCH"; then
                printf '%s (squash merged)\n\n%s\n\nCo-Authored-By: Claude <noreply@anthropic.com>' "$COMMIT_TITLE" "$COMMIT_BODY" | git commit -F -

                echo "=== Pushing squash-merged changes to $GIT_BRANCH ==="
                if ! git push origin "$GIT_BRANCH"; then
                    echo "MERGE_WARNING=Failed to push squash merge to $GIT_BRANCH"
                    echo "=== Warning: Could not push squash-merged changes ==="
                else
                    # Clean up remote feature branch
                    git push origin --delete "$NEW_BRANCH" 2>/dev/null || true
                    echo "=== Auto Squash Merge Complete (after retry) ==="
                fi
            else
                echo "=== Merge conflict detected after retry. Aborting merge. ==="
                git merge --abort 2>/dev/null || true
                git checkout "$NEW_BRANCH"
                echo "=== Feature branch $NEW_BRANCH already pushed. Please resolve conflicts manually. ==="
                echo "MERGE_WARNING=Failed to merge — resolve conflicts manually"
            fi
        fi
    fi
fi

echo "=== Agent Complete ==="

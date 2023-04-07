"""Create a new release tag with CalVer format."""
import datetime
import operator
import os
from pathlib import Path

import git
from packaging import version


def get_repo() -> git.Repo:
    """Get the git repo for the current project."""
    return git.Repo(Path(__file__).parent.parent)


def is_already_tagged(repo: git.Repo) -> bool:
    """Check if the current commit is already tagged."""
    return repo.git.tag(points_at="HEAD")


def should_skip_release(repo: git.Repo) -> bool:
    """Check if the commit message contains [skip release]."""
    commit_message = repo.head.commit.message.split("\n")[0]
    return "[skip release]" in commit_message


def get_new_version(repo: git.Repo) -> str:
    """Get the new version number."""
    latest_tag = max(repo.tags, key=operator.attrgetter("commit.committed_datetime"))
    last_version = version.parse(latest_tag.name)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    patch = (
        last_version.micro + 1
        if last_version.major == now.year and last_version.minor == now.month
        else 0
    )
    return f"{now.year}.{now.month}.{patch}"


def set_author(repo: git.Repo) -> None:
    """Set author information."""
    author_name = repo.head.commit.author.name
    author_email = repo.head.commit.author.email
    os.environ["GIT_AUTHOR_NAME"] = author_name
    os.environ["GIT_AUTHOR_EMAIL"] = author_email
    os.environ["GIT_COMMITTER_NAME"] = author_name
    os.environ["GIT_COMMITTER_EMAIL"] = author_email


def create_tag(repo: git.Repo, new_version: str) -> None:
    """Create a new tag."""
    set_author(repo)
    repo.create_tag(new_version, message=f"Release {new_version}")


def push_tag(repo: git.Repo, new_version: str) -> None:
    """Push the new tag to the remote repository."""
    origin = repo.remote("origin")
    origin.push(new_version)


def main() -> None:
    """Main entry point."""
    repo = get_repo()
    if is_already_tagged(repo):
        print("Current commit is already tagged!")
        return

    if should_skip_release(repo):
        print("Commit message is [skip release]!")
        return

    new_version = get_new_version(repo)
    create_tag(repo, new_version)
    push_tag(repo, new_version)
    print(f"::set-output name=version::{new_version}")  # Add this line
    print(f"Created new tag: {new_version}")


if __name__ == "__main__":
    main()

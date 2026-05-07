"""
Handlers for GitHub repository operations.

Exposes:
    push_to_github(repo_name, files_dict, token) -> dict
"""

import base64
from github import Github, GithubException

def push_to_github(repo_name: str, files_dict: dict, token: str) -> dict:
    """
    Create or update a GitHub repository and push files.

    Arguments:
        repo_name: Name of the repository (e.g., "my-project").
        files_dict: Dictionary mapping file paths to their *raw* (plain text) content.
                    Example: {"src/main.py": "print('hello')"}
        token: Personal access token with repo scope.

    Returns:
        dict with keys:
            - "success": bool
            - "message": str (human-readable outcome)
            - "repo_url": str (if successful)
    """
    try:
        g = Github(token)
        user = g.get_user()

        # Check if repo exists; create if not
        try:
            repo = user.get_repo(repo_name)
        except GithubException as e:
            if e.status == 404:
                repo = user.create_repo(repo_name, private=False, auto_init=False)
            else:
                raise

        # Process each file
        for file_path, content in files_dict.items():
            # Encode content to bytes for PyGithub (it expects string or bytes)
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content  # assume bytes

            try:
                # Try to get existing file to update it
                contents = repo.get_contents(file_path)
                repo.update_file(
                    path=file_path,
                    message=f"Update {file_path}",
                    content=content_bytes,
                    sha=contents.sha,
                )
            except GithubException as e:
                if e.status == 404:
                    # File does not exist -> create new
                    repo.create_file(
                        path=file_path,
                        message=f"Create {file_path}",
                        content=content_bytes,
                    )
                else:
                    raise

        return {
            "success": True,
            "message": f"Successfully pushed {len(files_dict)} file(s) to {repo_name}.",
            "repo_url": repo.html_url,
        }

    except GithubException as e:
        return {
            "success": False,
            "message": f"GitHub API error (status {e.status}): {e.data.get('message', str(e))}",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error: {str(e)}",
        }
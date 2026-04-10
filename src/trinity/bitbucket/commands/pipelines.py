"""Pipeline status command — fetch CI build results by branch or PR."""

from typing import Any, Dict, List, Optional

from ..api import BitbucketAPI


def get_pipeline_status(
    api: BitbucketAPI,
    workspace: str,
    repo: str,
    branch: Optional[str] = None,
    pr_id: Optional[int] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retrieve pipeline status for a branch or pull request.

    If *pr_id* is supplied the source branch is resolved automatically.
    Returns a list of pipeline dicts with state, steps, and optional log tails.
    """
    if pr_id is not None:
        pr = api.get_pull_request(workspace, repo, pr_id)
        branch = pr["source"]["branch"]["name"]

    response = api.list_pipelines(workspace, repo, branch=branch, limit=limit)
    raw_pipelines = response.get("values", [])

    pipelines: List[Dict[str, Any]] = []
    for pipeline in raw_pipelines:
        pipeline_uuid = pipeline["uuid"]
        raw_steps = api.get_pipeline_steps(workspace, repo, pipeline_uuid)

        steps: List[Dict[str, Any]] = []
        for step in raw_steps:
            step_state = step.get("state", {})
            step_result_name = step_state.get("result", {}).get("name")

            step_entry: Dict[str, Any] = {
                "name": step.get("name"),
                "state": step_state.get("name"),
                "result": step_result_name,
                "duration_in_seconds": step.get("duration_in_seconds"),
            }

            if step_result_name == "FAILED":
                step_uuid = step["uuid"]
                log_text = api.get_step_log(workspace, repo, pipeline_uuid, step_uuid)
                log_lines = log_text.splitlines()
                step_entry["log_tail"] = "\n".join(log_lines[-50:])

            steps.append(step_entry)

        pipeline_state = pipeline.get("state", {})
        pipelines.append({
            "uuid": pipeline["uuid"],
            "build_number": pipeline["build_number"],
            "state": pipeline_state.get("name"),
            "result": pipeline_state.get("result", {}).get("name"),
            "branch": (
                pipeline.get("target", {}).get("ref_name")
                or pipeline.get("target", {}).get("source")
            ),
            "created_on": pipeline.get("created_on"),
            "duration_in_seconds": pipeline.get("duration_in_seconds"),
            "steps": steps,
        })

    return pipelines

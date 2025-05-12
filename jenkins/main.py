import os
import jenkins
import requests
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, Dict
from mcp.server.fastmcp import Context, FastMCP
from requests.packages.urllib3.exceptions import InsecureRequestWarning

@dataclass
class JenkinsContext:
    client: jenkins.Jenkins

@asynccontextmanager
async def jenkins_lifespan(server: FastMCP) -> AsyncIterator[JenkinsContext]:
    """Manage application lifecycle with type-safe context"""
    # Jenkins server details
    import dotenv

    dotenv.load_dotenv()

    jenkins_url = os.environ["JENKINS_URL"]
    username = os.environ["JENKINS_USERNAME"]
    use_token = os.environ["JENKINS_USE_API_TOKEN"]

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Connect to Jenkins with the custom session
    server = jenkins.Jenkins(
        url=jenkins_url,
        username=username,
        password=use_token,
    )

    server._session.verify = False

    yield JenkinsContext(client=server)


# Pass jenkins_lifespan to server
mcp = FastMCP("Jenkins MCP", lifespan=jenkins_lifespan)


@mcp.tool(
    name='get_job_info', 
    description="The tools used to get the job details information")
def get_job_info(ctx: Context, job_name: str) -> Dict:
    """get the job info"""
    client = ctx.request_context.lifespan_context.client

    job_info = client.get_job_info(job_name, fetch_all_builds=True)
    return job_info


@mcp.tool(
        name='get_job_result',
        description="The tools used to get the result of the job w/o the build number, will get the latest build by default")
def get_job_result(ctx: Context, job_name: str, build_num: Optional[int]) -> Dict:
    """Get the job result

    Args:
        job_name: Name of the job
        build_num: Build number to check, defaults to latest

    Returns:
        Build information dictionary
    """
    client = ctx.request_context.lifespan_context.client

    if build_num is None:
        build_num = client.get_job_info(job_name)["lastBuild"]["number"]

    report = client.get_build_test_report(job_name, build_num)
    return report


@mcp.tool(name='trigger_build',
          description='the tools used to trigger the jenkins build with parameters')
def trigger_build(
        ctx: Context, job_name: str, parameters: Dict = None) -> Dict:
    """Trigger a build

    Args:
        job_name: Name of the job
        parameters: The parameters dict used for the jobs

    Returns:
        Build information dictionary
    """
    if not isinstance(job_name, str):
        raise ValueError(f"job_name must be a string, got {type(job_name)}")
    if parameters is not None and not isinstance(parameters, dict):
        raise ValueError(
            f"parameters must be a dictionary or None, got {type(parameters)}"
        )

    client = ctx.request_context.lifespan_context.client

    # First verify the job exists
    try:
        if not client.job_exists(job_name):
            raise ValueError(f"Job {job_name} not found")
    except Exception as e:
        raise ValueError(f"Error checking job {job_name}: {str(e)}")

    if parameters is None:
        last_build_num = client.get_job_info(job_name)["lastBuild"]["number"]
        build_info = client.get_build_info(job_name, last_build_num)
        for i in build_info['actions']:
            if i['_class'] == 'hudson.model.ParametersAction':
                parameters = parse_parameters(i['parameters'])
                # parameters = i['parameters']
                break

    queueid = client.build_job(job_name, parameters)
    rst = client.get_queue_item(queueid)

    return rst


def parse_parameters(params: list) -> dict:
    result = {}
    for i in params:
        result[i['name']] = i['value']
    return result


if __name__ == "__main__":
    mcp.run(transport='sse')

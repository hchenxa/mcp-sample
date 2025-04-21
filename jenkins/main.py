import os
import jenkins
import requests
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, List
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


@mcp.tool()
def list_jobs(ctx: Context) -> List[str]:
    """List all Jenkins jobs"""
    client = ctx.request_context.lifespan_context.client
    return client.get_all_jobs()

@mcp.tool()
def get_current_user(ctx: Context) -> str:
    """Get the current users"""
    client = ctx.request_context.lifespan_context.client
    return client.get_whoami()

if __name__ == "__main__":
    mcp.run()
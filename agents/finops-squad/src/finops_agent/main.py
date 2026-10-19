"""finops-squad hosted agent. One codebase; AGENT_ROLE selects the role, tools and skills."""
import asyncio
import io
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from agent_framework import Agent, SkillsProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

from roles import ROLES
from tools import ANALYSER_TOOLS, COMMON_TOOLS, DISCOVERY_TOOLS, IMPLEMENTER_TOOLS, VISUALIZER_TOOLS

load_dotenv()
logger = logging.getLogger(__name__)
SKILLS_DIR = Path(tempfile.gettempdir()) / "downloaded_skills"
TOOLS = {"discovery": DISCOVERY_TOOLS, "analyser": ANALYSER_TOOLS, "visualizer": VISUALIZER_TOOLS, "implementer": IMPLEMENTER_TOOLS}


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "").strip()
    return default if not v or v.startswith(("${", "{{")) else v


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for m in zf.infolist():
        p = (root / m.filename).resolve()
        if root != p and root not in p.parents:
            raise RuntimeError(f"unsafe path in skill archive: {m.filename}")
    zf.extractall(dest)


async def _bootstrap_skills(endpoint: str, names: list[str]) -> None:
    if SKILLS_DIR.exists():
        shutil.rmtree(SKILLS_DIR)
    SKILLS_DIR.mkdir(parents=True)
    async with DefaultAzureCredential() as cred, AIProjectClient(endpoint=endpoint, credential=cred, allow_preview=True) as project:
        for name in names:
            stream = await project.beta.skills.download(name)
            data = b"".join([c async for c in stream])
            d = SKILLS_DIR / name
            d.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                _safe_extract(zf, d)
            if not (d / "SKILL.md").is_file():
                raise RuntimeError(f"skill '{name}' has no SKILL.md at its root")


async def main() -> None:
    role = _env("AGENT_ROLE", "discovery")
    spec = ROLES[role]
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    names = [n.strip() for n in _env("SKILL_NAMES", spec["skills"]).split(",") if n.strip()]

    providers = []
    if names:
        await asyncio.wait_for(_bootstrap_skills(endpoint, names), timeout=90)
        # Skills are read-only instructions and there are no scripts, so no approval gate is needed.
        providers.append(
            SkillsProvider.from_paths(
                skill_paths=str(SKILLS_DIR),
                disable_load_skill_approval=True,
                disable_read_skill_resource_approval=True,
            )
        )

    async with DefaultAzureCredential() as cred:
        client = FoundryChatClient(project_endpoint=endpoint, model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"], credential=cred)
        agent = Agent(
            client=client,
            name=f"finops-{role}",
            instructions=spec["instructions"],
            tools=TOOLS.get(role, COMMON_TOOLS),
            context_providers=providers,
            default_options={"store": False},
        )
        await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())

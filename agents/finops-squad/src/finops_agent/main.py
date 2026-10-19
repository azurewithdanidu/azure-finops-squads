"""finops-squad hosted agent. One codebase; AGENT_ROLE selects the role, tools and skills."""
import asyncio
import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, SkillsProvider, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

from roles import ROLES
from tools import ANALYSER_TOOLS, COMMON_TOOLS, DISCOVERY_TOOLS, IMPLEMENTER_TOOLS, ORCHESTRATOR_TOOLS, VISUALIZER_TOOLS

load_dotenv()
logger = logging.getLogger(__name__)
SKILLS_DIR = Path(tempfile.gettempdir()) / "downloaded_skills"
TOOLS = {"discovery": DISCOVERY_TOOLS, "analyser": ANALYSER_TOOLS, "visualizer": VISUALIZER_TOOLS, "implementer": IMPLEMENTER_TOOLS, "orchestrator": ORCHESTRATOR_TOOLS}


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
            data = None
            for attempt in range(3):
                try:
                    stream = await project.beta.skills.download(name)
                    data = b"".join([c async for c in stream])
                    break
                except Exception as exc:  # transient upstream errors; skip the skill rather than crash
                    print(f"skill '{name}' download attempt {attempt + 1} failed: {exc}", flush=True)
                    await asyncio.sleep(2 * (attempt + 1))
            if data is None:
                continue
            d = SKILLS_DIR / name
            d.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                _safe_extract(zf, d)
            if not (d / "SKILL.md").is_file():
                raise RuntimeError(f"skill '{name}' has no SKILL.md at its root")


def _provider_for(skill_names: list[str], role: str) -> SkillsProvider | None:
    """Build a skills provider exposing only this role's skills from the shared download."""
    d = SKILLS_DIR.parent / "role_skills" / role
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    found = 0
    for n in skill_names:
        if (SKILLS_DIR / n).is_dir():
            shutil.copytree(SKILLS_DIR / n, d / n)
            found += 1
    if not found:
        return None
    # Skills are read-only instructions and there are no scripts, so no approval gate is needed.
    return SkillsProvider.from_paths(
        skill_paths=str(d),
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
    )


def _split(csv: str) -> list[str]:
    return [n.strip() for n in csv.split(",") if n.strip()]


def make_specialist_tools(build) -> list:
    discovery, analyser, visualizer, implementer = (build(r) for r in ("discovery", "analyser", "visualizer", "implementer"))

    @tool
    async def draft_pull_request(
        task: Annotated[str, "Subscription id, run id and the approved finding ids to draft PRs for"],
        user_approval: Annotated[str, "The user's exact words approving these specific findings in this conversation"],
    ) -> str:
        """Ask the Implementer to draft Bicep changes and PR bodies (stored in blob; nothing is applied). Requires explicit user approval."""
        if len(user_approval.strip()) < 3:
            return json.dumps({"error": True, "body": "Explicit user approval is required. Ask the user which findings to approve."})
        return (await implementer.run(task)).text

    return [
        discovery.as_tool(name="run_discovery", description="Inventory, spend and Advisor discovery. Give subscription id and run id; it saves inventory.json, spend.json, advisor.json.", arg_name="task"),
        analyser.as_tool(name="run_analyser", description="Analyse one mode (waste, rightsizing, tagging, commitment, anomaly, verify). Give mode, subscription id and run id; it saves findings/<mode>.json. Call several in parallel for different modes.", arg_name="task"),
        visualizer.as_tool(name="run_visualizer", description="Build savings ledger and KPI reports for a run. Give subscription id and run id.", arg_name="task"),
        draft_pull_request,
    ]


async def main() -> None:
    role = _env("AGENT_ROLE", "discovery")
    spec = ROLES[role]
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    names = _split(_env("SKILL_NAMES", spec["skills"]))

    # The orchestrator embeds the specialists in-process (Foundry gives callee agents no trusted
    # user identity when the caller is a managed identity), so it needs their skills too.
    specialists = ["discovery", "analyser", "visualizer", "implementer"] if role == "orchestrator" else []
    all_names = list(dict.fromkeys(names + [s for r in specialists for s in _split(ROLES[r]["skills"])]))
    if all_names:
        await asyncio.wait_for(_bootstrap_skills(endpoint, all_names), timeout=150)

    async with DefaultAzureCredential() as cred:
        client = FoundryChatClient(project_endpoint=endpoint, model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"], credential=cred)

        def build(r: str) -> Agent:
            p = _provider_for(_split(ROLES[r]["skills"]), r) if r != role else _provider_for(names, r)
            return Agent(
                client=client,
                name=f"finops-{r}",
                instructions=ROLES[r]["instructions"],
                tools=TOOLS.get(r, COMMON_TOOLS),
                context_providers=[p] if p else [],
                default_options={"store": False},
            )

        tools = list(TOOLS.get(role, COMMON_TOOLS))
        if role == "orchestrator":
            tools += make_specialist_tools(build)
        agent = Agent(
            client=client,
            name=f"finops-{role}",
            instructions=spec["instructions"],
            tools=tools,
            context_providers=[p] if (p := _provider_for(names, role)) else [],
            default_options={"store": False},
        )
        await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())

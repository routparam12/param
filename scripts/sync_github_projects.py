#!/usr/bin/env python3
"""Synchronize new public GitHub repositories into the static portfolio."""
from __future__ import annotations
import base64, html, json, os, re, subprocess, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH, OUTPUT_PATH = ROOT / "data/portfolio-sync.json", ROOT / "data/projects.generated.json"
PROJECT_PAGES = (ROOT / "projects.html", ROOT / "index.html")
START_MARKER, END_MARKER = "<!-- GENERATED_GITHUB_PROJECTS_START -->", "<!-- GENERATED_GITHUB_PROJECTS_END -->"

def load(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))
def dump(path: Path, value: dict[str, Any]) -> None: path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json", "User-Agent":"param-portfolio-sync/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response: return json.loads(response.read().decode("utf-8"))
def clean(value: Any, length: int) -> str: return re.sub(r"\s+", " ", str(value or "")).strip()[:length]

def fallback(repo: dict[str, Any], readme: str) -> dict[str, Any]:
    description = clean(repo.get("description"), 420) or next((clean(line.strip("# \t"), 420) for line in readme.splitlines() if line.strip()), "A public GitHub project.")
    topics = [clean(x, 32) for x in repo.get("topics", [])][:8]
    return {"name":clean(repo["name"],80), "tagline":description[:140], "description":description, "category":"Project", "technologies":topics or ([repo["language"]] if repo.get("language") else []), "highlights":[]}

def validate(value: Any, repo: dict[str, Any], readme: str) -> dict[str, Any]:
    base = fallback(repo, readme)
    if not isinstance(value, dict): return base
    technologies, highlights = value.get("technologies", base["technologies"]), value.get("highlights", [])
    return {"name":clean(value.get("name") or base["name"],80), "tagline":clean(value.get("tagline") or base["tagline"],160), "description":clean(value.get("description") or base["description"],500), "category":clean(value.get("category") or "Project",50), "technologies":[clean(x,32) for x in technologies if clean(x,32)][:8] if isinstance(technologies,list) else base["technologies"], "highlights":[clean(x,140) for x in highlights if clean(x,140)][:3] if isinstance(highlights,list) else []}

def extract_json(response: str) -> dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.S | re.I)
    candidate = match.group(1) if match else response[response.find("{"):response.rfind("}")+1]
    return json.loads(candidate)

def copilot_summary(readme: str, config: dict[str, Any]) -> dict[str, Any]:
    temporary = ROOT / ".portfolio-sync-readme.md"
    temporary.write_text(readme[:int(config["max_readme_characters"])], encoding="utf-8")
    prompt = "Read .portfolio-sync-readme.md. Return ONLY JSON: {name, tagline, description, category, technologies, highlights}. Use only README facts. Do not invent metrics, impact, or technologies. Tagline <=140 characters; description <=500; technologies <=8; highlights <=3."
    command = ["copilot", "-p", prompt, "-s", "--no-ask-user", "--allow-tool=shell(cat:*)"]
    if config.get("copilot_model") not in (None, "", "auto"): command.extend(["--model", config["copilot_model"]])
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180, check=True)
        return extract_json(result.stdout)
    finally: temporary.unlink(missing_ok=True)

def api_summary(readme: str, config: dict[str, Any]) -> dict[str, Any]:
    settings, key = config["api_provider"], os.environ.get(config["api_provider"]["api_key_env"])
    if not key: raise RuntimeError(f"Missing {settings['api_key_env']} for summary_provider=api")
    schema = {"type":"object", "additionalProperties":False, "properties":{key:{"type":"string"} for key in ("name","tagline","description","category")}|{"technologies":{"type":"array","items":{"type":"string"}},"highlights":{"type":"array","items":{"type":"string"}}}, "required":["name","tagline","description","category","technologies","highlights"]}
    body = json.dumps({"model":settings["model"], "messages":[{"role":"user","content":"Summarize only supported README facts; do not invent metrics, impact, or technologies.\n\n"+readme[:int(config["max_readme_characters"])]}], "response_format":{"type":"json_schema","json_schema":{"name":"project", "strict":True, "schema":schema}}}).encode()
    request = urllib.request.Request(settings["base_url"].rstrip("/")+"/chat/completions", data=body, headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response: return json.loads(json.loads(response.read().decode())["choices"][0]["message"]["content"])

def summarize(repo: dict[str, Any], readme: str, config: dict[str, Any]) -> dict[str, Any]:
    try: return validate(copilot_summary(readme,config) if config.get("summary_provider")=="copilot" else api_summary(readme,config),repo,readme)
    except Exception as error:
        print(f"Using metadata fallback for {repo['full_name']}: {error}", file=sys.stderr); return fallback(repo,readme)

def render(projects: list[dict[str, Any]]) -> str:
    if not projects: return '<p class="generated-projects-empty">New public projects will appear here automatically.</p>'
    cards=[]
    for index, project in enumerate(projects, 1):
        highlights="".join(f"<li>{html.escape(x)}</li>" for x in project["highlights"])
        cards.append(f'''<article class="generated-project-card">
  <p class="generated-project-index">{index:02d} / {html.escape(project["category"])}</p><h3>{html.escape(project["name"])}</h3>
  <p class="generated-project-tagline">{html.escape(project["tagline"])}</p><p>{html.escape(project["description"])}</p>
  {f"<ul>{highlights}</ul>" if highlights else ""}
  <p class="generated-project-tech">{html.escape(" · ".join(x.upper() for x in project["technologies"]) or "GITHUB PROJECT")}</p>
  <a class="project-link" href="{html.escape(project["url"], quote=True)}" target="_blank" rel="noreferrer">Open project ↗</a>
</article>''')
    return "\n".join(cards)

def main() -> None:
    config, cache = load(CONFIG_PATH), None
    cache = config.setdefault("repository_cache", {})
    cutoff = datetime.fromisoformat(config["activation_cutoff"].replace("Z","+00:00"))
    projects=[]
    repos=get_json(f"https://api.github.com/users/{config['github_owner']}/repos?type=owner&sort=updated&direction=desc&per_page=100")
    for repo in repos:
        created=datetime.fromisoformat(repo["created_at"].replace("Z","+00:00"))
        if repo.get("private") or repo.get("fork") or repo.get("archived") or created<=cutoff or config["hidden_topic"] in repo.get("topics",[]): continue
        try: readme_data=get_json(f"https://api.github.com/repos/{repo['full_name']}/readme"); readme=base64.b64decode(readme_data.get("content", "")).decode("utf-8",errors="replace"); sha=readme_data.get("sha", "")
        except urllib.error.HTTPError as error:
            if error.code != 404: raise
            readme, sha = "", ""
        cached=cache.get(repo["full_name"],{})
        summary=cached["summary"] if cached.get("readme_sha")==sha and cached.get("summary") else summarize(repo,readme,config)
        cache[repo["full_name"]]={"readme_sha":sha,"summary":summary}
        projects.append({**summary,"url":repo["html_url"],"created_at":repo["created_at"],"updated_at":repo["updated_at"]})
    projects.sort(key=lambda project:project["created_at"],reverse=True)
    dump(OUTPUT_PATH,{"generated_at":datetime.now(timezone.utc).isoformat(),"projects":projects}); dump(CONFIG_PATH,config)
    replacement=START_MARKER+"\n"+render(projects)+"\n"+END_MARKER
    for project_page in PROJECT_PAGES:
        page=project_page.read_text(encoding="utf-8")
        if START_MARKER not in page or END_MARKER not in page: raise RuntimeError(f"Generated-project markers are missing from {project_page.name}")
        project_page.write_text(re.sub(re.escape(START_MARKER)+r".*?"+re.escape(END_MARKER),replacement,page,flags=re.S),encoding="utf-8")
    print(f"Generated {len(projects)} project card(s).")
if __name__ == "__main__": main()

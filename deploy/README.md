# Deployment Files

This folder contains all deployment-related configurations for Cloud Run.

## Structure

```
deploy/
├── docker/           # Dockerfiles
├── cloudbuild/       # Cloud Build configurations
├── scripts/          # Deployment scripts
└── procfiles/        # Procfiles for AgentBeats controller
```

## Services

| Service | Dockerfile | Deploy Script |
|---------|------------|---------------|
| Green Agent (production) | `docker/Dockerfile.green-agent` | `scripts/green-agent.sh` |
| Green Agent (AgentBeats) | `docker/Dockerfile.green-agent-agentbeats` | `scripts/green-agent-agentbeats.sh` |
| White Agent (production) | `docker/Dockerfile.white-agent` | `scripts/white-agent.sh` |
| White Agent (AgentBeats) | `docker/Dockerfile.white-agent-agentbeats` | `scripts/white-agent-agentbeats.sh` |
| WebUI (Next.js) | `docker/Dockerfile.webui-nextjs` | `scripts/webui-nextjs.sh` |

## Usage

Deploy from the repository root:

```bash
# Green Agent (production)
bash deploy/scripts/green-agent.sh

# Green Agent (AgentBeats mode)
bash deploy/scripts/green-agent-agentbeats.sh

# White Agent (production)
bash deploy/scripts/white-agent.sh

# White Agent (AgentBeats mode)
bash deploy/scripts/white-agent-agentbeats.sh

# WebUI
bash deploy/scripts/webui-nextjs.sh
```

## Notes

- All scripts must be run from the repository root (not from deploy/)
- Scripts require `gcloud` CLI configured with appropriate project
- Environment variables should be set in `.env` file at repository root

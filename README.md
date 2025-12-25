# AI-Powered Development Template

A project template with integrated AI Developer Workflows (ADW) for automated issue processing, planning, and implementation using Claude Code CLI.

## What is This?

This template provides a complete scaffolding for projects that leverage AI-powered development workflows. It includes:

- **AI Developer Workflows (ADW)** - Automated GitHub issue processing, planning, and implementation
- **Flexible application structure** - Supports CLI, web apps, APIs, or any project type
- **Development scripts** - Quick start, stop, and utility scripts
- **Claude Code integration** - Pre-configured hooks and permissions
- **Specification system** - Structured feature specs that guide AI implementation

## Features

- Automated GitHub issue classification and processing
- AI-generated implementation plans from specifications
- Continuous monitoring via cron or webhook triggers
- Structured logging and agent execution tracking
- Claude Code CLI integration with custom hooks
- Flexible project structure for any application type

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- [GitHub CLI (`gh`)](https://cli.github.com/)
- [uv](https://docs.astral.sh/uv/) - Python package manager
- Anthropic API key
- (Optional) GitHub Personal Access Token

## Quick Start

### 1. Clone and Setup

```bash
# Clone this template (or use it as a GitHub template)
git clone <your-repo-url>
cd <your-project>

# Copy and configure environment variables
cp .env.sample .env
# Edit .env and add your API keys
```

### 2. Configure for Your Project

```bash
# Set required environment variables
export GITHUB_REPO_URL="https://github.com/owner/repository"
export ANTHROPIC_API_KEY="sk-ant-xxxx..."
export CLAUDE_CODE_PATH="claude"  # or full path from 'which claude'
```

### 3. Initialize Your Application

The `app/` directory is where your application code lives. See `app/README.md` for structure examples:

- Web application (frontend + backend)
- CLI tool
- API service
- Monorepo
- Or any other structure

**Replace `app/README.md` with your actual application code.**

### 4. Start Development

```bash
# Customize scripts/start.sh for your app, then:
./scripts/start.sh

# Stop services:
./scripts/stop_apps.sh
```

## AI Developer Workflows (ADW)

The `adws/` directory contains the core AI development automation system.

### Process a Single Issue

```bash
cd adws/
uv run adw_plan_build.py <issue-number>
```

This will:
1. Fetch the GitHub issue
2. Classify it (/feature, /bug, or /chore)
3. Generate an implementation plan
4. Implement the solution
5. Create commits and a pull request

### Continuous Monitoring

```bash
# Poll GitHub every 20 seconds for new issues or "adw" comments
uv run trigger_cron.py
```

### Webhook Server

```bash
# Start webhook server for instant GitHub event processing
uv run trigger_webhook.py
```

See `adws/README.md` for detailed documentation.

## Project Structure

```
.
├── app/                    # Your application code (customize this!)
│   └── README.md           # Application structure guide
│
├── adws/                   # AI Developer Workflows (core system)
│   ├── agent.py            # Claude Code integration
│   ├── github.py           # GitHub API operations
│   ├── adw_plan_build.py   # Main workflow orchestration
│   ├── trigger_cron.py     # Continuous monitoring
│   ├── trigger_webhook.py  # Webhook server
│   └── README.md           # Full ADW documentation
│
├── scripts/                # Utility scripts
│   ├── start.sh            # Start application (customize!)
│   ├── stop_apps.sh        # Stop services
│   └── ...                 # ADW helper scripts
│
├── specs/                  # Feature specifications
│   └── example-feature-spec.md  # Template for specs
│
├── ai_docs/                # AI/LLM documentation and references
│
├── .claude/                # Claude Code configuration
│   ├── settings.json       # Permissions and hooks
│   ├── hooks/              # Custom hooks
│   └── commands/           # Custom commands
│
├── .env.sample             # Environment variables template
└── README.md               # This file
```

## Customization Guide

### 1. Application Structure

Edit `app/` to match your project:

```bash
# Remove the placeholder
rm app/README.md

# Initialize your project
cd app/
# ... create your project structure
```

### 2. Start Script

Edit `scripts/start.sh` to start your application:

```bash
# Uncomment and modify the example in start.sh
# Add commands to start your specific application
```

### 3. Environment Variables

Add project-specific environment variables to `.env.sample` and `.env`.

### 4. Specifications

Create feature specs in `specs/` following the template in `specs/example-feature-spec.md`.

### 5. Claude Code Permissions

Edit `.claude/settings.json` to add any project-specific permissions or hooks.

## Development Workflow

### With ADW (Recommended)

1. Create a GitHub issue describing the feature or bug
2. ADW automatically (or manually via `uv run adw_plan_build.py <issue>`) will:
   - Generate a specification in `specs/`
   - Create an implementation plan
   - Implement the changes
   - Create a pull request
3. Review and merge the PR

### Manual Development

1. Create a spec in `specs/`
2. Use Claude Code to implement: `claude --spec specs/your-spec.md`
3. Commit and push changes

## Environment Variables

Configure these in `.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-xxxx...          # Your Anthropic API key
GITHUB_REPO_URL=https://github.com/...    # Your repository URL

# Optional
GITHUB_PAT=ghp_xxxx...                    # GitHub token (if not using 'gh auth')
CLAUDE_CODE_PATH=claude                   # Path to Claude CLI
E2B_API_KEY=...                           # For cloud sandboxes
CLOUDFLARED_TUNNEL_TOKEN=...              # For webhook exposure
```

See `.env.sample` for full list.

## Scripts Reference

- `./scripts/start.sh` - Start your application (customize!)
- `./scripts/stop_apps.sh` - Stop all services
- `./scripts/expose_webhook.sh` - Expose webhook via cloudflared
- `./scripts/kill_trigger_webhook.sh` - Stop webhook server
- `./scripts/clear_issue_comments.sh` - Clear ADW comments from issues
- `./scripts/delete_pr.sh` - Delete pull requests

## ADW Outputs

ADW creates structured outputs:

```
agents/
└── <adw-id>/              # Unique 8-char ID per workflow
    ├── sdlc_planner/
    │   └── raw_output.jsonl
    └── sdlc_implementor/
        └── raw_output.jsonl

specs/
└── <feature-name>-plan.md  # Generated implementation plans
```

## Tips

1. **Start Small**: Test ADW with a simple issue first
2. **Review Plans**: Check generated specs before implementation
3. **Branch Protection**: Set up branch protection rules for ADW PRs
4. **Monitor Costs**: Watch API usage in Anthropic console
5. **Customize Hooks**: Add project-specific hooks in `.claude/hooks/`

## Security Best Practices

- Never commit API keys (use `.env` and `.gitignore`)
- Use fine-grained GitHub tokens with minimal permissions
- Review all ADW-generated code before merging
- Set up PR review requirements
- Monitor API usage and set billing alerts

## Troubleshooting

### ADW Not Working

```bash
# Check environment variables
env | grep -E "(GITHUB|ANTHROPIC|CLAUDE)"

# Verify GitHub auth
gh auth status

# Test Claude Code
claude --version
```

### Start Script Not Working

The template `start.sh` needs customization for your project. Edit it to start your specific application.

## Next Steps

1. Remove this README or customize it for your project
2. Set up your application in `app/`
3. Configure environment variables in `.env`
4. Customize `scripts/start.sh` to start your app
5. Create your first GitHub issue and let ADW process it!

## Resources

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [ADW Documentation](./adws/README.md)
- [Anthropic API Docs](https://docs.anthropic.com/)
- [GitHub CLI Docs](https://cli.github.com/)

## License

[Your License Here]

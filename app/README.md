# Application Directory

This directory is where your application code lives. The structure is intentionally flexible to accommodate different project types.

## Project Types

Depending on your project, this directory might contain:

### Web Application (Frontend + Backend)
```
app/
├── client/          # Frontend code (React, Vue, Svelte, etc.)
├── server/          # Backend code (FastAPI, Express, Django, etc.)
└── shared/          # Shared types, utilities, etc.
```

### CLI Application
```
app/
├── src/            # Source code
├── tests/          # Test files
└── pyproject.toml  # or package.json, Cargo.toml, etc.
```

### Backend API Only
```
app/
├── api/            # API endpoints
├── models/         # Data models
├── services/       # Business logic
├── tests/          # Test files
└── main.py         # Entry point
```

### Frontend Application Only
```
app/
├── src/            # Source code
│   ├── components/
│   ├── pages/
│   └── utils/
├── public/         # Static assets
└── package.json
```

### Monorepo
```
app/
├── packages/
│   ├── web/        # Web app
│   ├── mobile/     # Mobile app
│   └── shared/     # Shared code
└── package.json
```

## Getting Started

1. Remove this README
2. Initialize your project structure
3. Update the root `scripts/start.sh` if needed to start your application
4. Update the root `README.md` with project-specific information

## Integration with ADW

The AI Developer Workflow (ADW) system in the `adws/` directory will work with whatever structure you create here. It will:
- Read and understand your codebase structure
- Generate specs in the `specs/` directory
- Implement features according to your project architecture
- Create pull requests with the changes

The ADW system is agnostic to your application structure and will adapt to your project's needs.

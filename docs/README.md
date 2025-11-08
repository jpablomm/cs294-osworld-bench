# Green Agent Documentation

This directory contains comprehensive documentation for the Green Agent project, organized by topic.

## 📚 Documentation Structure

### Getting Started
- **[Native Mode Guide](getting-started/NATIVE_MODE.md)** - How to use native OSWorld mode (recommended)
- **[Complete System Guide](getting-started/RUN_COMPLETE_SYSTEM.md)** - End-to-end system setup and usage
- **[OSWorld Integration](getting-started/OSWORLD_INTEGRATION.md)** - OSWorld dependency installation and testing

### Architecture
- **[Cloud-First Architecture](architecture/CLOUD_FIRST_ARCHITECTURE.md)** - Production architecture with MIG, Cloud Run, and auto-scaling

### Deployment
- **[GCP Deployment](deployment/GCP_DEPLOYMENT.md)** - Deploying Green Agent to Google Cloud Platform
- **[Golden Image Creation](deployment/CREATE_GOLDEN_IMAGE.md)** - Creating OSWorld golden images for fast VM deployment
- **[GNOME Image Deployment](deployment/DEPLOY_GNOME_IMAGE.md)** - Deploying OSWorld with full GNOME desktop
- **[Cloud SQL Migration](deployment/CLOUD_SQL_MIGRATION.md)** - Migrating from SQLite to PostgreSQL
- **[Cloud SQL Quickstart](deployment/CLOUD_SQL_QUICKSTART.md)** - Quick reference for Cloud SQL setup

### API Reference
- **[OSWorld API](api/OSWORLD_API.md)** - Complete REST API reference for OSWorld server

### Troubleshooting
- **[OSWorld Debugging](troubleshooting/DEBUG_OSWORLD.md)** - Common issues and solutions


## 🚀 Quick Links

### For New Users
1. Start with [Native Mode Guide](getting-started/NATIVE_MODE.md)
2. Follow [Complete System Guide](getting-started/RUN_COMPLETE_SYSTEM.md)
3. Reference [OSWorld API](api/OSWORLD_API.md) as needed

### For Developers
1. Review [Cloud-First Architecture](architecture/CLOUD_FIRST_ARCHITECTURE.md)
2. Check [GCP Deployment Guide](deployment/GCP_DEPLOYMENT.md)
3. See [Troubleshooting Guide](troubleshooting/DEBUG_OSWORLD.md) for common issues

### For DevOps
1. Read [Golden Image Creation](deployment/CREATE_GOLDEN_IMAGE.md)
2. Follow [Cloud SQL Migration](deployment/CLOUD_SQL_MIGRATION.md) for production
3. Review [GNOME Image Deployment](deployment/DEPLOY_GNOME_IMAGE.md) for full desktop support

## 📖 Main Documentation

The main project README is located at [../README.md](../README.md) and provides:
- Project overview and status
- Quick start guides
- Key features and architecture
- Performance metrics
- Cost analysis

## 🔍 Finding What You Need

- **Setting up locally?** → [Getting Started](getting-started/)
- **Deploying to production?** → [Deployment](deployment/)
- **Understanding the system?** → [Architecture](architecture/)
- **API reference?** → [API](api/)
- **Having issues?** → [Troubleshooting](troubleshooting/)

## 📝 Documentation Standards

All documentation follows these conventions:
- **Code blocks** include working examples
- **Commands** are copy-paste ready
- **Troubleshooting** sections address common issues
- **Architecture diagrams** use ASCII art
- **Cost estimates** are included where relevant

## 🤝 Contributing

When adding or updating documentation:
1. Place files in the appropriate subdirectory
2. Update this index if adding new sections
3. Follow existing formatting conventions
4. Include code examples and troubleshooting tips
5. Update the main README if adding major features


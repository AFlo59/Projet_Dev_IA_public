# D&D GameMaster AI

An AI-powered Dungeons & Dragons Game Master system built with modern technologies, designed to provide an immersive tabletop roleplaying experience.

## Project Overview

The D&D GameMaster AI is composed of three main services:

1. **DataReference**: A system for managing D&D reference data
   - Bronze database: Stores raw imported data
   - Silver database: Stores transformed and optimized data
   - REST API: Exposes the reference data securely
   
2. **LLMGameMaster**: An AI service for generating narrative content
   - Uses OpenAI's GPT-4o or Claude from Anthropic
   - Contextual responses based on campaign history, character data, and D&D reference data
   - API for integrating with the web application
   
3. **WebApp**: A web application for users
   - User authentication and management
   - Campaign and character creation and management
   - Interactive chat interface with the AI Game Master

## Architecture

The entire system is containerized using Docker and orchestrated with Docker Compose:

### System Components

1. **[DataCollection](documents/datacollection/README.md)** - Data scraping and collection
   - Scrapes D&D reference data from GitHub repositories
   - Downloads JSON files and images from official sources
   - Organizes data in structured output directories

2. **[DataReference](documents/datareference/README.md)** - ETL pipeline and reference data API
   - **Bronze Layer**: Raw data import from DataCollection
   - **Silver Layer**: Transformed and optimized reference data  
   - **API Layer**: Secure REST API with JWT authentication

3. **[LLMGameMaster](documents/llmgamemaster/README.md)** - AI-powered Game Master service
   - Integrates with OpenAI GPT-4o and Anthropic Claude
   - Generates narrative content, NPCs, locations, and quests
   - Provides context-aware responses using D&D reference data

4. **[WebApp](documents/webapp/README.md)** - Web application and user interface
   - ASP.NET Core MVC application with responsive design
   - User management with ASP.NET Identity
   - Campaign and character management
   - Interactive AI Game Master interface

### Data Flow
```
DataCollection → DataReference (Bronze) → DataReference (Silver) → DataReference API
                                                                        ↓
WebApp ←→ LLMGameMaster ←→ Reference Data + Game Database
```

### Infrastructure
- **PostgreSQL databases**: Separate databases for each layer (Bronze, Silver, App)
- **Docker orchestration**: All services containerized and networked
- **Secure communication**: JWT tokens for inter-service authentication
- **Email integration**: User registration and notification system

## Requirements

- Docker and Docker Compose
- Internet connection for LLM API access
- Minimum 4GB RAM and 10GB disk space

## Documentation

Comprehensive documentation is available in the `documents` directory:

### Module Documentation
- [DataCollection Module](documents/datacollection/README.md) - Data collection and scraping system
- [DataReference Module](documents/datareference/README.md) - ETL pipeline and reference data API
- [LLMGameMaster Module](documents/llmgamemaster/README.md) - AI-powered Game Master service
- [WebApp Module](documents/webapp/README.md) - Web application and user interface

### Legacy Documentation (docs/)
The `docs/` directory contains additional technical documentation and troubleshooting guides:
- [Project Documentation](docs/PROJECT_DOCUMENTATION.md) - Complete technical overview
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [JWT Integration Guide](docs/JWT_INTEGRATION_GUIDE.md) - Authentication setup
- [CI/CD Guide](docs/CI-CD-Guide.md) - Deployment and automation

## Setup

### Quick Setup on Linux/macOS

1. Clone the repository
2. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Open http://localhost in your browser

### Quick Setup on Windows

1. Clone the repository
2. Run the setup script in PowerShell:
   ```powershell
   .\setup.ps1
   ```
3. Open http://localhost in your browser

For detailed setup instructions, refer to the [Setup Guide](documents/setup/SETUP_GUIDE.md).

## Development

For development, you can modify the source code and rebuild the containers:

```bash
docker-compose build
docker-compose up -d
```

## Security

- JWT authentication for API access
- Secure password storage with ASP.NET Identity
- Role-based access control
- Email verification for new accounts

For detailed security information, refer to the [Security Documentation](documents/security/SECURITY.md).

## Project Status

Current project status and roadmap can be found in the [Roadmap](roadmap.md) file.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
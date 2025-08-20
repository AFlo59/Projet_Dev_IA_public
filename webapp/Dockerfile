FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app
EXPOSE 80
EXPOSE 443

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["DnDGameMaster.WebApp.csproj", "./"]
RUN dotnet restore "DnDGameMaster.WebApp.csproj"
COPY . .
WORKDIR "/src"
RUN dotnet build "DnDGameMaster.WebApp.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "DnDGameMaster.WebApp.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app

# Installer les outils PostgreSQL pour les healthchecks
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Créer les répertoires pour les fichiers statiques
RUN mkdir -p /app/wwwroot/css /app/wwwroot/js /app/wwwroot/lib /app/wwwroot/images

# Copier les fichiers publiés
COPY --from=publish /app/publish .

# Copier explicitement les fichiers statiques
COPY wwwroot/css/site.css /app/wwwroot/css/
COPY wwwroot/js/site.js /app/wwwroot/js/

# Add entrypoint script with proper line endings and permissions
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"] 
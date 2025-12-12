FROM mcr.microsoft.com/devcontainers/javascript-node:20-bookworm

RUN apt-get update \
    #
    # install gcloud
    && apt-get install -y apt-transport-https ca-certificates gnupg curl \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update \
    && apt-get install -y google-cloud-sdk \
    #
    # Create config directory
    && mkdir -p /home/node/.claude \
    && chown -R node:node /home/node/.claude

USER node

# Add ~/.local/bin to PATH for Claude Code
ENV PATH="/home/node/.local/bin:${PATH}"

ARG APP_FOLDER
WORKDIR ${APP_FOLDER}

    # Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION} \
    #
    # Install uv MCP servers
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    #
    # update npm !!!--ignore-scripts due to Shai Hulud attack!!!
    && npm install --ignore-scripts -g npm@11.4.2

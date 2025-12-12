#!/bin/bash

# Read .env file and export variables
echo -e "Reading environment variables from .env file ..."
if [ -f ./.devcontainer/.env ]; then
    set -a
    source ./.devcontainer/.env
    set +a
    echo -e "done\n"
else
    echo -e "Warning: .env file not found\n"
fi

# Login to Google Cloud
echo -e "Setting gcp project ..."
gcloud config set project ${GCP_PROJECT_ID}
echo -e "done\n"

echo -e "Logging in to Google Cloud ..."
gcloud auth application-default login
echo -e "done\n"

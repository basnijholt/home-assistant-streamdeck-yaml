FROM mambaorg/micromamba:lunar

# Run the container as root to get access to the USB devices
USER root

# Install unidep
RUN micromamba install --name base --channel conda-forge --yes unidep git
WORKDIR /app

# Copy the dependencies file for pip
COPY . /app/
COPY .git /app/.git

# Install the required dependencies
RUN eval "$(micromamba shell hook --shell bash)" && \
    micromamba activate base && \
    unidep install -e .

# Set the entrypoint
CMD ["home-assistant-streamdeck-yaml"]

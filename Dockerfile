FROM mambaorg/micromamba:lunar

# Add udev rule for the Stream Deck
USER root
RUN apt-get update && apt-get install -y usbutils
RUN mkdir -p /etc/udev/rules.d && \
    echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' > /etc/udev/rules.d/99-streamdeck.rules
USER ${MAMBA_USER}

# Install unidep
RUN micromamba install --name base --channel conda-forge --yes unidep git
WORKDIR /app

# Copy the dependencies file for pip
COPY --chown=${MAMBA_USER}:${MAMBA_USER} . /app/
COPY --chown=${MAMBA_USER}:${MAMBA_USER} .git /app/.git

# Install the required dependencies
RUN eval "$(micromamba shell hook --shell bash)" && \
    micromamba activate base && \
    unidep install -e .

# Set the entrypoint
CMD ["home-assistant-streamdeck-yaml"]

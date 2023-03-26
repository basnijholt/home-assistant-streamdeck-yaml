FROM debian:11

# Install dependencies
RUN apt-get update && apt-get install -y \
    # Micromamba installation dependencies
    curl \
    git \
    bzip2 \
    # Stream Deck dependencies
    libudev-dev \
    libusb-1.0-0-dev \
    libhidapi-libusb0 \
    libffi-dev \
    # Needed for cairosvg
    libcairo2-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add udev rule for the Stream Deck
RUN mkdir -p /etc/udev/rules.d
RUN echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' > /etc/udev/rules.d/99-streamdeck.rules

# Install micromamba
RUN curl micro.mamba.pm/install.sh | bash
ENV MAMBA_ROOT_PREFIX="/root/micromamba"
ENV MAMBA_EXE="/root/.local/bin/micromamba"

# Switch to shell, such that bashrc is sourced
SHELL ["bash", "-l" ,"-c"]

# Install Python 3.11
RUN micromamba activate && micromamba install --yes --channel conda-forge python=3.11

# Clone the repository
RUN git clone https://github.com/basnijholt/home-assistant-streamdeck-yaml.git

# Set the working directory to the repository
WORKDIR /home-assistant-streamdeck-yaml

# Install the required dependencies
RUN micromamba activate && pip install -e .

# Set the entrypoint to run the application
ENTRYPOINT ["/bin/bash", "-c", "source ~/.bashrc && micromamba activate && home-assistant-streamdeck-yaml"]

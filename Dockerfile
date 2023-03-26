FROM python:alpine3.17

# Install dependencies
RUN apk update && apk add --no-cache \
    # Stream Deck dependencies
    libusb \
    libusb-dev \
    hidapi-dev \
    libffi-dev \
    # Needed for cairosvg
    cairo-dev \
    # Needed for git clone
    git \
    openssh-client \
    # Needed to run pip install our requirements
    musl-dev gcc \
    && rm -rf /var/cache/apk/*

# Install numpy and matplotlib with apk
RUN apk add --no-cache \
    && rm -rf /var/cache/apk/*

# Add udev rule for the Stream Deck
RUN mkdir -p /etc/udev/rules.d
RUN echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' > /etc/udev/rules.d/99-streamdeck.rules

# Clone the repository
RUN git clone https://github.com/basnijholt/home-assistant-streamdeck-yaml.git /app

# Set the working directory to the repository
WORKDIR /app

# Install the required dependencies
RUN pip3 install -e .

# Set the entrypoint to run the application
ENTRYPOINT ["/bin/sh", "-c", "home-assistant-streamdeck-yaml"]

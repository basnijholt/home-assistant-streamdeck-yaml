FROM python:alpine3.17

# Install dependencies
RUN apk update && apk add --no-cache \
    # Stream Deck dependencies
    libusb \
    libusb-dev \
    hidapi-dev \
    libffi-dev \
    # Needed for git clone
    git \
    # Needed to run pip install our requirements
    musl-dev gcc \
    # Needed for cairosvg
    cairo-dev \
    # Needed for lxml
    libxml2-dev libxslt-dev \
    # Needed for Pillow
    tiff-dev jpeg-dev openjpeg-dev zlib-dev freetype-dev lcms2-dev \
    libwebp-dev tcl-dev tk-dev harfbuzz-dev fribidi-dev libimagequant-dev \
    libxcb-dev libpng-dev \
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

# Remove musl-dev and gcc
RUN apk del musl-dev gcc && rm -rf /var/cache/apk/*

# Set the entrypoint to run the application
ENTRYPOINT ["/bin/sh", "-c", "home-assistant-streamdeck-yaml"]

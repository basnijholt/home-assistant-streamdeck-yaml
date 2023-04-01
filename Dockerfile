FROM python:3.11-alpine3.17

# Install dependencies
RUN apk update && apk add --no-cache \
    # Stream Deck dependencies
    libusb \
    libusb-dev \
    hidapi-dev \
    libffi-dev \
    # Needed for cairosvg
    cairo-dev \
    # Needed for lxml
    libxml2-dev libxslt-dev \
    # Needed for Pillow
    jpeg-dev zlib-dev freetype-dev libpng-dev \
    # Openblas for Matplotlib (numpy)
    openblas-dev \
    # Needed for pip install
    && apk add --virtual build-deps \
    # General
    gcc python3-dev musl-dev \
    # Needed for matplotlib
    g++ gfortran py-pip build-base wget \
    && rm -rf /var/cache/apk/*

# Add udev rule for the Stream Deck
RUN mkdir -p /etc/udev/rules.d
RUN echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' > /etc/udev/rules.d/99-streamdeck.rules

# Clone the repository
COPY . /app

# Set the working directory to the repository
WORKDIR /app

# Install the required dependencies
RUN pip3 install -e ".[colormap]" && \
    # Remove musl-dev and gcc
    apk del build-deps && rm -rf /var/cache/apk/* && \
    # Purge the pip cache
    pip3 cache purge

# Set the entrypoint to run the application
ENTRYPOINT ["/bin/sh", "-c", "home-assistant-streamdeck-yaml"]

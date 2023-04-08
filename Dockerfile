FROM python:3.11-alpine3.17

# Install dependencies
RUN apk --update --no-cache add \
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
    && apk add --no-cache --virtual build-deps \
    # General
    gcc python3-dev musl-dev \
    # Needed for matplotlib
    g++ gfortran py-pip build-base wget \
    # Needed for getting the version from git
    git

# Add udev rule for the Stream Deck
RUN mkdir -p /etc/udev/rules.d && \
    echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"' > /etc/udev/rules.d/99-streamdeck.rules

COPY .git /app/.git

# Set the working directory to the repository
WORKDIR /app

# Copy files to the working directory
COPY . /app

# Install the required dependencies
RUN pip3 install -e ".[colormap]" --no-cache-dir && \
    # Remove musl-dev and gcc
    apk del build-deps && \
    rm -rf /var/cache/apk/*

# Set the entrypoint to run the application
ENTRYPOINT ["/bin/sh", "-c", "home-assistant-streamdeck-yaml"]

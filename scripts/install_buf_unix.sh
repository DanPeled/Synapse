#!/bin/bash
set -e

# Check if npm is installed; if not, install Node.js (includes npm)
if ! command -v npm >/dev/null; then
  echo "npm not found. Installing Node.js and npm..."

  if command -v apt-get >/dev/null; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y nodejs npm
  elif command -v brew >/dev/null; then
    # macOS Homebrew
    brew install node
  elif command -v yum >/dev/null; then
    # Fedora/CentOS
    sudo yum install -y nodejs npm
  else
    echo "Could not detect package manager. Please install Node.js and npm manually."
    exit 1
  fi
else
  echo "npm is already installed."
fi

# Install buf
if ! command -v buf >/dev/null; then
  echo "Installing buf..."
  sudo curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m)" -o /usr/local/bin/buf
  sudo chmod +x /usr/local/bin/buf
else
  echo "buf is already installed."
fi

# Install protoc-gen-typescript
if ! command -v protoc-gen-ts >/dev/null; then
  echo "Installing protoc-gen-typescript..."
  npm install -g protoc-gen-typescript
else
  echo "protoc-gen-typescript is already installed."
fi

# Install protobuf python package
if ! python3 -c "import google.protobuf" >/dev/null 2>&1; then
  echo "Installing protobuf python package..."
  pip install protobuf
else
  echo "protobuf python package is already installed."
fi

# Install protoc-gen-ts_proto
if ! command -v protoc-gen-ts_proto >/dev/null; then
  echo "Installing protoc-gen-ts_proto..."
  npm install -g ts-proto
else
  echo "protoc-gen-ts_proto is already installed."
fi

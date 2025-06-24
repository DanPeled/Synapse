function Install-NodeJs {
    $nodeInstalled = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $nodeInstalled) {
        Write-Host "npm not found. Installing Node.js..."

        $installerUrl = "https://nodejs.org/dist/v20.5.1/node-v20.5.1-x64.msi"
        $installerPath = "$env:TEMP\nodejs.msi"

        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
        Write-Host "Downloaded Node.js installer."

        Start-Process msiexec.exe -ArgumentList "/i `"$installerPath`" /quiet /norestart" -Wait

        Remove-Item $installerPath

        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Write-Host "Node.js and npm installed successfully."
        } else {
            Write-Host "Node.js installation failed. Please install it manually."
            exit 1
        }
    } else {
        Write-Host "npm is already installed."
    }
}

# Install Node.js/npm if missing
Install-NodeJs

# Install buf
if (-not (Get-Command buf -ErrorAction SilentlyContinue)) {
    Write-Host "Installing buf..."
    $bufUrl = "https://github.com/bufbuild/buf/releases/latest/download/buf-Windows-x86_64.exe"
    $bufPath = "$env:USERPROFILE\bin\buf.exe"

    # Ensure directory exists
    if (-not (Test-Path "$env:USERPROFILE\bin")) {
        New-Item -ItemType Directory -Path "$env:USERPROFILE\bin" | Out-Null
    }

    Invoke-WebRequest -Uri $bufUrl -OutFile $bufPath
    Write-Host "Downloaded buf to $bufPath"

    # Add to PATH if not already present (temporary for this session)
    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq "$env:USERPROFILE\bin" })) {
        $env:PATH = "$env:USERPROFILE\bin;$env:PATH"
        Write-Host "Added $env:USERPROFILE\bin to PATH for this session."
    }
} else {
    Write-Host "buf is already installed."
}

# Install protoc-gen-typescript
if (-not (Get-Command protoc-gen-ts -ErrorAction SilentlyContinue)) {
    Write-Host "Installing protoc-gen-typescript..."
    npm install -g protoc-gen-typescript
} else {
    Write-Host "protoc-gen-typescript is already installed."
}

# Install protobuf python package
try {
    python -c "import google.protobuf" | Out-Null
    Write-Host "protobuf python package is already installed."
} catch {
    Write-Host "Installing protobuf python package..."
    pip install protobuf
}

# Install protoc-gen-ts_proto
if (-not (Get-Command protoc-gen-ts_proto -ErrorAction SilentlyContinue)) {
    Write-Host "Installing protoc-gen-ts_proto..."
    npm install -g ts-proto
} else {
    Write-Host "protoc-gen-ts_proto is already installed."
}

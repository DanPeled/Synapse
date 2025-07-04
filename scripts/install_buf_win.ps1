function Check-Winget {
    $wingetInstalled = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetInstalled) {
        Write-Host "winget is not installed or not available in PATH."
        Write-Host "Please install winget (App Installer) from the Microsoft Store or:"
        Write-Host "https://aka.ms/getwinget"
        Write-Host "After installing winget, rerun this script."
        exit 1
    }
}

function Confirm-Installation($toInstall) {
    Write-Host "The script will attempt to install the following components if missing:`n"
    foreach ($item in $toInstall) {
        Write-Host "- $item"
    }
    Write-Host ""
    $response = Read-Host "Do you want to continue? (Y/N)"
    if ($response.ToUpper() -ne "Y") {
        Write-Host "Installation aborted by user."
        exit 0
    }
}

function Install-NodeJs {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Node.js via winget..."
        winget install --id OpenJS.NodeJS.LTS -e --silent
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
            Write-Host "Node.js installation failed. Please install it manually."
            exit 1
        }
        Write-Host "Node.js and npm installed successfully."
    } else {
        Write-Host "npm is already installed."
    }
}

function Install-Buf {
    if (-not (Get-Command buf -ErrorAction SilentlyContinue)) {
        Write-Host "Installing buf via winget..."
        winget install --id buf.build.buf -e --silent
        if (-not (Get-Command buf -ErrorAction SilentlyContinue)) {
            Write-Host "buf installation failed. Please install it manually."
            exit 1
        }
        Write-Host "buf installed successfully."
    } else {
        Write-Host "buf is already installed."
    }
}

function Install-Protoc {
    if (-not (Get-Command protoc -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Protocol Buffers compiler via winget..."
        winget install --id Google.Protobuf.Compiler -e --silent
        if (-not (Get-Command protoc -ErrorAction SilentlyContinue)) {
            Write-Host "protoc installation failed. Please install it manually."
            exit 1
        }
        Write-Host "protoc installed successfully."
    } else {
        Write-Host "protoc is already installed."
    }
}

function Install-ProtocGenTs {
    if (-not (Get-Command protoc-gen-ts -ErrorAction SilentlyContinue)) {
        Write-Host "Installing protoc-gen-typescript via npm..."
        npm install -g protoc-gen-typescript
        Write-Host "protoc-gen-typescript installed."
    } else {
        Write-Host "protoc-gen-typescript is already installed."
    }
}

function Install-ProtobufPython {
    try {
        python -c "import google.protobuf" | Out-Null
        Write-Host "protobuf python package is already installed."
    } catch {
        Write-Host "Installing protobuf python package via pip..."
        pip install protobuf
        Write-Host "protobuf python package installed."
    }
}

function Install-TsProto {
    if (-not (Get-Command protoc-gen-ts_proto -ErrorAction SilentlyContinue)) {
        Write-Host "Installing protoc-gen-ts_proto via npm..."
        npm install -g ts-proto
        Write-Host "protoc-gen-ts_proto installed."
    } else {
        Write-Host "protoc-gen-ts_proto is already installed."
    }
}

# Check if winget is installed
Check-Winget

# Determine what needs installing
$installList = @()
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { $installList += "Node.js + npm" }
if (-not (Get-Command buf -ErrorAction SilentlyContinue)) { $installList += "buf" }
if (-not (Get-Command protoc -ErrorAction SilentlyContinue)) { $installList += "protoc (Protocol Buffers compiler)" }
if (-not (Get-Command protoc-gen-ts -ErrorAction SilentlyContinue)) { $installList += "protoc-gen-typescript (npm package)" }

try {
    python -c "import google.protobuf" | Out-Null
} catch {
    $installList += "protobuf Python package (pip)"
}

if (-not (Get-Command protoc-gen-ts_proto -ErrorAction SilentlyContinue)) { $installList += "protoc-gen-ts_proto (npm package)" }

if ($installList.Count -eq 0) {
    Write-Host "All required components are already installed. Nothing to do."
    exit 0
}

# Confirm with user before proceeding
Confirm-Installation $installList

# Proceed with installs
Install-NodeJs
Install-Buf
Install-Protoc
Install-ProtocGenTs
Install-ProtobufPython
Install-TsProto

Write-Host "`nAll requested installations completed."

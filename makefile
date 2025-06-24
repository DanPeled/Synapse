.PHONY: clean install build install_buf generate_buf

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf synapse_ui/out/
	rm -rf synapse_net/src/synapse_net/proto/
	rm -rf synapse_ui/src/proto/

install_buf:
	@echo "Detecting OS..."
	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
	ARCH=$$(uname -m); \
	if [ "$$OS" = "mingw64_nt-10.0" ] || [ "$$OS" = "msys_nt-10.0" ]; then \
		OS="windows"; EXT=".exe"; \
	else \
		EXT=""; \
	fi; \
	\
	if ! command -v buf >/dev/null 2>&1; then \
		echo "Installing buf for $$OS..."; \
		URL="https://github.com/bufbuild/buf/releases/latest/download/buf-$$OS-$$ARCH$$EXT"; \
		echo "Downloading: $$URL"; \
		curl -sSL "$$URL" -o ./buf$$EXT || (echo "Failed to download buf"; exit 1); \
		chmod +x ./buf$$EXT; \
		if [ "$$OS" = "windows" ]; then \
			mkdir -p "$$USERPROFILE/bin"; \
			mv ./buf$$EXT "$$USERPROFILE/bin/buf.exe"; \
			echo "Add $$USERPROFILE/bin to your PATH if it's not already."; \
		else \
			sudo mv ./buf$$EXT /usr/local/bin/buf; \
		fi; \
	else \
		echo "buf is already installed."; \
	fi

	@echo "Checking for protoc-gen-typescript..."
	@command -v protoc-gen-ts >/dev/null 2>&1 || npm install -g protoc-gen-typescript

	@echo "Checking for protoc-gen-ts_proto..."
	@command -v protoc-gen-ts_proto >/dev/null 2>&1 || npm install -g ts-proto

	@echo "Checking for Python protobuf module..."
	@python3 -c "import google.protobuf" >/dev/null 2>&1 || pip install protobuf

install:  # installs the synapse runtime pip package locally
	pip install .

generate_buf:
	cd synapse_net/proto && \
		buf lint && \
		buf format -w && \
		buf generate

build:
	python3 -m build .
	cd synapse_ui && npm run build

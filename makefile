.PHONY: clean install build install_buf generate_buf

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf synapse_ui/out/

install_buf:
	@if ! command -v buf > /dev/null; then \
		echo "Installing buf..."; \
		sudo curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(shell uname -s)-$(shell uname -m)" -o /usr/local/bin/buf; \
		sudo chmod +x /usr/local/bin/buf; \
	else \
		echo "buf is already installed."; \
	fi

	@if ! command -v protoc-gen-ts > /dev/null; then \
		echo "Installing protoc-gen-typescript..."; \
		npm install -g protoc-gen-typescript; \
	else \
		echo "protoc-gen-typescript is already installed."; \
	fi

	@if ! python3 -c "import google.protobuf" > /dev/null 2>&1; then \
		echo "Installing protobuf python package..."; \
		pip install protobuf; \
	else \
		echo "protobuf python package is already installed."; \
	fi

	@if ! command -v protoc-gen-python > /dev/null; then \
		echo "protoc-gen-python not found, creating shim script..."; \
		echo '#!/bin/bash' | sudo tee /usr/local/bin/protoc-gen-python > /dev/null; \
		echo 'python3 -m grpc_tools.protoc "$$@"' | sudo tee -a /usr/local/bin/protoc-gen-python > /dev/null; \
		sudo chmod +x /usr/local/bin/protoc-gen-python; \
	else \
		echo "protoc-gen-python already exists."; \
	fi

	@if ! command -v protoc-gen-ts_proto > /dev/null; then \
		echo "Installing protoc-gen-ts_proto..."; \
		npm install -g ts-proto; \
	else \
		echo "protoc-gen-ts_proto is already installed."; \
	fi

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

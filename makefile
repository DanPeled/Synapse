.PHONY: clean install build install_buf generate_buf format clean_buf_out

# Detect platform
IS_WINDOWS := $(findstring Windows_NT, $(OS))
ifeq ($(IS_WINDOWS), Windows_NT)
    RM = rmdir /S /Q
    DEL = del /F /Q
    NULL = nul
    SHELL := cmd
    CD = cd
else
    RM = rm -rf
    NULL = /dev/null
    SHELL := /bin/bash
    CD = cd
endif

# Remove generated protobuf directories
clean_buf_out:
	@$(RM) synapse_net/src/synapse_net/proto/ 2>$(NULL) || true
	@$(RM) synapse_ui/src/proto/ 2>$(NULL) || true

# General clean
clean:
	@$(RM) build/ dist/ .pytest_cache/ synapse_ui/out/ 2>$(NULL) || true
	@$(MAKE) clean_buf_out

# Install Python package locally
install:
	pip install .

# Generate protobuf code with buf
generate_buf:
	@$(MAKE) clean_buf_out
	@$(CD) synapse_net/proto && \
		buf lint && \
		buf format -w && \
		buf generate --template buf-ts.yaml && \
		buf generate --template buf-python.yaml && \
		$(CD) .. &\
		$(CD) .. &\
		make install

# Format code with tools
format:
	@python3 -m ruff format . >$(NULL) 2>&1 || echo ruff format failed
	@python3 -m isort . >$(NULL) 2>&1 || echo isort failed
	@$(CD) synapse_ui && npx prettier . --write >$(NULL) 2>&1 || echo prettier failed
	@$(CD) synapse_net/proto && \
		buf format -w

# Build Python and UI
build:
	python3 -m build .
	@$(CD) synapse_ui && npm run build

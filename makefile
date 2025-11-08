.PHONY: clean install build generate_buf format clean_buf_out

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
	@echo Building UI...
	@$(CD) synapse_ui && npm run build
	@$(CD) ..
	@echo Installing Synapse Package...
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

license:
	shopt -s globstar; python3 -m reuse annotate --license GPL-3.0-or-later --copyright "Dan Peled" **/*.py

format:
	make license
	@echo Ruff format...
	@python3 -m ruff format . >$(NULL) 2>&1 || echo ruff format failed
	@echo Isort format...
	@python3 -m isort . >$(NULL) 2>&1 || echo isort failed
	@echo Prettier format...
	@$(CD) synapse_ui && npm run format
	@echo ProtoBuf format...
	@cd ..
	@$(CD) synapse_net/proto && \
		buf format -w
	@cd ..
	@echo SynapseLib SpotlessApply
	@${CD} synapse_lib && \
		./gradlew spotlessApply

test:
	@echo Reinstalling Synapse Runtime...
	@make install
	@echo Starting Tests...
	@python3 -m pytest . --ignore=synapse_lib/

# Build Python and UI
build:
	make install
	python3 setup.py sdist bdist_wheel

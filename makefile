.PHONY: clean install build install_buf generate_buf

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf synapse_ui/out/
	rm -rf synapse_net/src/synapse_net/proto/
	rm -rf synapse_ui/src/proto/

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

from synapse.synapse import PipelineHandler, Synapse

if __name__ == "__main__":
    handler = PipelineHandler("./")
    s = Synapse()
    if s.init(handler):
        s.run()

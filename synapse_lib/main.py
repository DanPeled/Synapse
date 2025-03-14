from core import Synapse, PipelineHandler

if __name__ == "__main__":
    handler = PipelineHandler("./")
    s = Synapse()
    if s.init(handler):
        s.run()

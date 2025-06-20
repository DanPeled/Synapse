export namespace PipelineManagement {
  export namespace SettingsManagement {
    export enum ConstraintType {
      NumberRange,
      Boolean,
      ListOfOptions,
    }
  }

  export interface PipelineSetting {
    constraint: SettingsManagement.ConstraintType;
  }

  export class Pipeline {
    constructor(
      public name: string,
      public type: string,
      public settings: Map<string, PipelineSetting>,
    ) {}
  }

  export class PipelineContext {
    pipelines: Pipeline[];
    pipelineTypes: string[];

    public constructor(pipelines: Pipeline[], pipelineTypes: string[]) {
      this.pipelines = [...pipelines];
      this.pipelineTypes = [...pipelineTypes];
    }

    public addPipeline(pipeline: Pipeline) {
      this.pipelines.push(pipeline);
    }

    public getPipeline(name: string): Pipeline | undefined {
      return this.pipelines.find((pipe) => pipe.name == name);
    }
  }
}

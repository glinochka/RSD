declare module 'onnxruntime-node' {
  export class Tensor {
    constructor(
      type: string,
      data: ArrayLike<number> | BigInt64Array,
      dims?: number[],
    );
    readonly data: ArrayLike<number> | BigInt64Array;
  }

  export class InferenceSession {
    static create(
      path: string,
      options?: { executionProviders?: string[] },
    ): Promise<InferenceSession>;
    runSync?(feeds: Record<string, Tensor>): Record<string, Tensor>;
    run(feeds: Record<string, Tensor>): Promise<Record<string, Tensor>>;
  }
}

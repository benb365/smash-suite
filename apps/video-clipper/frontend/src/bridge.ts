import type { ScreenState } from './types';

export function action(name: string, data: unknown = {}): Promise<ScreenState> {
  return new Promise((resolve, reject) => {
    NativeModules.Product.call(name, data, (reply: { value?: string; error?: string }) => {
      if (reply.error) reject(new Error(reply.error));
      else resolve(JSON.parse(reply.value!) as ScreenState);
    });
  });
}
